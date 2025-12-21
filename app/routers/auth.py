# backend/app/routers/auth.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.services.supabase_service import supabase, supabase_auth

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
    # 1) 회원가입 (auth client)
    try:
        sign_up_res = supabase_auth.auth.sign_up(
            {
                "email": body.email,
                "password": body.password,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase sign_up 실패: {e}")

    if sign_up_res.user is None:
        raise HTTPException(status_code=400, detail="User creation failed")

    # 2) 바로 로그인 (auth client)
    try:
        sign_in_res = supabase_auth.auth.sign_in_with_password(
            {
                "email": body.email,
                "password": body.password,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto login 실패: {e}")

    user = sign_in_res.user
    session = sign_in_res.session

    if user is None or session is None:
        raise HTTPException(status_code=500, detail="Session creation failed")

    # 3) public.users upsert (service_role client)
    profile = {
        "id": user.id,
        "email": body.email,
        "name": body.name,
    }

    try:
        prof_res = (
            supabase
            .table("users")
            .upsert(profile, on_conflict="id")
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"users upsert 실패: {e}")

    saved_profile = prof_res.data[0] if prof_res.data else None

    return {
        "message": "signup ok",
        "access_token": session.access_token,
        "user": {
            "id": user.id,
            "email": body.email,
            "name": saved_profile.get("name") if saved_profile else body.name,
        },
    }


@router.post("/users/login")
def login(body: LoginRequest):
    # 1) 로그인 (auth client)
    try:
        response = supabase_auth.auth.sign_in_with_password(
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

    # 2) 프로필 조회 (service_role client)
    try:
        prof_res = (
            supabase
            .table("users")
            .select("*")
            .eq("id", user.id)
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"users select 실패: {e}")

    saved_profile = prof_res.data[0] if prof_res.data else None

    return {
        "message": "login ok",
        "access_token": session.access_token,
        "user": {
            "id": user.id,
            "email": body.email,
            "name": saved_profile.get("name") if saved_profile else None,
        },
    }
