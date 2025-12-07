# backend/app/routers/output.py
import os
from fastapi import APIRouter, Form, BackgroundTasks, HTTPException
import json
import requests
from datetime import datetime, timedelta
from app.services.supabase_service import supabase, SUPABASE_URL, SUPABASE_SERVICE_KEY, upload_bytes, normalize_supabase_response, BUCKET
from app.services.langgraph_service import run_langgraph

router = APIRouter(prefix="/outputs", tags=["outputs"])

google_project_id = os.getenv("VERTEX_AI_PROJECT_ID")
google_region = os.getenv("VERTEX_AI_REGION")
google_sa_file = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE")

# output 삭제 - 내부용
def delete_output_internal(output_id: int):
    # output_contents + output_images + 관련 storage 파일 전체 삭제
    try:
        # 1) output_contents 조회 (audio/script 경로 확보)
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

        # 2) output_images 조회 (이미지 경로 확보)
        imgs = supabase.table("output_images") \
            .select("img_path") \
            .eq("output_id", output_id).execute()

        img_rows = imgs.data or []
        img_paths = [row["img_path"] for row in img_rows]

        # 3) Storage 파일 삭제
        storage = supabase.storage.from_(BUCKET)

        # 오디오 삭제
        if audio_path:
            storage.remove([audio_path])

        # 스크립트 삭제
        if script_path:
            storage.remove([script_path])

        # 이미지 삭제
        for p in img_paths:
            storage.remove([p])

        # 4) DB 삭제
        supabase.table("output_images").delete().eq("output_id", output_id).execute()
        supabase.table("output_contents").delete().eq("id", output_id).execute()

        print(f"[delete_output_internal] output_id={output_id} 삭제 완료")

    except Exception as e:
        print("[delete_output_internal Error]", e)


# 타임스탬프 문자열을 초(float)로 변환
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

# 프로젝트 output 목록 조회
@router.get("/list")
def get_outputs(project_id: int):
    try:
        res = supabase.table("output_contents") \
            .select("id, title, created_at, audio_path, script_path, status") \
            .eq("project_id", project_id) \
            .order("created_at", desc=True) \
            .execute()

        return {"outputs": res.data or []}

    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="출력 목록 불러오기 실패")

# output 상세 조회
@router.get("/{output_id}")
def get_output_detail(output_id: int):
    # output_contents 가져오기
    content_res = supabase.table("output_contents") \
        .select("*") \
        .eq("id", output_id) \
        .single() \
        .execute()

    if content_res.data is None:
        raise HTTPException(status_code=404, detail="Output not found")

    # output_images 가져오기
    images_res = supabase.table("output_images") \
        .select("*") \
        .eq("output_id", output_id) \
        .order("img_index", desc=False) \
        .execute()

    return {
        "output": content_res.data,
        "images": images_res.data
    }

# output 상태 조회 - 프론트에서 polling 용도
@router.get("/{output_id}/status")
def get_output_status(output_id: int):
    res = supabase.table("output_contents") \
        .select("status") \
        .eq("id", output_id) \
        .single() \
        .execute()

    if res.data is None:
        raise HTTPException(status_code=404, detail="Output not found")

    return res.data

# output 삭제
@router.delete("/{output_id}")
def delete_output(output_id: int):
    try:
        delete_output_internal(output_id)
        return {"message": "삭제 완료", "deleted_id": output_id}
    except Exception as e:
        print("[output 삭제 오류]", e)
        raise HTTPException(status_code=500, detail="output 삭제 실패")


# generate: output 생성 요청 -> output_contents row 생성 + 비동기 LangGraph 실행
@router.post("/generate")
async def generate_output(
    background_tasks: BackgroundTasks,
    project_id: int = Form(...),
    title: str = Form("새 팟캐스트"),
    input_content_ids: str = Form("[]"),
    host1: str = Form(""),
    host2: str = Form(""),
    style: str = Form("default"),
):
    try:
        # title이 빈 문자열("")일 때 기본값 설정
        title = (title or "새 팟캐스트").strip()

        input_ids = json.loads(input_content_ids)

        # project_id로 user_id 가져오기
        proj_res = supabase.table("projects").select("user_id").eq("id", project_id).single().execute()
        user_id = proj_res.data["user_id"]

        # output_contents row 생성
        out_res = supabase.table("output_contents").insert({
            "project_id": project_id,
            "title": title,
            "input_content_ids": input_ids,
            "options": {
                "host1": host1,
                "host2": host2,
                "style": style
            },
            "status": "processing", # default status : processing(생성 중)
        }).execute()

        output_id = out_res.data[0]["id"]

        # Background로 LangGraph 실행
        background_tasks.add_task(
            process_langgraph_output,
            project_id=project_id,
            output_id=output_id,
            input_ids=input_ids,
            host1=host1,
            host2=host2,
            style=style,
            user_id=user_id
        )

        return {
            "output_id": output_id,
            "status": "processing"
        }

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="출력 생성 요청 실패")

# 백그라운드에서 LangGraph 실행 -> output_contents, output_images 업데이트
async def process_langgraph_output(project_id, output_id, input_ids, host1, host2, style, user_id):
    # 파라미터는 db project id가 넘어온 거임
    """
    LangGraph 결과를 받아 Supabase에 업로드 및 DB 저장을 수행하는 함수
    """
    try:
        
        # input_ids기반으로 실제 Storage URL 또는 link_url 있는지 조회
        rows = (
            supabase.table("input_contents")
            .select("id, is_link, storage_path, link_url")
            .in_("id", input_ids)
            .execute()
        )

        # input_ids -> sources 변환
        sources = []
        for r in rows.data:
            if r["is_link"]:
                sources.append(r["link_url"])
            else:
                # storage_path = "user/.../file.pdf"
                storage_path = r["storage_path"]

                # signed URL 생성 (1시간 유효)
                signed = supabase.storage.from_("project_resources").create_signed_url(
                    storage_path, 60 * 60
                )

                if "signedURL" not in signed:
                    raise Exception(f"Signed URL 생성 실패: {storage_path}")

                sources.append(signed["signedURL"])

        if not rows.data:
            raise Exception("input_contents 조회 실패")

        # 1) LangGraph 실행
        result = await run_langgraph(
            sources=sources,
            project_id=google_project_id,
            region=google_region,
            sa_file=google_sa_file,
            host1=host1,
            host2=host2,
            style=style
        )

        print("langgraph 호출 후")

        # =====================================================
        # 2) 결과 상태 추출
        # =====================================================
        audio_local = result["final_podcast_path"]
        script_local = result["transcript_path"]
        image_local_paths = result["image_paths"]          # dict: { "img_001": "localpath" }
        image_plans = result["image_plans"]                # list[ImagePlan]
        timeline = result["timeline"]                      # list[{image_id, start, end}]
        metadata = result["metadata"]                      # PodcastMetadata

        # image_index 부여
        for idx, plan in enumerate(image_plans, start=1):
            setattr(plan, "image_index", idx)

        # title, summary 추출
        summary_text = metadata.content.detailed_summary if hasattr(metadata, "content") else ""
        title_text = (
            getattr(metadata.content, "title", None)
            or (image_plans[0].title if image_plans else "새 팟캐스트")
        )

        # =====================================================
        # 3) Storage 업로드
        # =====================================================

        # 오디오, 스크립트 파일명만 추출
        base_audio_name = os.path.basename(audio_local)
        base_script_name = os.path.basename(script_local)      

        # 오디오 업로드
        with open(audio_local, "rb") as f:
            audio_url = upload_bytes(
                f.read(),
                folder=f"user/{user_id}/project/{project_id}/outputs",
                filename=base_audio_name,
                content_type="audio/mpeg"
            )

        # 스크립트 업로드
        with open(script_local, "rb") as f:
            script_url = upload_bytes(
                f.read(),
                folder=f"user/{user_id}/project/{project_id}/outputs",
                filename=base_script_name,
                content_type="text/plain"
            )

        # 이미지 업로드
        uploaded_images = []
        for image_id, local_path in image_local_paths.items():
            with open(local_path, "rb") as f:
                url = upload_bytes(
                    f.read(),
                    folder=f"user/{user_id}/project/{project_id}/outputs/images",
                    filename=f"{output_id}_{image_id}.png",
                    content_type="image/png"
                )
            uploaded_images.append((image_id, url))

        # =====================================================
        # 4) output_contents 업데이트
        # =====================================================
        supabase.table("output_contents").update({
            "title": title_text,
            "summary": summary_text,
            "status": "completed",
            "audio_path": audio_url,
            "script_path": script_url,
            "script_text": result.get("script_text", ""),
            "metadata": {
                "image_count": len(image_local_paths)
            }
        }).eq("id", output_id).execute()

        # =====================================================
        # 5) output_images 테이블 저장
        # =====================================================
        # timeline 기반 매핑 생성
        uploaded_dict = dict(uploaded_images)   # { "img_002": "url", ... }

        timeline_map = {t.image_id: t for t in timeline}

        for plan in image_plans:
            image_id = plan.image_id

            # 1) 실제 생성된 이미지인지 체크
            if image_id not in uploaded_dict:
                print(f"[Skip] 이미지 '{image_id}'는 생성되지 않아 저장하지 않습니다.")
                continue

            # 2) timeline에도 존재하는지 체크
            if image_id not in timeline_map:
                print(f"[Skip] 이미지 '{image_id}'에 대한 timeline 없음")
                continue

            t = timeline_map[image_id]

            supabase.table("output_images").insert({
                "output_id": output_id,
                "img_index": getattr(plan, "image_index", 0),
                "img_path": uploaded_dict[image_id],   # 안전하게 접근
                "img_description": plan.description,
                "start_time": to_seconds(getattr(t, "start", getattr(t, "timestamp", None))),
                "end_time": to_seconds(getattr(t, "end", getattr(t, "end_timestamp", None))),
            }).execute()

        # =====================================================
        # 6) 프로젝트 이름 자동 업데이트
        # =====================================================
        project_row = supabase.table("projects").select("title").eq("id", project_id).single().execute()

        if project_row.data and project_row.data["title"] in ["새 프로젝트", "", None]:
            supabase.table("projects").update({
                "title": f"{title_text} 프로젝트"
            }).eq("id", project_id).execute()

        # =====================================================
        # 7) input_contents → last_used_at 업데이트
        # =====================================================
        now = datetime.utcnow()
        supabase.table("input_contents").update({
            "last_used_at": now.isoformat(),
            "expires_at": (now + timedelta(days=180)).isoformat()
        }).in_("id", input_ids).execute()

    except Exception as e:
        print("[LangGraph Error]", e)
        delete_output_internal(output_id)
        return
