# app/routers/input.py
from fastapi import APIRouter, UploadFile, Query, File, Form, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid, json
import requests
from app.services.supabase_service import create_signed_upload, supabase, upload_bytes, SUPABASE_URL, SUPABASE_SERVICE_KEY, normalize_supabase_response, BUCKET

import time
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inputs", tags=["inputs"])

# 업로드 url 생성 요청 모델
class CreateUploadUrlReq(BaseModel):
    user_id: str
    project_id: int
    filename: str
    content_type: str | None = None

# -----------------------------
# Register용 요청 모델
# -----------------------------
class RegisterFileItem(BaseModel):
    title: str  # 원본 파일명 (예: lecture.pdf)
    storage_path: str  # Supabase Storage path (예: user/.../inputs/uuid.pdf)
    file_type: Optional[str] = None  # MIME type (예: application/pdf)
    file_size: Optional[int] = None  # bytes


class RegisterInputsReq(BaseModel):
    user_id: str
    project_id: int

    # options (값이 있을 때만 저장)
    host1: Optional[str] = ""
    host2: Optional[str] = ""
    style: Optional[str] = ""

    # 링크/파일 메타
    links: List[str] = []
    files: List[RegisterFileItem] = []


# 프로젝트별 input 목록 조회
@router.get("/list")
def get_inputs(project_id: int = Query(...)):
    try:
        res = supabase.table("input_contents") \
            .select("id, title, created_at") \
            .eq("project_id", project_id) \
            .order("created_at", desc=False) \
            .execute()
        return {"inputs": res.data or []}

    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="input 목록 조회 실패")


# 프론트에서 바로 파일 업로드 용
@router.post("/create-upload-url")
def create_upload_url(body: CreateUploadUrlReq):
    ext = body.filename.split(".")[-1] if "." in body.filename else "bin"
    file_id = f"{uuid.uuid4()}.{ext}"
    folder = f"user/{body.user_id}/project/{body.project_id}/inputs"
    path = f"{folder}/{file_id}"

    data = create_signed_upload(BUCKET, path, expires_in=3600, upsert=False)

    token = data.get("token")
    signed_url = data.get("signedUrl") or data.get("signedURL") or data.get("signed_url")
    returned_path = data.get("path") or path

    return {
        "bucket": BUCKET,
        "path": returned_path,
        "token": token,
        "signed_url": signed_url,
        "content_type": body.content_type or "application/octet-stream",
        "original_filename": body.filename,
    }


# 프론트에서 바로 파일 업로드 용
@router.post("/register")
def register_inputs(body: RegisterInputsReq):
    """
    direct upload 이후, 프론트가 links + (storage_path 기반 files 메타)를 한 번에 등록하는 API

    - links[]: input_contents에 is_link=True로 저장
    - files[]: 이미 Supabase Storage에 업로드된 파일의 storage_path를 input_contents에 저장
    - 업로드(바이너리 전송)는 여기서 하지 않음 (프론트가 signed upload로 직접 업로드)
    """

    # ✅ project_id 유효성 체크 (FK 에러 사전 방지)
    proj = (
        supabase.table("projects")
        .select("id")
        .eq("id", body.project_id)
        .limit(1)
        .execute()
    )

    if not (proj.data and len(proj.data) > 0):
        # 400으로 내려서 프론트가 "세션 꼬임/새로고침" 안내할 수 있게
        raise HTTPException(
            status_code=400,
            detail=f"프로젝트 정보가 유효하지 않습니다. (project_id={body.project_id}) 새로고침 후 다시 시도해주세요."
        )

    # 일반 사용자 기준 input source 만료일 180일로 지정
    expires_at = datetime.utcnow() + timedelta(days=180)

    saved_inputs = []

    # options 딕셔너리 생성 (값이 있을 때만 포함)
    options: Dict[str, Any] = {}
    if body.host1:
        options["host1"] = body.host1
    if body.host2:
        options["host2"] = body.host2
    if body.style:
        options["style"] = body.style

    # 1) 링크 저장 (input_contents)
    for url in (body.links or []):
        res = supabase.table("input_contents").insert({
            "user_id": body.user_id,
            "project_id": body.project_id,
            "title": url,
            "is_link": True,
            "link_url": url,
            "is_main": False,
            "options": options if options else None,
            "expires_at": expires_at.isoformat()
        }).execute()

        if res.data:
            saved_inputs.append(res.data[0])

    # 2) 파일 메타 저장 (input_contents)
    for f in (body.files or []):
        res = supabase.table("input_contents").insert({
            "user_id": body.user_id,
            "project_id": body.project_id,
            "title": f.title,
            "is_link": False,
            "storage_path": f.storage_path,
            "file_type": f.file_type,
            "file_size": f.file_size,
            "is_main": False,
            "options": options if options else None,
            "expires_at": expires_at.isoformat()
        }).execute()

        if res.data:
            saved_inputs.append(res.data[0])

    return {
        "status": "ok",
        "inputs": saved_inputs
    }

# 입력 소스 삭제
@router.delete("/{input_id}")
def delete_input(input_id: int):
    try:
        # 1) input 조회
        raw = (
            supabase.table("input_contents")
            .select("id, is_link, storage_path")
            .eq("id", input_id)
            .execute()
        )

        rows = raw.data or []

        if not rows:
            return {"message": "이미 삭제된 상태입니다.", "deleted_id": input_id}

        row = rows[0]

        # 2) input_contents row 삭제
        url = f"{SUPABASE_URL}/rest/v1/input_contents?id=eq.{input_id}"
        headers = {
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Prefer": "return=minimal",
        }

        res_del = requests.delete(url, headers=headers)

        if res_del.status_code not in (200, 204):
            print("Delete error:", res_del.text)
            raise HTTPException(status_code=500, detail="DB 삭제 실패")

        # 3) Storage 파일 삭제 (파일 input일 경우만)
        if row.get("is_link") is False:
            storage_path = row.get("storage_path")
            if storage_path:
                supabase.storage.from_(BUCKET).remove([storage_path])

        return {"message": "삭제 완료", "deleted_id": input_id}

    except HTTPException:
        raise
    except Exception as e:
        print("input 삭제 오류:", e)
        raise HTTPException(status_code=500, detail="input 소스 삭제 실패")