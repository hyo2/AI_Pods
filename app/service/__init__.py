# app/service/cli.py
import os
import sys
import argparse

# 프로젝트 루트를 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from app.services.podcast import run_podcast_generation

if __name__ == "__main__":
    PROJECT_ID_ENV = os.getenv("VERTEX_AI_PROJECT_ID")
    REGION_ENV = os.getenv("VERTEX_AI_REGION", "us-central1")
    SA_FILE_DEFAULT = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE")
    
    parser = argparse.ArgumentParser(description="팟캐스트 생성기")
    parser.add_argument("--sources", nargs='+', required=True, help="파일 경로 또는 URL")
    parser.add_argument("--project-id", default=PROJECT_ID_ENV, help="GCP Project ID")
    parser.add_argument("--region", default=REGION_ENV, help="Vertex AI Region")
    parser.add_argument("--sa-file", default=SA_FILE_DEFAULT, help="서비스 계정 파일")
    parser.add_argument("--host-name", default=None, help="진행자 이름")
    parser.add_argument("--guest-name", default=None, help="게스트 이름")
    parser.add_argument("--style", default="explain", help="스타일")
    
    args = parser.parse_args()
    
    if not args.project_id:
        print(" VERTEX_AI_PROJECT_ID 환경 변수 필요")
        sys.exit(1)
    
    if not args.sa_file or not os.path.exists(args.sa_file):
        print(f" 서비스 계정 파일 없음: {args.sa_file}")
        sys.exit(1)
    
    print(f"\n 팟캐스트 생성 시작...")
    print(f"소스: {args.sources}")
    print(f"스타일: {args.style}\n")
    
    try:
        result = run_podcast_generation(
            sources=args.sources,
            project_id=args.project_id,
            region=args.region,
            sa_file=args.sa_file,
            host_name=args.host_name,
            guest_name=args.guest_name,
            style=args.style
        )
        
        print(f"\n 완료!")
        print(f" {result['final_podcast_path']}")
        print(f" {result['transcript_path']}")
        
    except Exception as e:
        print(f"\n 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)