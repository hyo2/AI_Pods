# app/routers/input.py
from fastapi import APIRouter, UploadFile, Query, File, Form, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid, json
import requests
from app.services.supabase_service import create_signed_upload, supabase, upload_bytes, SUPABASE_URL, SUPABASE_SERVICE_KEY, normalize_supabase_response, BUCKET
from pydantic import BaseModel

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


# 기존 업로드 로직
# 업로드된 파일 + 링크를 input_contents에 저장
@router.post("/upload")
async def submit_inputs(
    user_id: str = Form(...),
    project_id: int = Form(...),
    host1: str = Form(""),
    host2: str = Form(""),
    style: str = Form(""),
    links: str = Form("[]"),
    files: List[UploadFile] = File(None)
):
    t0 = time.perf_counter()
    logger.info(f"[upload] start user={user_id} project={project_id}")

    expires_at = datetime.utcnow() + timedelta(days=180)
    saved_inputs = []

    options = {}
    if host1:
        options["host1"] = host1
    if host2:
        options["host2"] = host2
    if style:
        options["style"] = style

    # -----------------------
    # 1) 링크 저장
    # -----------------------
    t_links0 = time.perf_counter()
    link_list = json.loads(links) if links else []

    for url in link_list:
        res = supabase.table("input_contents").insert({
            "user_id": user_id,
            "project_id": project_id,
            "title": url,
            "is_link": True,
            "link_url": url,
            "is_main": False,
            "options": options if options else None,
            "expires_at": expires_at.isoformat()
        }).execute()
        saved_inputs.append(res.data[0])

    logger.info(
        f"[upload] links_saved count={len(link_list)} "
        f"elapsed={(time.perf_counter() - t_links0):.3f}s"
    )

    # -----------------------
    # 2) 파일 저장
    # -----------------------
    if files:
        for file in files:
            tf0 = time.perf_counter()
            logger.info(f"[upload] file_start name={file.filename}")

            # (A) file.read()
            tr0 = time.perf_counter()
            content = await file.read()
            read_s = time.perf_counter() - tr0
            size_mb = len(content) / (1024 * 1024)
            logger.info(
                f"[upload] file_read name={file.filename} "
                f"size={size_mb:.2f}MB elapsed={read_s:.3f}s"
            )

            # (B) Supabase Storage 업로드
            tu0 = time.perf_counter()
            ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
            file_id = f"{uuid.uuid4()}.{ext}"
            folder = f"user/{user_id}/project/{project_id}/inputs"

            storage_path = upload_bytes(
                file_bytes=content,
                folder=folder,
                filename=file_id,
                content_type=file.content_type
            )
            upload_s = time.perf_counter() - tu0
            logger.info(
                f"[upload] storage_uploaded name={file.filename} "
                f"path={storage_path} elapsed={upload_s:.3f}s"
            )

            # (C) DB insert
            td0 = time.perf_counter()
            res = supabase.table("input_contents").insert({
                "user_id": user_id,
                "project_id": project_id,
                "title": file.filename,
                "is_link": False,
                "storage_path": storage_path,
                "file_type": file.content_type,
                "file_size": len(content),
                "is_main": False,
                "options": options if options else None,
                "expires_at": expires_at.isoformat()
            }).execute()
            saved_inputs.append(res.data[0])
            db_s = time.perf_counter() - td0

            logger.info(
                f"[upload] db_inserted name={file.filename} elapsed={db_s:.3f}s"
            )

            logger.info(
                f"[upload] file_done name={file.filename} "
                f"total_elapsed={(time.perf_counter() - tf0):.3f}s"
            )

    logger.info(
        f"[upload] done total_elapsed={(time.perf_counter() - t0):.3f}s"
    )

    return {"status": "ok", "inputs": saved_inputs}


# 입력 소스 삭제
@router.delete("/{input_id}")
def delete_input(input_id: int):
    try:
        # 존재 여부 확인
        raw = (
            supabase.table("input_contents")
            .select("id, is_link, storage_path")
            .eq("id", input_id)
            .execute()
        )

        normalized = normalize_supabase_response(raw)
        rows = normalized["data"]

        # row 없으면 이미 삭제된 상태 -> 성공 처리
        if not rows:
            return {"message": "이미 삭제된 상태입니다.", "deleted_id": input_id}

        check = rows[0]

        # DB 삭제
        url = f"{SUPABASE_URL}/rest/v1/input_contents?id=eq.{input_id}"
        headers = {
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Prefer": "return=minimal",
        }

        res_del = requests.delete(url, headers=headers)

        # 상태코드 검증
        if res_del.status_code not in (200, 204):
            print("Delete error:", res_del.text)
            raise HTTPException(status_code=500, detail="DB 삭제 실패")

        # Storage 삭제
        if check.get("is_link") is False:
            storage_path = check.get("storage_path")
            if storage_path:
                supabase.storage.from_("inputs").remove([storage_path])

        return {"message": "삭제 완료", "deleted_id": input_id}

    except HTTPException:
        raise
    except Exception as e:
        print("input 삭제 오류:", e)
        raise HTTPException(status_code=500, detail="input 소스 삭제 실패")