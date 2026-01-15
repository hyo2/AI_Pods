# DB 및 Storage 연동
from dotenv import load_dotenv
load_dotenv()

import os, re
from supabase import create_client, Client
from typing import Optional, List

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# auth client
supabase_auth = create_client(
    SUPABASE_URL,
    SUPABASE_ANON_KEY
)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

BUCKET = "project_resources"

def safe_filename(filename: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", filename)

# 프론트에서 바로 업로드할 때 쓰는 용
def create_signed_upload(bucket: str, path: str, expires_in: int = 3600, upsert: bool = False):
    """
    storage3 버전 차이로 create_signed_upload_url 시그니처가 제각각이라,
    우선 '기본 호출'로만 signed upload token을 발급한다.
    """
    res = supabase.storage.from_(bucket).create_signed_upload_url(path)

    # supabase-py 응답 형태 방어적으로 처리
    if isinstance(res, dict) and "data" in res:
        return res["data"]
    data = getattr(res, "data", None)
    return data if data is not None else res

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
    # return supabase.storage.from_(BUCKET).get_public_url(path)
    return path 

# signend_url 생성
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


# 헬퍼 함수 - Supabase 응답 정규화
def normalize_supabase_response(res):
    """
    Supabase Python SDK 응답을 항상 { "data": [...] } 형태로 정규화한다.
    """
    if isinstance(res, dict):
        # 이미 dict라면 data가 없을 수도 있음
        data = res.get("data")
        if data is None:
            # 단일 row가 dict로 온 경우 강제로 리스트로 감싸기
            return { "data": [res] }
        return { "data": data }

    # SDK Response 객체인 경우
    if hasattr(res, "data"):
        data = res.data
        if isinstance(data, dict):
            return { "data": [data] }
        return { "data": data or [] }

    # 혹시 모르는 edge case
    return { "data": [] }


