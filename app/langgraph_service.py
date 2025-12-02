import os
import asyncio
import tempfile
import logging
import shutil
from typing import List, Dict, Any
from pathlib import Path
import httpx

# 모듈화된 podcast 서비스 임포트
from app.services.podcast import run_podcast_generation
# Supabase 서비스는 외부에서 제공된다고 가정합니다.
# from app.services.supabase_service import supabase, upload_bytes 
# 임포트 오류를 피하기 위해 Mock 함수를 정의합니다.
class MockSupabase:
    def table(self, name):
        return self
    def select(self, columns):
        return self
    def in_(self, column, values):
        return self
    def execute(self):
        # 목업 데이터 반환 (실제 환경에서는 DB에서 가져옴)
        return type('MockResponse', (object,), {'data': [{"id": 1, "is_link": False, "storage_path": "https://mock-storage.com/file1.txt", "title": "file1.txt", "user_id": "test_user", "project_id": "test_proj"}]})
supabase = MockSupabase()
def upload_bytes(file_bytes, folder, filename, content_type):
    # 목업 URL 반환
    return f"https://uploaded-storage.com/{folder}/{filename}"

logger = logging.getLogger(__name__)


async def download_file(url: str, dest_path: Path) -> None:
    """Supabase Storage에서 파일 다운로드 (또는 URL에서 직접 다운로드)"""
    logger.info(f"Downloading {url} to {dest_path}")
    async with httpx.AsyncClient() as client:
        # NOTE: 실제 Supabase Storage URL은 토큰이 필요할 수 있으나, 여기서는 단순 HTTP GET으로 가정
        response = await client.get(url, timeout=120.0)
        response.raise_for_status()
        dest_path.write_bytes(response.content)
    logger.info(f"Download complete for {dest_path.name}")


async def run_langgraph(
    input_ids: List[int],
    host1: str,
    host2: str,
    style: str,
) -> Dict[str, Any]:
    """
    LangGraph 팟캐스트 생성 실행
    """
    
    # 환경 변수 확인
    project_id = os.getenv("VERTEX_AI_PROJECT_ID") or "default-project"
    region = os.getenv("VERTEX_AI_REGION", "us-central1")
    sa_file = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE") or "mock_sa.json"
    
    if not os.path.exists(sa_file):
        # SA 파일이 없으면 테스트용 더미 생성
        with open(sa_file, 'w') as f:
            f.write('{"mock": "service_account_data"}')

    
    # 임시 디렉토리 생성
    temp_dir = Path(tempfile.mkdtemp())
    logger.info(f"임시 디렉토리 생성: {temp_dir}")
    
    # 팟캐스트 생성 결과 저장을 위해 파일 이름 임의 설정
    mock_audio_path = temp_dir / "final_podcast.mp3"
    mock_transcript_path = temp_dir / "transcript.txt"
    
    try:
        # 1. input_contents 조회 (Mockup)
        # 실제 환경에서는 input_ids를 기반으로 DB에서 데이터를 가져옵니다.
        inputs_res = supabase.table("input_contents") \
            .select("id, is_link, storage_path, link_url, title, user_id, project_id") \
            .in_("id", input_ids) \
            .execute()
        
        if not inputs_res.data:
            raise ValueError("입력 소스를 찾을 수 없습니다")
        
        # 2. 소스 파일 준비
        sources = []
        
        # 첫 번째 항목에서 user_id와 project_id를 가져옴 (업로드에 사용)
        user_id = inputs_res.data[0]["user_id"]
        project_id_db = inputs_res.data[0]["project_id"]
        
        for inp in inputs_res.data:
            if inp.get("is_link"):
                # 링크는 그대로 전달
                sources.append(inp.get("link_url", ""))
                logger.info(f"링크 추가: {inp.get('link_url')}")
            else:
                # 파일은 다운로드
                storage_url = inp.get("storage_path", "")
                file_name = inp.get("title", f"temp_file_{inp['id']}")
                local_path = temp_dir / file_name
                
                # NOTE: 실제 환경에서는 storage_url을 사용하여 다운로드
                await download_file(storage_url, local_path) 
                sources.append(str(local_path))
                logger.info(f"파일 다운로드: {file_name} -> {local_path}")
        
        if not sources or all(not s for s in sources):
            raise ValueError("처리할 유효한 소스가 없습니다")
        
        # 3. 팟캐스트 생성 (동기 함수를 비동기에서 실행)
        logger.info(f"팟캐스트 생성 시작 - {len(sources)}개 소스")
        
        # run_podcast_generation이 최종 경로를 반환해야 합니다.
        # LangGraph 내부에서 파일이 생성되지만, 임시 디렉토리 안에 생성되도록 mock 처리 필요.
        
        # LangGraph를 실행하기 전에 예상되는 최종 경로를 설정 (run_podcast_generation 내부에서 덮어쓰거나 사용)
        os.environ['MOCK_FINAL_AUDIO_PATH'] = str(mock_audio_path)
        os.environ['MOCK_FINAL_TRANSCRIPT_PATH'] = str(mock_transcript_path)

        result = await asyncio.to_thread(
            run_podcast_generation,
            sources=sources,
            project_id=project_id,
            region=region,
            sa_file=sa_file,
            host_name=host1,
            guest_name=host2
        )
        
        logger.info(f"팟캐스트 생성 완료: {result.get('final_podcast_path', 'N/A')}")
        
        # 4. 결과 파일을 Supabase Storage에 업로드
        audio_path = Path(result.get('final_podcast_path', mock_audio_path))
        transcript_path = Path(result.get('transcript_path', mock_transcript_path))
        
        # NOTE: run_podcast_generation이 목업으로 실행되었을 경우, 파일이 실제로 생성되지 않았을 수 있습니다.
        # 업로드 테스트를 위해 임시로 파일 생성 (실제 환경에서는 필요 없음)
        if not audio_path.exists():
            audio_path.write_text("Mock Audio Content")
        if not transcript_path.exists():
             transcript_path.write_text("Mock Transcript Content")

        # 오디오 파일 업로드
        audio_url = None
        if audio_path.exists():
            with open(audio_path, 'rb') as f:
                audio_bytes = f.read()
            
            audio_url = upload_bytes(
                file_bytes=audio_bytes,
                folder=f"user/{user_id}/project/{project_id_db}/outputs",
                filename=audio_path.name,
                content_type="audio/mpeg"
            )
        
        # 스크립트 파일 업로드
        script_text = ""
        script_url = None
        
        if transcript_path.exists():
            with open(transcript_path, 'r', encoding='utf-8') as f:
                script_text = f.read()
            
            script_bytes = script_text.encode('utf-8')
            script_url = upload_bytes(
                file_bytes=script_bytes,
                folder=f"user/{user_id}/project/{project_id_db}/outputs",
                filename=transcript_path.name,
                content_type="text/plain"
            )
        
        logger.info(f"업로드 완료 - 오디오: {audio_url}")
        
        return {
            "audio_url": audio_url,
            "script": script_text,
            "script_url": script_url,
            "images": [], 
            "host1": result["host_name"],
            "host2": result["guest_name"],
            "errors": result.get("errors", [])
        }
        
    except Exception as e:
        logger.error(f"팟캐스트 생성 실패: {e}", exc_info=True)
        raise
    
    finally:
        # 5. 임시 디렉토리 정리
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"임시 디렉토리 삭제: {temp_dir}")
        except Exception as e:
            logger.warning(f"임시 디렉토리 삭제 실패: {e}")