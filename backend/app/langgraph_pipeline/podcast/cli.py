# app/service/cli.py
import os
import sys
import argparse

# 프로젝트 루트를 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

print(f"🔍 Python path: {sys.path[0]}")  # 디버그
print(f"🔍 Current dir: {current_dir}")  # 디버그

from app.services.podcast import run_podcast_generation

if __name__ == "__main__":
    print("✓ CLI 시작")  # 디버그
    
    PROJECT_ID_ENV = os.getenv("VERTEX_AI_PROJECT_ID")
    REGION_ENV = os.getenv("VERTEX_AI_REGION", "us-central1")
    SA_FILE_DEFAULT = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE")
    
    print(f"🔍 PROJECT_ID: {PROJECT_ID_ENV}")  # 디버그
    print(f"🔍 SA_FILE: {SA_FILE_DEFAULT}")  # 디버그
    
    parser = argparse.ArgumentParser(description="팟캐스트 생성기")
    parser.add_argument("--sources", nargs='+', required=True, help="파일 경로")
    parser.add_argument("--project-id", default=PROJECT_ID_ENV, help="GCP Project ID")
    parser.add_argument("--region", default=REGION_ENV, help="Vertex AI Region")
    parser.add_argument("--sa-file", default=SA_FILE_DEFAULT, help="서비스 계정 파일")
    parser.add_argument("--host-name", default=None, help="진행자 이름")
    parser.add_argument("--guest-name", default=None, help="게스트 이름")
    parser.add_argument("--style", default="explain", help="스타일")
    
    args = parser.parse_args()
    
    print(f"✓ 인자 파싱 완료")  # 디버그
    print(f"  sources: {args.sources}")  # 디버그
    
    if not args.project_id:
        print("❌ 오류: VERTEX_AI_PROJECT_ID 환경 변수를 설정하거나 --project-id 옵션을 사용하세요")
        print("\n설정 방법:")
        print('  $env:VERTEX_AI_PROJECT_ID="your-project-id"')
        sys.exit(1)
    
    if not args.sa_file:
        print("❌ 오류: VERTEX_AI_SERVICE_ACCOUNT_FILE 환경 변수를 설정하거나 --sa-file 옵션을 사용하세요")
        print("\n설정 방법:")
        print('  $env:VERTEX_AI_SERVICE_ACCOUNT_FILE="C:\\path\\to\\service-account.json"')
        sys.exit(1)
    
    if not os.path.exists(args.sa_file):
        print(f"❌ 오류: 서비스 계정 파일을 찾을 수 없습니다")
        print(f"   경로: {args.sa_file}")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"📻 팟캐스트 생성 시작")
    print(f"{'='*60}")
    print(f"소스: {args.sources}")
    print(f"스타일: {args.style}")
    print(f"프로젝트: {args.project_id}")
    print(f"{'='*60}\n")
    
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
        
        print(f"\n{'='*60}")
        print(f"✅ 팟캐스트 생성 완료!")
        print(f"{'='*60}")
        print(f"🎵 오디오: {result['final_podcast_path']}")
        print(f"📝 스크립트: {result['transcript_path']}")
        print(f"👥 진행자: {result['host_name']}, 게스트: {result['guest_name']}")
        
        if result.get('errors'):
            print(f"\n⚠️  경고 ({len(result['errors'])}개):")
            for error in result['errors']:
                print(f"  - {error}")
        
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ 오류 발생!")
        print(f"{'='*60}")
        print(f"{str(e)}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)