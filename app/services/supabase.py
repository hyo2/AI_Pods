# DB 및 Storage 연동
from dotenv import load_dotenv
load_dotenv()

import os, re
from supabase import create_client, Client
from typing import Optional, List

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

BUCKET = "project_resources"

def safe_filename(filename: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", filename)

# Storage에 파일 업로드(bytes) 후 public URL 반환
def upload_bytes(file_bytes, folder, filename, content_type=None):
    path = f"{folder}/{filename}"

    options = {
        "contentType": content_type or "application/octet-stream",
    }

    res = supabase.storage.from_(BUCKET).upload(
        path,
        file_bytes,
        file_options=options
    )

    if hasattr(res, "error") and res.error:
        print("Storage upload error:", res.error)
        return None

    # public URL 반환
    return supabase.storage.from_(BUCKET).get_public_url(path)

def create_signed_url(path: str, expires_in: int = 3600) -> str:
    signed = supabase.storage.from_(BUCKET).create_signed_url(path, expires_in)
    if isinstance(signed, dict):
        return signed.get("signedURL") or signed.get("signed_url") or ""
    return signed

# 프로젝트 삭제 시 프로젝트 내 파일도 전체 삭제
def delete_project_folder(user_id: str, project_id: int):
    folder = f"user/{user_id}/project/{project_id}/"
    bucket = supabase.storage.from_(BUCKET)

    # 폴더 내 모든 파일 목록 가져오기
    files = bucket.list(path=folder)

    if isinstance(files, dict) and "error" in files:
        return  # 폴더 자체가 없을 수도 있으므로 무시

    # 파일 이름만 추출
    file_paths = [f"{folder}{item['name']}" for item in files]

    if file_paths:
        bucket.remove(file_paths)

