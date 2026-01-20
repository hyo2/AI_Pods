# backend/app/services/output_service.py
import os
import tempfile
from datetime import datetime, timedelta
from app.services.supabase_service import supabase, upload_bytes, BUCKET
from app.services.langgraph_service import run_langgraph, CancelledException
from app.utils.output_helpers import output_exists

# 모듈 레벨 변수 제거 - 함수 실행 시점에 읽도록 변경

def update_output_step(output_id: int, current_step: str):
    """output의 현재 진행 단계 업데이트"""
    try:
        supabase.table("output_contents").update({
            "current_step": current_step
        }).eq("id", output_id).execute()
        print(f"[Step Updated] output_id={output_id}, step={current_step}")
    except Exception as e:
        print(f"[Step Update Error] {e}")


def delete_output_internal(output_id: int):
    """output 삭제 - 내부용"""
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

def strip_nul(obj):
    if isinstance(obj, str):
        return obj.replace("\x00", "")
    if isinstance(obj, list):
        return [strip_nul(x) for x in obj]
    if isinstance(obj, dict):
        return {k: strip_nul(v) for k, v in obj.items()}
    return obj

async def process_langgraph_output(
    project_id,
    output_id,
    input_ids,
    main_input_id,
    host1,
    host2,
    style,
    duration,
    difficulty,
    user_prompt,
    user_id,
):
    """
    Storage에서 파일을 직접 다운로드하여 로컬 임시 파일로 저장 후 처리
    """
    # 함수 시작 시점에 환경 변수 읽기 (모듈 로드 시점이 아닌!)
    google_project_id = os.getenv("VERTEX_AI_PROJECT_ID")
    google_region = os.getenv("VERTEX_AI_REGION")
    google_sa_file = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE")
    
    if not google_sa_file:
        raise RuntimeError(
            "❌ VERTEX_AI_SERVICE_ACCOUNT_FILE 환경 변수가 설정되지 않았습니다!\n"
            "vertex_env_patch.py가 실행되었는지 확인하세요."
        )
    
    if not google_project_id or not google_region:
        raise RuntimeError(
            "❌ VERTEX_AI_PROJECT_ID 또는 VERTEX_AI_REGION 환경 변수가 설정되지 않았습니다!"
        )
    
    temp_files = []
    
    try:
        print(f"LangGraph 처리 시작 (Output ID: {output_id})")
        print(f"주 소스 ID: {main_input_id}")
        print(f"Vertex AI Config: project={google_project_id}, region={google_region}, sa_file={google_sa_file}")

        update_output_step(output_id, "start")

        if not output_exists(output_id):
            print(f"[process_langgraph_output] 시작 시점에 output_id={output_id}가 이미 없음. 작업 중단.")
            return

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
                source_path = r["link_url"]
                print(f"link URL: {r['link_url'][:80]}...")
            else:
                storage_path = r["storage_path"]
                print(f"Storage path: {storage_path}")
                
                try:
                    file_data = supabase.storage.from_(BUCKET).download(storage_path)
                    print(f"다운로드 완료: {len(file_data):,} bytes")
                    
                    file_ext = os.path.splitext(storage_path)[1]
                    temp_fd, temp_path = tempfile.mkstemp(suffix=file_ext, prefix=f"input_{r['id']}_")
                    
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

            if r["id"] == main_input_id:
                main_sources.append(source_path)
                print(f"✅ 주 소스로 추가: {source_path}")
            else:
                aux_sources.append(source_path)
                print(f"🔎 보조 소스로 추가: {source_path}")

        if not main_sources:
            raise Exception(f"주 소스(main_input_id={main_input_id})를 찾을 수 없습니다.")
                
        print(f"\n주 소스: {len(main_sources)}개, 보조 소스: {len(aux_sources)}개 소스 준비 완료")
        print(f"{'='*80}\n")

        def step_callback(step: str):
            if output_exists(output_id):
                update_output_step(output_id, step)

        try:
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
                difficulty=difficulty,
                user_prompt=user_prompt,
                output_id=output_id,
                step_callback=step_callback
            )
        except CancelledException as ce:
            print(f"✅ 사용자가 output {output_id}를 취소함: {ce}")
            return

        print("\n✅ LangGraph 실행 완료")

        audio_local = result["final_podcast_path"]
        script_local = result["transcript_path"]
        title_text = result.get("title") or "자동 생성된 팟캐스트"

        print(f"Title: {title_text}")

        if not output_exists(output_id):
            print(f"[LangGraph] Output 결과 저장 직전에 output_id={output_id}가 삭제됨. 파일 업로드/DB 업데이트 스킵.")
            return

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

        if not output_exists(output_id):
            print(f"[LangGraph] Output 업로드 후 output_id={output_id}가 삭제됨 -> 업로드 파일 제거/DB 업데이트 스킵")
            storage = supabase.storage.from_(BUCKET)

            try:
                if audio_url:
                    storage.remove([audio_url])
            except:
                pass

            try:
                if script_url:
                    storage.remove([script_url])
            except:
                pass

            return
        
        try:
            with open(script_local, "r", encoding="utf-8") as f:
                transcript_text = f.read()
        except Exception as e:
            print("Transcript 파일 읽기 실패:", e)
            transcript_text = result.get("script", "")

        # 사용자 input 데이터에 대한 metadata
        source_data = result["source_data"]

        payload = {
            "title": title_text,
            "status": "completed",
            "audio_path": audio_url,
            "script_path": script_url,
            "script_text": transcript_text,
            "current_step": "completed",
            "metadata": source_data
        }

        payload = strip_nul(payload)

        supabase.table("output_contents").update(payload).eq("id", output_id).execute()

        project_row = supabase.table("projects").select("title").eq("id", project_id).single().execute()

        if project_row.data and project_row.data["title"] in ["새 프로젝트", "", None]:
            supabase.table("projects").update({
                "title": f"{title_text} 프로젝트"
            }).eq("id", project_id).execute()

        now = datetime.utcnow()
        supabase.table("input_contents").update({
            "last_used_at": now.isoformat(),
            "expires_at": (now + timedelta(days=180)).isoformat()
        }).in_("id", input_ids).execute()

        print(f"\n처리 완료(completed)\n{'='*80}\n")

    except CancelledException:
        print(f"✅ Output {output_id} 취소됨 - 정상 종료")
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n오류 발생(failed): {error_msg}\n")
        
        import traceback
        traceback.print_exc()
        
        if output_exists(output_id):
            try:
                error_payload = {
                    "status": "failed",
                    "error_message": error_msg[:500],
                    "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                    "current_step": "error"
                }

                error_payload = strip_nul(error_payload)

                supabase.table("output_contents").update(error_payload).eq("id", output_id).execute()

            except Exception as update_err:
                print(f"상태 업데이트 실패: {update_err}")
        else:
            print(f"⚠️ Output {output_id}가 이미 삭제되어 오류 상태 업데이트 스킵")
    
    finally:
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    print(f"임시 파일 삭제됨: {temp_file}")
            except Exception as cleanup_error:
                print(f"임시 파일 삭제 실패: {temp_file} - {cleanup_error}")
        print(f"임시 파일 정리 완료")