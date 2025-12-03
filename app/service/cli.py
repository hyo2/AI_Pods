# app/service/cli.py
import os
import sys
import argparse
import logging

# 로깅 설정 (가장 먼저!)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 프로젝트 루트를 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

logger.info("="*60)
logger.info("CLI 시작")
logger.info("="*60)
logger.info(f"Python 경로: {sys.path[0]}")
logger.info(f"현재 디렉토리: {current_dir}")
logger.info(f"프로젝트 루트: {project_root}")

try:
    from app.services.podcast import run_podcast_generation
    logger.info("✓ 모듈 임포트 성공")
except ImportError as e:
    logger.error(f"✗ 모듈 임포트 실패: {e}")
    sys.exit(1)


def main():
    """CLI 메인 함수"""
    
    # 환경 변수 로드
    PROJECT_ID_ENV = os.getenv("VERTEX_AI_PROJECT_ID")
    REGION_ENV = os.getenv("VERTEX_AI_REGION", "us-central1")
    SA_FILE_DEFAULT = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE")
    
    logger.info(f"환경 변수 확인:")
    logger.info(f"  PROJECT_ID: {PROJECT_ID_ENV or '(없음)'}")
    logger.info(f"  REGION: {REGION_ENV}")
    logger.info(f"  SA_FILE: {SA_FILE_DEFAULT or '(없음)'}")
    
    # 인자 파서 설정
    parser = argparse.ArgumentParser(
        description="팟캐스트 생성기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  python app/service/cli.py --sources "file1.pdf" "file2.docx"
  python app/service/cli.py --sources "https://example.com" --style debate
  python app/service/cli.py --sources "file.pdf" --host-name "김철수" --guest-name "이영희"
        """
    )
    
    parser.add_argument(
        "--sources", 
        nargs='+', 
        required=True, 
        help="파일 경로 또는 URL (여러 개 가능)"
    )
    parser.add_argument(
        "--project-id", 
        default=PROJECT_ID_ENV, 
        help="GCP Project ID (환경 변수: VERTEX_AI_PROJECT_ID)"
    )
    parser.add_argument(
        "--region", 
        default=REGION_ENV, 
        help="Vertex AI Region (기본값: us-central1)"
    )
    parser.add_argument(
        "--sa-file", 
        default=SA_FILE_DEFAULT, 
        help="서비스 계정 파일 경로 (환경 변수: VERTEX_AI_SERVICE_ACCOUNT_FILE)"
    )
    parser.add_argument(
        "--host-name", 
        default=None, 
        help="진행자 이름 (선택, 미지정시 자동 생성)"
    )
    parser.add_argument(
        "--guest-name", 
        default=None, 
        help="게스트 이름 (선택, 미지정시 자동 생성)"
    )
    parser.add_argument(
        "--style", 
        default="explain",
        choices=["explain", "debate", "interview", "summary"],
        help="팟캐스트 스타일 (기본값: explain)"
    )
    
    # 인자 파싱
    try:
        args = parser.parse_args()
    except SystemExit:
        # argparse가 --help 또는 오류로 종료
        return
    
    logger.info("="*60)
    logger.info("인자 파싱 완료")
    logger.info("="*60)
    logger.info(f"소스: {args.sources}")
    logger.info(f"스타일: {args.style}")
    logger.info(f"진행자: {args.host_name or '(자동 생성)'}")
    logger.info(f"게스트: {args.guest_name or '(자동 생성)'}")
    
    # === 필수 환경 변수 검증 ===
    if not args.project_id:
        logger.error("="*60)
        logger.error("오류: VERTEX_AI_PROJECT_ID가 설정되지 않았습니다")
        logger.error("="*60)
        logger.error("\n설정 방법:")
        logger.error("  Windows PowerShell:")
        logger.error('    $env:VERTEX_AI_PROJECT_ID="your-project-id"')
        logger.error("  Linux/Mac:")
        logger.error('    export VERTEX_AI_PROJECT_ID="your-project-id"')
        logger.error("\n또는 --project-id 옵션 사용:")
        logger.error('    python app/service/cli.py --sources "file.pdf" --project-id "your-project-id"')
        sys.exit(1)
    
    if not args.sa_file:
        logger.error("="*60)
        logger.error("오류: VERTEX_AI_SERVICE_ACCOUNT_FILE이 설정되지 않았습니다")
        logger.error("="*60)
        logger.error("\n설정 방법:")
        logger.error("  Windows PowerShell:")
        logger.error('    $env:VERTEX_AI_SERVICE_ACCOUNT_FILE="C:\\path\\to\\service-account.json"')
        logger.error("  Linux/Mac:")
        logger.error('    export VERTEX_AI_SERVICE_ACCOUNT_FILE="/path/to/service-account.json"')
        sys.exit(1)
    
    if not os.path.exists(args.sa_file):
        logger.error("="*60)
        logger.error(f"오류: 서비스 계정 파일을 찾을 수 없습니다")
        logger.error("="*60)
        logger.error(f"경로: {args.sa_file}")
        logger.error("\n파일이 존재하는지 확인하세요.")
        sys.exit(1)
    
    # === 소스 파일 검증 ===
    logger.info("\n소스 파일 검증 중...")
    verified_sources = []
    
    for source in args.sources:
        if source.startswith("http://") or source.startswith("https://"):
            # URL인 경우
            logger.info(f"  ✓ URL: {source}")
            verified_sources.append(source)
        else:
            # 로컬 파일인 경우 - 경로 정규화
            normalized_path = os.path.normpath(source)
            absolute_path = os.path.abspath(normalized_path)
            
            logger.info(f"  파일 검증 중: {os.path.basename(source)}")
            logger.info(f"    원본 경로: {source}")
            logger.info(f"    정규화된 경로: {normalized_path}")
            logger.info(f"    절대 경로: {absolute_path}")
            
            # 여러 경로 시도
            paths_to_try = [
                source,
                normalized_path,
                absolute_path,
                source.replace('\u00a0', ' '),  # Non-breaking space 제거
                source.strip()
            ]
            
            found = False
            for path_attempt in paths_to_try:
                if os.path.exists(path_attempt):
                    file_size = os.path.getsize(path_attempt) / 1024  # KB
                    logger.info(f"  ✓ 파일 발견: {os.path.basename(path_attempt)} ({file_size:.1f} KB)")
                    verified_sources.append(path_attempt)
                    found = True
                    break
            
            if not found:
                logger.error(f"\n오류: 파일을 찾을 수 없습니다")
                logger.error(f"  검색한 경로:")
                for p in paths_to_try:
                    logger.error(f"    - {p}")
                logger.error(f"\n다음을 확인하세요:")
                logger.error(f"  1. 파일이 실제로 존재하는지")
                logger.error(f"  2. 경로에 특수 문자나 공백이 있는지")
                logger.error(f"  3. 파일명을 간단하게 변경하거나 현재 디렉토리로 복사")
                sys.exit(1)
    
    # 검증된 소스로 업데이트
    args.sources = verified_sources
    
    # === 팟캐스트 생성 시작 ===
    logger.info("\n" + "="*60)
    logger.info("📻 팟캐스트 생성 시작")
    logger.info("="*60)
    logger.info(f"프로젝트: {args.project_id}")
    logger.info(f"리전: {args.region}")
    logger.info(f"스타일: {args.style}")
    logger.info("="*60 + "\n")
    
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
        
        # === 성공 메시지 ===
        logger.info("\n" + "="*60)
        logger.info("✅ 팟캐스트 생성 완료!")
        logger.info("="*60)
        logger.info(f"🎵 오디오 파일: {result['final_podcast_path']}")
        logger.info(f"📝 스크립트: {result['transcript_path']}")
        logger.info(f"👥 진행자: {result['host_name']}")
        logger.info(f"👥 게스트: {result['guest_name']}")
        
        if result.get('errors'):
            logger.warning(f"\n⚠️  경고 ({len(result['errors'])}개):")
            for error in result['errors']:
                logger.warning(f"  - {error}")
        
        logger.info("="*60 + "\n")
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("\n\n사용자에 의해 중단되었습니다.")
        return 130
        
    except Exception as e:
        logger.error("\n" + "="*60)
        logger.error("❌ 오류 발생!")
        logger.error("="*60)
        logger.error(f"{str(e)}\n")
        
        # 상세 스택 트레이스
        import traceback
        logger.error("상세 오류 정보:")
        traceback.print_exc()
        
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code if exit_code is not None else 0)
    except Exception as e:
        logger.error(f"예기치 않은 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)