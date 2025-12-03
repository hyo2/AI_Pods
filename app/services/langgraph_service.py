# app/services/langgraph_service.py
import os
import asyncio
import tempfile
import logging
import shutil
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
import httpx

from app.services.supabase import supabase, upload_bytes
from app.services.podcast import run_podcast_generation

logger = logging.getLogger(__name__)


async def download_file(url: str, dest_path: Path) -> None:
    """Supabase Storage에서 파일 다운로드"""
    logger.info(f"다운로드 시작: {url}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=120.0)
            response.raise_for_status()
            dest_path.write_bytes(response.content)
        logger.info(f"다운로드 완료: {dest_path.name} ({dest_path.stat().st_size} bytes)")
    except Exception as e:
        logger.error(f"다운로드 실패 [{url}]: {e}")
        raise


async def save_to_database(
    project_id: int,
    input_ids: List[int],
    audio_url: str,
    script_text: str,
    script_url: str,
    host1: str,
    host2: str,
    style: str,
    duration: float = 0.0,
    title: str = "새 에피소드",
    summary: str = None
) -> int:
    """
    생성된 팟캐스트를 output_contents 테이블에 저장
    
    Returns:
        생성된 output_content의 ID
    """
    logger.info(f"DB 저장 시작 - Project: {project_id}")
    
    try:
        # expires_at: 현재로부터 30일 후
        expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat()
        
        # options JSON 생성
        options = {
            "host1": host1,
            "host2": host2,
            "style": style
        }
        
        # metadata JSON 생성
        metadata = {
            "duration": duration,
            "input_count": len(input_ids),
            "generated_at": datetime.utcnow().isoformat()
        }
        
        # output_contents 테이블에 삽입
        insert_data = {
            "project_id": project_id,
            "input_content_ids": input_ids,
            "options": options,
            "script_text": script_text,
            "storage_path": audio_url,
            "metadata": metadata,
            "expires_at": expires_at,
            "title": title,
            "summary": summary,
            "status": "completed"
        }
        
        result = supabase.table("output_contents").insert(insert_data).execute()
        
        if not result.data:
            raise RuntimeError("DB 저장 실패: 결과가 없습니다")
        
        output_id = result.data[0]["id"]
        logger.info(f"DB 저장 완료 - Output ID: {output_id}")
        
        return output_id
        
    except Exception as e:
        logger.error(f"DB 저장 실패: {e}", exc_info=True)
        raise


def calculate_audio_duration(audio_path: Path) -> float:
    """
    오디오 파일의 재생 시간 계산 (초 단위)
    
    ffmpeg 또는 mutagen 라이브러리 필요
    간단하게는 파일 크기로 추정 가능 (192kbps MP3 기준)
    """
    try:
        # ffprobe 사용 (ffmpeg 설치 필요)
        import subprocess
        
        result = subprocess.run(
            [
                "ffprobe", 
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path)
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        duration = float(result.stdout.strip())
        return duration
        
    except Exception as e:
        logger.warning(f"오디오 길이 계산 실패 (추정값 사용): {e}")
        
        # 폴백: 파일 크기로 추정 (192kbps = 24KB/s)
        try:
            file_size = audio_path.stat().st_size
            estimated_duration = file_size / (24 * 1024)  # 초 단위
            return estimated_duration
        except:
            return 0.0


async def run_langgraph(
    input_ids: List[int],
    host1: str,
    host2: str,
    style: str,
    title: str = "새 에피소드",
    summary: str = None
) -> Dict[str, Any]:
    """
    LangGraph 팟캐스트 생성 및 DB 저장
    
    Args:
        input_ids: input_contents 테이블의 ID 목록
        host1: 진행자 이름
        host2: 게스트 이름
        style: 팟캐스트 스타일 (explain, debate, interview, summary)
        title: 에피소드 제목
        summary: 에피소드 요약
    
    Returns:
        생성된 팟캐스트 정보 및 output_id
    """
    
    # === 1. 환경 변수 검증 ===
    project_id = os.getenv("VERTEX_AI_PROJECT_ID")
    region = os.getenv("VERTEX_AI_REGION", "us-central1")
    sa_file = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE")
    
    if not project_id:
        raise ValueError("VERTEX_AI_PROJECT_ID 환경 변수가 설정되지 않았습니다")
    if not sa_file or not os.path.exists(sa_file):
        raise ValueError(f"서비스 계정 파일을 찾을 수 없습니다: {sa_file}")
    
    logger.info(f"팟캐스트 생성 시작 - Project: {project_id}, Region: {region}, Style: {style}")
    logger.info(f"진행자: {host1}, 게스트: {host2}")
    
    # 임시 디렉토리 생성
    temp_dir = Path(tempfile.mkdtemp(prefix="podcast_"))
    logger.info(f"임시 디렉토리 생성: {temp_dir}")
    
    try:
        # === 2. 입력 소스 조회 ===
        logger.info(f"입력 소스 조회: {input_ids}")
        inputs_res = supabase.table("input_contents") \
            .select("*") \
            .in_("id", input_ids) \
            .execute()
        
        if not inputs_res.data:
            raise ValueError(f"입력 소스를 찾을 수 없습니다 (IDs: {input_ids})")
        
        logger.info(f"입력 소스 {len(inputs_res.data)}개 발견")
        
        # 사용자 정보 추출
        user_id = inputs_res.data[0]["user_id"]
        project_id_db = inputs_res.data[0]["project_id"]
        
        # === 3. 소스 파일 다운로드 ===
        sources = []
        download_tasks = []
        
        for inp in inputs_res.data:
            if inp["is_link"]:
                # 링크는 그대로 전달
                sources.append(inp["link_url"])
                logger.info(f"링크 추가: {inp['link_url']}")
            else:
                # 파일 다운로드
                storage_url = inp["storage_path"]
                file_name = inp["title"]
                local_path = temp_dir / file_name
                
                download_tasks.append(download_file(storage_url, local_path))
                sources.append(str(local_path))
        
        # 모든 다운로드 동시 실행
        if download_tasks:
            logger.info(f"{len(download_tasks)}개 파일 다운로드 중...")
            await asyncio.gather(*download_tasks)
            logger.info("모든 파일 다운로드 완료")
        
        if not sources:
            raise ValueError("처리할 소스가 없습니다")
        
        logger.info(f"총 {len(sources)}개 소스 준비 완료")
        
        # === 4. 팟캐스트 생성 ===
        logger.info("팟캐스트 생성 시작...")
        
        result = await asyncio.to_thread(
            run_podcast_generation,
            sources=sources,
            project_id=project_id,
            region=region,
            sa_file=sa_file,
            host_name=host1,
            guest_name=host2,
            style=style
        )
        
        logger.info(f"팟캐스트 생성 완료: {result['final_podcast_path']}")
        
        # === 5. 오디오 길이 계산 ===
        audio_path = Path(result['final_podcast_path'])
        transcript_path = Path(result['transcript_path']) if result.get('transcript_path') else None
        
        if not audio_path.exists():
            raise FileNotFoundError(f"오디오 파일이 생성되지 않았습니다: {audio_path}")
        
        duration = calculate_audio_duration(audio_path)
        logger.info(f"오디오 길이: {duration:.1f}초")
        
        # === 6. Supabase Storage 업로드 ===
        logger.info("오디오 파일 업로드 중...")
        with open(audio_path, 'rb') as f:
            audio_bytes = f.read()
        
        audio_url = upload_bytes(
            file_bytes=audio_bytes,
            folder=f"user/{user_id}/project/{project_id_db}/outputs",
            filename=audio_path.name,
            content_type="audio/mpeg"
        )
        
        if not audio_url:
            raise RuntimeError("오디오 파일 업로드 실패")
        
        logger.info(f"오디오 업로드 완료: {audio_url}")
        
        # 스크립트 파일 처리
        script_text = ""
        script_url = None
        
        if transcript_path and transcript_path.exists():
            logger.info("스크립트 파일 업로드 중...")
            with open(transcript_path, 'r', encoding='utf-8') as f:
                script_text = f.read()
            
            script_bytes = script_text.encode('utf-8')
            script_url = upload_bytes(
                file_bytes=script_bytes,
                folder=f"user/{user_id}/project/{project_id_db}/outputs",
                filename=transcript_path.name,
                content_type="text/plain"
            )
            logger.info(f"스크립트 업로드 완료: {script_url}")
        
        # === 7. DB에 저장 ===
        output_id = await save_to_database(
            project_id=project_id_db,
            input_ids=input_ids,
            audio_url=audio_url,
            script_text=script_text,
            script_url=script_url,
            host1=result["host_name"],
            host2=result["guest_name"],
            style=style,
            duration=duration,
            title=title or "새 에피소드",
            summary=summary
        )
        
        # === 8. 생성된 로컬 파일 삭제 ===
        logger.info("로컬 파일 정리 중...")
        if audio_path.exists():
            audio_path.unlink()
            logger.debug(f"삭제: {audio_path}")
        if transcript_path and transcript_path.exists():
            transcript_path.unlink()
            logger.debug(f"삭제: {transcript_path}")
        
        # === 9. 결과 반환 ===
        result_data = {
            "output_id": output_id,
            "audio_url": audio_url,
            "script": script_text,
            "script_url": script_url,
            "duration": duration,
            "images": [],
            "host1": result["host_name"],
            "host2": result["guest_name"],
            "style": style,
            "errors": result.get("errors", [])
        }
        
        logger.info(f"팟캐스트 생성 완료 - Output ID: {output_id}")
        if result_data["errors"]:
            logger.warning(f"경고 {len(result_data['errors'])}개: {result_data['errors']}")
        
        return result_data
        
    except Exception as e:
        logger.error(f"팟캐스트 생성 실패: {e}", exc_info=True)
        
        # 실패 시 DB에 실패 상태 기록 (선택사항)
        try:
            # 기본 정보만으로 실패 레코드 생성
            inputs_res = supabase.table("input_contents") \
                .select("user_id, project_id") \
                .in_("id", input_ids) \
                .limit(1) \
                .execute()
            
            if inputs_res.data:
                supabase.table("output_contents").insert({
                    "project_id": inputs_res.data[0]["project_id"],
                    "input_content_ids": input_ids,
                    "options": {"host1": host1, "host2": host2, "style": style},
                    "title": title or "새 에피소드",
                    "status": "failed",
                    "metadata": {"error": str(e)}
                }).execute()
        except:
            pass  # 실패 기록도 실패하면 무시
        
        raise RuntimeError(f"팟캐스트 생성 중 오류 발생: {str(e)}") from e
    
    finally:
        # === 10. 임시 디렉토리 정리 ===
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"임시 디렉토리 삭제 완료: {temp_dir}")
            except Exception as e:
                logger.warning(f"임시 디렉토리 삭제 실패 (무시): {e}")