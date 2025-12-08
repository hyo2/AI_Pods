# app/routers/storage.py
from fastapi import APIRouter
from app.services.supabase_service import create_signed_url

router = APIRouter()

@router.get("/storage/signed-url")
def get_signed(path: str):
    url = create_signed_url(path, 2592000)  # 30일 = 3600 × 24 × 30 = 2,592,000초
    return {"url": url}
