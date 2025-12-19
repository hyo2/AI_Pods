# backend/app/routers/output.py
import os
import tempfile
import time
from fastapi import APIRouter, Form, BackgroundTasks, HTTPException
import json
import requests
from datetime import datetime, timedelta
from app.services.supabase_service import supabase, upload_bytes, BUCKET
from app.services.langgraph_service import run_langgraph

router = APIRouter(prefix="/outputs", tags=["outputs"])

google_project_id = os.getenv("VERTEX_AI_PROJECT_ID")
google_region = os.getenv("VERTEX_AI_REGION")
google_sa_file = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE")

# Supabase 쿼리 retry + output 존재 여부 체크
def supabase_retry(fn, desc: str, max_retries: int = 3, delay: float = 0.2):
    """
    Supabase 쿼리용 retry 래퍼.
    일시적인 네트워크/프로토콜 오류에 대해 재시도.
    """
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            print(f"[Supabase Retry] {desc} {attempt}/{max_retries} 실패: {e}")
            if attempt < max_retries:
                time.sleep(delay)
    # 그래도 안 되면 마지막 에러 다시 던지기
    raise last_err

# output_id에 해당하는 output_contents가 있는지 확인
def output_exists(output_id: int) -> bool:
    """
    output_contents에 해당 output_id가 아직 존재하는지 확인.
    - 사용자가 생성 도중 삭제했을 때 FK 에러 방지용
    """
    try:
        res = supabase.table("output_contents") \
            .select("id") \
            .eq("id", output_id) \
            .execute()
        return bool(res.data)
    except Exception as e:
        print(f"[output_exists] 확인 실패 (output_id={output_id}):", e)
        return False

# output 삭제 - 내부용
def delete_output_internal(output_id: int):
    try:
        res = supabase.table("output_contents") \
            .select("audio_path, script_path") \
            .eq("id", output_id).execute()

        content_rows = res.data or []
        if content_rows:
            audio_path = content_rows[0].get("audio_path")
            script_path = content_rows[0].get("script_path")
        else:
            audio_path = None
            script_path = None

        imgs = supabase.table("output_images") \
            .select("img_path") \
            .eq("output_id", output_id).execute()

        img_rows = imgs.data or []
        img_paths = [row["img_path"] for row in img_rows]

        storage = supabase.storage.from_(BUCKET)

        if audio_path:
            storage.remove([audio_path])
        if script_path:
            storage.remove([script_path])
        for p in img_paths:
            storage.remove([p])

        supabase.table("output_images").delete().eq("output_id", output_id).execute()
        supabase.table("output_contents").delete().eq("id", output_id).execute()

        print(f"[delete_output_internal] output_id={output_id} 삭제 완료")

    except Exception as e:
        print("[delete_output_internal Error]", e)

# 타임스탬프 파싱 -> 초로 바꾸기
def to_seconds(time_str):
    if time_str is None:
        return None
    if isinstance(time_str, (int, float)):
        return float(time_str)

    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h = 0
        m, s = parts
    else:
        return float(time_str)

    return int(h) * 3600 + int(m) * 60 + float(s)

# output 목록 조회 라우터
@router.get("/list")
def get_outputs(project_id: int):
    try:

        # 일시적 네트워크/프로토콜 오류 대비를 위해 retry함수로 감싸기
        res = supabase_retry(
            lambda: supabase.table("output_contents")
            .select("id, title, created_at, audio_path, script_path, status")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .execute(),
            desc=f"output 목록 조회 (project_id={project_id})",
        )

        return {"outputs": res.data or []}

    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="출력 목록 불러오기 실패")

# output_id에 대한 output 상세
@router.get("/{output_id}")
def get_output_detail(output_id: int):
    content_res = supabase.table("output_contents") \
        .select("*") \
        .eq("id", output_id) \
        .single() \
        .execute()

    if content_res.data is None:
        raise HTTPException(status_code=404, detail="Output not found")

    images_res = supabase.table("output_images") \
        .select("*") \
        .eq("output_id", output_id) \
        .order("img_index", desc=False) \
        .execute()

    return {
        "output": content_res.data,
        "images": images_res.data
    }

# output_id인 output 상태 조회
@router.get("/{output_id}/status")
def get_output_status(output_id: int):
    res = supabase.table("output_contents") \
        .select("status, error_message") \
        .eq("id", output_id) \
        .execute()
    
    if not res.data or len(res.data) == 0:
        raise HTTPException(status_code=404, detail="Output not found")
    
    return res.data[0]

# output 삭제 라우터
@router.delete("/{output_id}")
def delete_output(output_id: int):
    try:
        delete_output_internal(output_id)
        return {"message": "삭제 완료", "deleted_id": output_id}
    except Exception as e:
        print("[output 삭제 오류]", e)
        raise HTTPException(status_code=500, detail="output 삭제 실패")

# output 생성 라우터
@router.post("/generate")
async def generate_output(
    background_tasks: BackgroundTasks,

    project_id: int = Form(...),
    title: str = Form("새 팟캐스트"),
    input_content_ids: str = Form("[]"),
    main_input_id: int = Form(...),

    host1: str = Form(...),
    host2: str = Form(""), # 비어있는 채로 감. <- ✨ 없애는 방향으로 수정하기

    # 선택값 – 없으면 기본값 사용
    style: str = Form("lecture"),     # lecture | dialogue
    duration: int = Form(5),           # 5 | 10 | 15
    user_prompt: str = Form(""),
):
    try:
        input_ids = json.loads(input_content_ids)

        # output row 생성
        out_res = supabase.table("output_contents").insert({
            "project_id": project_id,
            "title": title,
            "input_content_ids": input_ids,
            "options": {
                "host1": host1,
                "style": style,
                "duration": duration,
                "user_prompt": user_prompt,
                "main_input_id": main_input_id,  # ✅ 주 강의 자료 id
            },
            "status": "processing",
        }).execute()

        output_id = out_res.data[0]["id"]

        background_tasks.add_task(
            process_langgraph_output,
            project_id=project_id,
            output_id=output_id,
            input_ids=input_ids,
            main_input_id=main_input_id,  # ✅ 주 강의 자료 id
            host1=host1,
            host2=host2,
            style=style,
            duration=duration,
            user_prompt=user_prompt,
            user_id=out_res.data[0]["project_id"],
        )

        return {
            "output_id": output_id,
            "status": "processing",
        }

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="출력 생성 요청 실패")
    

# LangGraph 백그라운드 실행 및 결과 저장
async def process_langgraph_output(
    project_id,
    output_id,
    input_ids,
    main_input_id,  # ✅ 주 강의자료
    host1,
    host2,
    style,
    duration,
    user_prompt,
    user_id,
):
    """
    Storage에서 파일을 직접 다운로드하여 로컬 임시 파일로 저장 후 처리
    """
    temp_files = []  # 임시 파일 목록 (나중에 삭제하기 위함)
    
    try:
        print(f"LangGraph 처리 시작 (Output ID: {output_id})")
        print(f"주 소스 ID: {main_input_id}")  # ✅ 로그 추가

        # 생성 직후 삭제된 경우를 초반에 한 번 체크
        if not output_exists(output_id):
            print(f"[process_langgraph_output] 시작 시점에 output_id={output_id}가 이미 없음. 작업 중단.")
            return

        # 1) input_contents -> 실제 파일 소스 준비 (Storage에서 다운로드)
        rows = (
            supabase.table("input_contents")
            .select("id, is_link, storage_path, link_url, is_main")
            .in_("id", input_ids)
            .execute()
        )

        if not rows.data:
            raise Exception("input_contents 조회 실패")

        main_sources = []
        aux_sources = []
        
        for r in rows.data:
            source_path = None

            if r["is_link"]:
                # 링크는 그대로 사용
                source_path = r["link_url"]
                print(f"link URL: {r['link_url'][:80]}...")
            else:
                storage_path = r["storage_path"]
                print(f"Storage path: {storage_path}")
                
                try:
                    # Storage에서 직접 다운로드                    
                    file_data = supabase.storage.from_(BUCKET).download(storage_path)
                    
                    print(f"다운로드 완료: {len(file_data):,} bytes")
                    
                    # 임시 파일로 저장
                    file_ext = os.path.splitext(storage_path)[1]
                    
                    # 임시 파일 생성 (자동으로 유니크한 이름 설정)
                    temp_fd, temp_path = tempfile.mkstemp(suffix=file_ext, prefix=f"input_{r['id']}_")
                    
                    # 파일 디스크립터로 쓰기
                    with os.fdopen(temp_fd, 'wb') as f:
                        f.write(file_data)
                    
                    temp_files.append(temp_path)
                    source_path = temp_path
                    
                    print(f"임시 파일: {temp_path}")
                    print(f"크기: {len(file_data):,} bytes")

                except Exception as download_error:
                    print(f"Storage 다운로드 실패: {download_error}")
                    import traceback
                    traceback.print_exc()
                    raise Exception(f"Storage 접근 실패 ({storage_path}): {str(download_error)}")

            # ✅ main_input_id와 비교하여 주 소스/보조 소스 분류
            if r["id"] == main_input_id:
                main_sources.append(source_path)
                print(f"✅ 주 소스로 추가: {source_path}")
            else:
                aux_sources.append(source_path)
                print(f"📎 보조 소스로 추가: {source_path}")

        if not main_sources:
            raise Exception(f"주 소스(main_input_id={main_input_id})를 찾을 수 없습니다.")
                
        print(f"\n주 소스 : {len(main_sources)}개, 보조 소스 : {len(aux_sources)}개 소스 준비 완료")
        print(f"{'='*80}\n")

        """
        LangGraph 결과를 받아서
        - Storage에 업로드
        - output_contents / output_images 업데이트
        - input_contents 만료일 업데이트 수행
        """
        # 2) LangGraph 실행
        result = await run_langgraph(
            main_sources=main_sources,
            aux_sources=aux_sources,
            project_id=google_project_id,
            region=google_region,
            sa_file=google_sa_file,
            host1=host1,
            host2=host2,
            style=style,
            duration=duration,
            user_prompt=user_prompt,
            output_id=output_id,
        )

        print("\n✅ LangGraph 실행 완료")

        # 결과 추출
        audio_local = result["final_podcast_path"]
        script_local = result["transcript_path"]

        title_text = result.get("title") or "새 팟캐스트"

        print(f"Title: {title_text}")

        # 3) output이 여전히 존재하는지 재확인
        #    사용자가 생성 도중 삭제한 경우 이후 작업 스킵
        if not output_exists(output_id):
            print(f"[LangGraph] Output 결과 저장 직전에 output_id={output_id}가 삭제됨. 파일 업로드/DB 업데이트 스킵.")
            return

        # 4) Storage 업로드 (오디오, 스크립트, 이미지)        
        base_audio_name = os.path.basename(audio_local)
        base_script_name = os.path.basename(script_local)

        with open(audio_local, "rb") as f:
            audio_url = upload_bytes(
                f.read(),
                folder=f"user/{user_id}/project/{project_id}/outputs",
                filename=base_audio_name,
                content_type="audio/mpeg"
            )

        with open(script_local, "rb") as f:
            script_url = upload_bytes(
                f.read(),
                folder=f"user/{user_id}/project/{project_id}/outputs",
                filename=base_script_name,
                content_type="text/plain"
            )

        print(f"Storage에 Output 파일 업로드 완료")

        # 5) DB 업데이트: output_contents

        # 존재 여부 재확인 후에만 업데이트
        if not output_exists(output_id):
            print(f"[LangGraph] Output 업로드 후 output_id={output_id}가 삭제됨 -> 업로드 파일 제거/DB 업데이트 스킵")
            storage = supabase.storage.from_(BUCKET)

            # 오디오 삭제
            try:
                if audio_url:
                    storage.remove([audio_url])
            except:
                pass

            # 스크립트 삭제
            try:
                if script_url:
                    storage.remove([script_url])
            except:
                pass

            return
        
        # 🔽 타임스탬프 포함 transcript 파일 읽기
        try:
            with open(script_local, "r", encoding="utf-8") as f:
                transcript_text = f.read()
        except Exception as e:
            print("Transcript 파일 읽기 실패:", e)
            transcript_text = result.get("script", "")

        # DB 업데이트 : output_contents 
        supabase.table("output_contents").update({
            "title": title_text,
            "status": "completed",
            "audio_path": audio_url,
            "script_path": script_url,
            "script_text": transcript_text,  # 🔥 타임스탬프 포함
        }).eq("id", output_id).execute()

        # 7) 프로젝트 이름 업데이트
        project_row = supabase.table("projects").select("title").eq("id", project_id).single().execute()

        if project_row.data and project_row.data["title"] in ["새 프로젝트", "", None]:
            supabase.table("projects").update({
                "title": f"{title_text} 프로젝트"
            }).eq("id", project_id).execute()

        # 8) input_contents 만료일 업데이트
        now = datetime.utcnow()
        supabase.table("input_contents").update({
            "last_used_at": now.isoformat(),
            "expires_at": (now + timedelta(days=180)).isoformat()
        }).in_("id", input_ids).execute()

        print(f"\n처리 완료(completed)\n{'='*80}\n")

    except Exception as e:
        error_msg = str(e)
        print(f"\n오류 발생(failed): {error_msg}\n")
        
        import traceback
        traceback.print_exc()
        
        try:
            # output이 이미 삭제됐다면 여기서 update는 실패할 수 있지만, 그 경우는 그냥 로그만 찍힘
            supabase.table("output_contents").update({
                "status": "failed",
                "error_message": error_msg[:500],
                "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat()
            }).eq("id", output_id).execute()

        except Exception as update_err:
            print(f"상태 업데이트 실패: {update_err}")
    
    finally:
        # 임시 파일 정리
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    print(f"임시 파일 삭제됨: {temp_file}")
            except Exception as cleanup_error:
                print(f"임시 파일 삭제 실패: {temp_file} - {cleanup_error}")
        print(f"임시 파일 정리 완료")