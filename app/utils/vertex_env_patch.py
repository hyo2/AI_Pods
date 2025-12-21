import os
import tempfile

def patch_vertex_ai_env():
    """
    Railway 환경에서
    VERTEX_AI_SERVICE_ACCOUNT_JSON → 임시 파일로 변환
    기존 VERTEX_AI_SERVICE_ACCOUNT_FILE 경로를 덮어쓴다
    """
    creds_json = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        return  # 로컬 환경 or 이미 파일 방식이면 그냥 패스

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
        f.write(creds_json.encode("utf-8"))
        temp_path = f.name

    # ⭐ 기존 코드가 쓰는 env를 여기서 덮어씀
    os.environ["VERTEX_AI_SERVICE_ACCOUNT_FILE"] = temp_path
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_path
