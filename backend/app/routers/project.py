from fastapi import APIRouter, HTTPException
from app.services.supabase_service import supabase, delete_project_folder
from datetime import datetime

router = APIRouter(prefix="/projects", tags=["projects"])

# 프로젝트 목록 조회
@router.get("/")
def list_projects(user_id: str):
    res = supabase.table("projects") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .execute()

    return res.data

# 새 프로젝트 생성
@router.post("/create")
def create_project(payload: dict):
    user_id = payload["user_id"]
    # title = payload.get("title")
    title = payload.get("title", "새 프로젝트") # default title 지정
    description = payload.get("description", "")

    res = supabase.table("projects").insert({
        "user_id": user_id,
        "title": title,
        "description": description,
    }).execute()

    return {"project": res.data[0]}


# 프로젝트 전체 삭제 - 폴더, 파일 포함
@router.delete("/{project_id}")
def delete_project(project_id: int, user_id: str):
    """
    프로젝트 전체 삭제:
    1. 프로젝트 소유자 확인
    2. output_images 삭제
    3. output_contents 삭제
    4. input_contents 삭제
    5. projects 삭제
    6. Supabase Storage의 프로젝트 폴더 삭제
    """

    # 프로젝트 존재 여부, 소유자 확인
    proj = (
        supabase.table("projects")
        .select("*")
        .eq("id", project_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not proj.data:
        raise HTTPException(404, "Project not found")

    # project의 모든 output_id 조회
    outputs = (
        supabase.table("output_contents")
        .select("id")
        .eq("project_id", project_id)
        .execute()
    )

    output_ids = [row["id"] for row in outputs.data] if outputs.data else []

    # output_images 삭제
    if output_ids:
        supabase.table("output_images") \
            .delete() \
            .in_("output_id", output_ids) \
            .execute()

    # output_contents 삭제
    supabase.table("output_contents") \
        .delete() \
        .eq("project_id", project_id) \
        .execute()

    # input_contents 삭제
    supabase.table("input_contents") \
        .delete() \
        .eq("project_id", project_id) \
        .execute()

    # projects 삭제
    supabase.table("projects") \
        .delete() \
        .eq("id", project_id) \
        .execute()

    # Supabase Storage에서 파일 삭제
    delete_project_folder(user_id, project_id)

    return {
        "message": "project deleted completely",
        "project_id": project_id,
        "deleted_outputs": output_ids,
    }




