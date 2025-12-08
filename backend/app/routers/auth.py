# backend/app/routers/auth.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.services.supabase_service import supabase

router = APIRouter()


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/users/signup")
def signup(body: SignupRequest):
    """
    Supabase Auth로 회원가입 + public.users에 프로필 생성/업데이트
    """
    # 1) Supabase Auth 회원가입
    try:
        response = supabase.auth.sign_up(
            {
                "email": body.email,
                "password": body.password,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase sign_up 실패: {e}")

    user = response.user
    session = response.session

    if user is None:
        raise HTTPException(
            status_code=400,
            detail="User creation failed (user is None). Supabase Auth 설정을 확인하세요."
        )

    user_id = user.id

    # 2) public.users에 프로필 upsert
    profile = {
        "id": user_id,
        "email": body.email,
        "name": body.name,
    }

    try:
        prof_res = supabase.table("users").upsert(
            profile,
            on_conflict="id"
        ).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"users upsert 실패: {e}")

    # prof_res.data가 리스트 형태로 반환됨
    saved_profile = prof_res.data[0] if prof_res.data else None

    # 3) 토큰/유저 정보 프론트로 반환
    access_token = session.access_token if session else None

    return {
        "message": "signup ok",
        "access_token": access_token,
        "user": {
            "id": user_id,
            "email": body.email,
            "name": saved_profile.get("name") if saved_profile else body.name,
        },
    }


@router.post("/users/login")
def login(body: LoginRequest):
    """
    Supabase Auth 로그인 -> access_token + user 객체 반환
    """
    try:
        response = supabase.auth.sign_in_with_password(
            {
                "email": body.email,
                "password": body.password,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase sign_in 실패: {e}")

    user = response.user
    session = response.session

    if user is None or session is None:
        raise HTTPException(status_code=400, detail="이메일 또는 비밀번호가 올바르지 않습니다.")

    user_id = user.id
    access_token = session.access_token

    # public.users에 행이 없으면 생성해두기 (최초 로그인 케이스)
    try:
        prof_res = supabase.table("users").select("*").eq("id", user_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"users upsert 실패: {e}")

    saved_profile = prof_res.data[0] if prof_res.data else None

    return {
        "message": "login ok",
        "access_token": access_token,
        "user": {
            "id": user_id,
            "email": body.email,
            "name": saved_profile.get("name") if saved_profile else None,
        },
    }