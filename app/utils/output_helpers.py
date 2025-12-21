# backend/app/utils/output_helpers.py
import time
from app.services.supabase_service import supabase

def supabase_retry(fn, desc: str, max_retries: int = 3, delay: float = 0.2):
    """
    Supabase 쿼리용 retry 래퍼.
    일시적인 네트워크/프로토콜 오류에 대해 재시도.
    """
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            print(f"[Supabase Retry] {desc} {attempt}/{max_retries} 실패: {e}")
            if attempt < max_retries:
                time.sleep(delay)
    raise last_err


def output_exists(output_id: int) -> bool:
    """
    output_contents에 해당 output_id가 아직 존재하는지 확인.
    - 사용자가 생성 도중 삭제했을 때 FK 에러 방지용
    """
    try:
        res = supabase.table("output_contents") \
            .select("id") \
            .eq("id", output_id) \
            .execute()
        return bool(res.data)
    except Exception as e:
        print(f"[output_exists] 확인 실패 (output_id={output_id}):", e)
        return False


def to_seconds(time_str):
    """타임스탬프 파싱 -> 초로 바꾸기"""
    if time_str is None:
        return None
    if isinstance(time_str, (int, float)):
        return float(time_str)

    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h = 0
        m, s = parts
    else:
        return float(time_str)

    return int(h) * 3600 + int(m) * 60 + float(s)