"""
Phase 4 이미지 생성 테스트
프롬프트 → 이미지 생성
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 찾기
current_dir = Path(__file__).parent
project_root = current_dir.parent if current_dir.name == "tests" else current_dir

# 작업 디렉토리를 프로젝트 루트로 변경
os.chdir(project_root)

# .env 파일 자동 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(project_root))

# Import
try:
    from app.nodes.image_generation_node import (
        ImageGenerationNode,
        load_prompts,
        save_image_manifest,
        print_generation_summary
    )
    print("✅ app.nodes에서 import 성공")
except ImportError:
    try:
        sys.path.insert(0, str(current_dir))
        from image_generation_node import (
            ImageGenerationNode,
            load_prompts,
            save_image_manifest,
            print_generation_summary
        )
        print("✅ 현재 디렉토리에서 import 성공")
    except ImportError as e:
        print(f"❌ Import 실패: {str(e)}")
        sys.exit(1)


def run_image_generation(project_id: str = None):
    """
    이미지 생성 실행
    
    플로우:
    1. 프롬프트 로드 (Phase 3 결과)
    2. 이미지 생성
    3. 매니페스트 저장
    """
    print("\n" + "="*80)
    print("🖼️  Phase 4: 이미지 생성")
    print("="*80)
    
    # ========================================================================
    # 프롬프트 로드
    # ========================================================================
    
    prompts_path = os.path.join(project_root, "outputs/image_prompts/image_prompts.json")
    
    if not os.path.exists(prompts_path):
        print(f"❌ 프롬프트 파일 없음: {prompts_path}")
        print("   Phase 3를 먼저 실행하세요: python tests/test_new_pipeline.py")
        return None
    
    print(f"\n📄 프롬프트 로드: {prompts_path}")
    prompts = load_prompts(prompts_path)
    print(f"✅ {len(prompts)}개 프롬프트 로드")
    
    # 프롬프트 미리보기
    print(f"\n📋 프롬프트 미리보기:")
    for i, p in enumerate(prompts[:3]):  # 처음 3개만
        print(f"\n[{i+1}] {p.get('image_id')} - {p.get('image_title')}")
        prompt_text = p.get('image_prompt', '')
        print(f"    {prompt_text[:100]}...")
    
    if len(prompts) > 3:
        print(f"\n... 외 {len(prompts) - 3}개")
    
    # ========================================================================
    # 이미지 생성
    # ========================================================================
    
    print(f"\n{'='*80}")
    print("🎨 이미지 생성 시작")
    print(f"{'='*80}")
    
    generator = ImageGenerationNode(
        project_id=project_id,
        output_dir="outputs/images"
    )
    
    image_paths = generator.generate_images_from_prompts(prompts)
    
    # ========================================================================
    # 결과 저장
    # ========================================================================
    
    if image_paths:
        # 매니페스트 저장
        manifest_path = os.path.join(project_root, "outputs/images/manifest.json")
        save_image_manifest(image_paths, manifest_path)
        
        # 요약 출력
        print_generation_summary(image_paths)
        
        # 파일 위치 안내
        print(f"\n📁 생성된 파일:")
        print(f"  - 이미지: outputs/images/")
        print(f"  - 매니페스트: {manifest_path}")
    else:
        print("\n❌ 이미지 생성 실패")
    
    print("\n" + "="*80)
    
    return image_paths


def main():
    """메인 함수"""
    print("\n🖼️  Phase 4: 이미지 생성 테스트")
    print("="*80)
    
    # 이미지 생성 실행
    image_paths = run_image_generation()
    
    if image_paths:
        print(f"\n✅ 성공: {len(image_paths)}개 이미지 생성")
    else:
        print("\n❌ 실패: 이미지 생성 안 됨")


if __name__ == "__main__":
    main()