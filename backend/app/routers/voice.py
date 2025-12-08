# app/routers/voice.py
from fastapi import APIRouter, HTTPException
from app.services.supabase_service import supabase

router = APIRouter(prefix="/voices", tags=["voices"])

@router.get("/")
def get_voices():
    """
    TTS 목소리 전체 목록 조회
    """
    try:
        # Supabase에서 tts_voice 테이블 조회
        res = (
            supabase.table("tts_voice")
            .select("name, gender")
            .order("name", desc=False)
            .execute()
        )

        return {"voices": res.data or []}

    except Exception as e:
        print("Voices Fetch Error:", e)
        raise HTTPException(status_code=500, detail="TTS 목소리 목록 조회 실패")
