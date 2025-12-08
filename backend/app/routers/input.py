# app/routers/input.py
from fastapi import APIRouter, UploadFile, Query, File, Form, HTTPException, Depends
from typing import List, Optional
from datetime import datetime, timedelta
import uuid, json
import requests
from app.services.supabase_service import supabase, upload_bytes, SUPABASE_URL, SUPABASE_SERVICE_KEY, normalize_supabase_response

router = APIRouter(prefix="/inputs", tags=["inputs"])

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

# 업로드
# 업로드된 파일 + 링크를 input_contents에 저장
@router.post("/upload")
async def submit_inputs(
    user_id: str = Form(...), # uuid
    project_id: int = Form(...),
    host1: str = Form(""),      # ✅ 선택 필드로 변경
    host2: str = Form(""),      # ✅ 선택 필드로 변경
    style: str = Form(""),      # ✅ 선택 필드로 변경
    links: str = Form("[]"),    # JSON string
    files: List[UploadFile] = File(None)
):
    """
    프론트에서 보낸 files[] + links[] + options 를 input_contents에 저장한다.
    파일은 supabase storage에 저장.
    링크는 input_contents에 URL 정보만 저장.
    호스트/스타일 옵션은 output 생성 요청할 때 사용되므로 input 단계에 options로 저장해 둠.
    
    ✅ host1, host2, style은 선택 필드 - 소스 추가만 할 때는 빈 값으로 전달 가능
    """

    # 일반 사용자 기준 input source 만료일 180일로 지정
    expires_at = datetime.utcnow() + timedelta(days=180)

    saved_inputs = []

    # options 딕셔너리 생성 (값이 있을 때만 포함)
    options = {}
    if host1:
        options["host1"] = host1
    if host2:
        options["host2"] = host2
    if style:
        options["style"] = style

    # 1) 링크 저장 (input_contents)
    link_list = json.loads(links) if links else []

    for url in link_list:
        res = supabase.table("input_contents").insert({
            "user_id": user_id,
            "project_id": project_id,
            "title": url,
            "is_link": True,
            "link_url": url,
            "options": options if options else None,  # 빈 dict 대신 None
            "expires_at": expires_at.isoformat()
        }).execute()

        saved_inputs.append(res.data[0])

    # 2) 파일 저장 (supabase storage + input_contents)
    if files:
        for file in files:
            # 파일 읽기
            content = await file.read()

            ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
            file_id = f"{uuid.uuid4()}.{ext}"

            folder = f"user/{user_id}/project/{project_id}/inputs"
            storage_path = upload_bytes(
                            file_bytes=content,
                            folder=folder,
                            filename=file_id,
                            content_type=file.content_type
                        )

            res = supabase.table("input_contents").insert({
                "user_id": user_id,
                "project_id": project_id,
                "title": file.filename,
                "is_link": False,
                "storage_path": storage_path,
                "file_type": file.content_type,
                "file_size": len(content),
                "options": options if options else None,  # ✅ 빈 dict 대신 None
                "expires_at": expires_at.isoformat()
            }).execute()

            saved_inputs.append(res.data[0])

    return {
        "status": "ok",
        "inputs": saved_inputs
    }

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