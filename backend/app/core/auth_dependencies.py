# backend/app/core/auth_dependencies.py

import os
from fastapi import Header, HTTPException
from jose import jwt, JWTError

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
if not SUPABASE_JWT_SECRET:
    raise RuntimeError("SUPABASE_JWT_SECRET environment variable is missing.")

def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(401, "Authorization header missing")

    try:
        scheme, token = authorization.split(" ")
        if scheme.lower() != "bearer":
            raise ValueError("Invalid auth scheme")
    except Exception:
        raise HTTPException(401, "Invalid Authorization header format")

    try:
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(401, "Invalid token")

    user_id = payload.get("sub")
    email = payload.get("email")

    if not user_id:
        raise HTTPException(401, "User id missing in token")

    return {"id": user_id, "email": email}