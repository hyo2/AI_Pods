import os

def patch_vertex_ai_env():
    """
    Railway 환경에서
    VERTEX_AI_SERVICE_ACCOUNT_JSON → 고정 경로 파일로 변환
    
    ⭐ 핵심: 고정 경로 사용으로 백그라운드 태스크에서도 안정적으로 접근
    """
    creds_json = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        # 로컬 환경이거나 이미 파일 경로가 있으면 패스
        print("ℹ️ VERTEX_AI_SERVICE_ACCOUNT_JSON 없음 (로컬 환경으로 추정)")
        return

    print("🔧 Railway 환경 감지: JSON → 고정 경로 파일 변환 중...")

    # ✅ 고정 경로 사용 (Railway는 /tmp 사용 가능)
    temp_path = "/tmp/vertex_ai_service_account.json"
    
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(creds_json)
        
        # ⭐ 두 환경 변수 모두 설정
        os.environ["VERTEX_AI_SERVICE_ACCOUNT_FILE"] = temp_path
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_path
        
        print(f"✅ 서비스 계정 파일 생성: {temp_path}")
        print(f"✅ VERTEX_AI_SERVICE_ACCOUNT_FILE={temp_path}")
        print(f"✅ GOOGLE_APPLICATION_CREDENTIALS={temp_path}")
        
    except Exception as e:
        print(f"❌ 서비스 계정 파일 생성 실패: {e}")
        raise