# backend/app/routers/output.py
import json
from fastapi import APIRouter, Form, BackgroundTasks, HTTPException
from app.services.supabase_service import supabase
from app.services.output_service import delete_output_internal, process_langgraph_output
from app.utils.output_helpers import supabase_retry

router = APIRouter(prefix="/outputs", tags=["outputs"])


@router.get("/list")
def get_outputs(project_id: int):
    """output 목록 조회"""
    try:
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


@router.get("/{output_id}")
def get_output_detail(output_id: int):
    """output_id에 대한 output 상세"""
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


@router.get("/{output_id}/status")
def get_output_status(output_id: int):
    """output_id인 output 상태 조회"""
    res = supabase.table("output_contents") \
        .select("status, error_message, current_step") \
        .eq("id", output_id) \
        .execute()
    
    if not res.data or len(res.data) == 0:
        raise HTTPException(status_code=404, detail="Output not found")
    
    return res.data[0]


@router.delete("/{output_id}")
def delete_output(output_id: int):
    """output 삭제"""
    try:
        delete_output_internal(output_id)
        return {"message": "삭제 완료", "deleted_id": output_id}
    except Exception as e:
        print("[output 삭제 오류]", e)
        raise HTTPException(status_code=500, detail="output 삭제 실패")


@router.post("/generate")
async def generate_output(
    background_tasks: BackgroundTasks,
    project_id: int = Form(...),
    title: str = Form("자동 생성된 팟캐스트"),
    input_content_ids: str = Form("[]"),
    main_input_id: int = Form(...),
    host1: str = Form(...),
    host2: str = Form(""),
    style: str = Form("lecture"),
    duration: int = Form(5),
    user_prompt: str = Form(""),
):
    """output 생성"""
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
                "main_input_id": main_input_id,
            },
            "status": "processing",
            "current_step": "start"  # 초기 step
        }).execute()

        output_id = out_res.data[0]["id"]

        background_tasks.add_task(
            process_langgraph_output,
            project_id=project_id,
            output_id=output_id,
            input_ids=input_ids,
            main_input_id=main_input_id,
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
            "current_step": "start"  # 초기 step 반환
        }

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="출력 생성 요청 실패")