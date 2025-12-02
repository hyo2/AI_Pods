# cli.py
import os
import argparse
import logging
from app.service import run_podcast_generation

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    # 환경 변수에서 기본값 로드
    PROJECT_ID_ENV = os.getenv("VERTEX_AI_PROJECT_ID")
    REGION_ENV = os.getenv("VERTEX_AI_REGION", "us-central1")
    # 서비스 계정 파일 경로 설정
    VERTEX_AI_SERVICE_ACCOUNT_FILE = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE") or \
                      os.path.join(os.path.expanduser('~'), ".config", "gcloud", "vertex-ai-service-account.json")
    
    parser = argparse.ArgumentParser(description="LangGraph 기반 팟캐스트 생성기")
    parser.add_argument("--sources", nargs='+', required=True, help="변환할 파일 경로 또는 웹 URL")
    parser.add_argument("--project_id", default=PROJECT_ID_ENV, help="Google Cloud Project ID")
    parser.add_argument("--region", default=REGION_ENV, help="Vertex AI Region")
    parser.add_argument("--sa_file", default=VERTEX_AI_SERVICE_ACCOUNT_FILE, help="서비스 계정 JSON 키 파일 경로")
    parser.add_argument("--host-name", default=None, help="진행자 이름 (미지정시 자동 생성)")
    parser.add_argument("--guest-name", default=None, help="게스트 이름 (미지정시 자동 생성)")
    
    args = parser.parse_args()

    try:
        result = run_podcast_generation(
            sources=args.sources,
            project_id=args.project_id,
            region=args.region,
            sa_file=args.sa_file,
            host_name=args.host_name,
            guest_name=args.guest_name
        )
        
        print("\n✓ 완료!")
        print(f"  → 팟캐스트: {result['final_podcast_path']}")
        print(f"  → 스크립트: {result['transcript_path']}")
        print(f"  → 진행자: {result['host_name']}, 게스트: {result['guest_name']}")
        if result['errors']:
             print("\n⚠️ 오류/경고 목록:")
             for error in result['errors']:
                 print(f"  - {error}")
                 
    except ValueError as e:
        print(f"\n❌ 설정 오류: {e}")
    except RuntimeError as e:
        print(f"\n❌ 실행 오류: {e}")
    except Exception as e:
        print(f"\n❌ 예측하지 못한 오류: {e}")