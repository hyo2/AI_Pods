"""
Phase 3 통합 테스트 (새로운 설계)
메타데이터 → 이미지 계획 → 프롬프트 → 타임스탬프 매핑
"""

import sys
import os
import json
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
    from app.nodes.script_parser_node import ScriptParserNode
    from app.nodes.metadata_extraction_node import (
        MetadataExtractionNode,
        save_metadata,
        print_metadata_summary
    )
    from app.nodes.image_planning_node import (
        ImagePlanningNode,
        print_image_plans_summary,
        export_image_plans
    )
    from app.nodes.prompt_generation_node import (
        PromptGenerationNode,
        print_prompts_summary,
        export_prompts
    )
    from app.nodes.timestamp_mapper import (
        TimestampMapper,
        print_timeline_summary,
        export_timeline,
        export_video_manifest
    )
    print("✅ app.nodes에서 import 성공")
except ImportError:
    try:
        sys.path.insert(0, str(current_dir))
        from script_parser_node import ScriptParserNode
        from metadata_extraction_node import (
            MetadataExtractionNode,
            save_metadata,
            print_metadata_summary
        )
        from image_planning_node import (
            ImagePlanningNode,
            print_image_plans_summary,
            export_image_plans
        )
        from prompt_generation_node import (
            PromptGenerationNode,
            print_prompts_summary,
            export_prompts
        )
        from timestamp_mapper import (
            TimestampMapper,
            print_timeline_summary,
            export_timeline,
            export_video_manifest
        )
        print("✅ 현재 디렉토리에서 import 성공")
    except ImportError as e:
        print(f"❌ Import 실패: {str(e)}")
        sys.exit(1)


def run_new_pipeline(project_id: str = None):
    """
    새로운 Phase 3 파이프라인 실행
    
    플로우:
    1. 스크립트 파싱
    2. 메타데이터 추출
    3. 이미지 계획 생성 (신규!)
    4. 프롬프트 생성 (수정)
    5. 타임스탬프 매핑 (신규!)
    """
    print("\n" + "="*80)
    print("🚀 Phase 3 통합 테스트 (새로운 설계)")
    print("="*80)
    
    # ========================================================================
    # Phase 3-1: 스크립트 파싱
    # ========================================================================
    
    print("\n" + "="*80)
    print("📄 Phase 3-1: 스크립트 파싱")
    print("="*80)
    
    script_path = os.path.join(project_root, "data/podcast_script.txt")
    
    if not os.path.exists(script_path):
        print(f"❌ 스크립트 파일 없음: {script_path}")
        return None
    
    parser = ScriptParserNode()
    scenes = parser.parse_from_file(script_path)
    
    print(f"✅ {len(scenes)}개 장면 파싱 완료")
    
    # 전체 스크립트 생성
    full_script = "\n".join([
        f"[{scene.timestamp_start}] {scene.speaker}: {scene.text}"
        for scene in scenes
    ])
    
    # ========================================================================
    # Phase 3-0: 메타데이터 추출
    # ========================================================================
    
    print("\n" + "="*80)
    print("🔍 Phase 3-0: 메타데이터 추출")
    print("="*80)
    
    metadata_extractor = MetadataExtractionNode(project_id=project_id)
    
    # scenes를 전달하면 내부에서 text로 변환됨
    # (기존 구조 활용)
    metadata = metadata_extractor.extract_metadata(scenes)
    
    print_metadata_summary(metadata)
    
    # 저장
    metadata_dir = os.path.join(project_root, "outputs", "metadata")
    os.makedirs(metadata_dir, exist_ok=True)
    metadata_path = os.path.join(metadata_dir, "podcast_metadata.json")
    save_metadata(metadata, metadata_path)
    
    # ========================================================================
    # Phase 3-1: 이미지 계획 생성 (신규!)
    # ========================================================================
    
    print("\n" + "="*80)
    print("🎬 Phase 3-1: 이미지 계획 생성")
    print("="*80)
    
    planner = ImagePlanningNode(project_id=project_id)
    image_plans = planner.create_image_plans(full_script, metadata)
    
    print_image_plans_summary(image_plans)
    
    # 저장
    plans_dir = os.path.join(project_root, "outputs", "image_plans")
    os.makedirs(plans_dir, exist_ok=True)
    plans_path = os.path.join(plans_dir, "image_plans.json")
    export_image_plans(image_plans, plans_path)
    
    # ========================================================================
    # Phase 3-2: 프롬프트 생성 (수정)
    # ========================================================================
    
    print("\n" + "="*80)
    print("📝 Phase 3-2: 프롬프트 생성")
    print("="*80)
    
    prompt_generator = PromptGenerationNode(project_id=project_id)
    image_prompts = prompt_generator.generate_prompts_for_plans(image_plans, metadata)
    
    print_prompts_summary(image_prompts)
    
    # 저장
    prompts_dir = os.path.join(project_root, "outputs", "image_prompts")
    os.makedirs(prompts_dir, exist_ok=True)
    prompts_path = os.path.join(prompts_dir, "image_prompts.json")
    export_prompts(image_prompts, prompts_path)
    
    # ========================================================================
    # Phase 3-3: 타임스탬프 매핑 (신규!)
    # ========================================================================
    
    print("\n" + "="*80)
    print("⏰ Phase 3-3: 타임스탬프 매핑")
    print("="*80)
    
    mapper = TimestampMapper()
    timeline = mapper.create_timeline(image_prompts)
    
    print_timeline_summary(timeline)
    
    # 저장
    timeline_dir = os.path.join(project_root, "outputs", "timeline")
    os.makedirs(timeline_dir, exist_ok=True)
    timeline_path = os.path.join(timeline_dir, "timeline.json")
    export_timeline(timeline, timeline_path)
    
    # ========================================================================
    # 최종 요약
    # ========================================================================
    
    print("\n" + "="*80)
    print("🎉 Phase 3 완료!")
    print("="*80)
    
    print(f"\n📊 최종 결과:")
    print(f"  입력: {len(scenes)}개 장면")
    print(f"  이미지 계획: {len(image_plans)}개")
    print(f"  프롬프트: {len(image_prompts)}개")
    print(f"  타임라인: {len(timeline)}개 항목")
    
    print(f"\n📁 생성된 파일:")
    print(f"  - 메타데이터: {metadata_path}")
    print(f"  - 이미지 계획: {plans_path}")
    print(f"  - 프롬프트: {prompts_path}")
    print(f"  - 타임라인: {timeline_path}")
    
    print("\n" + "="*80)
    
    return {
        'scenes': scenes,
        'metadata': metadata,
        'image_plans': image_plans,
        'image_prompts': image_prompts,
        'timeline': timeline
    }


def analyze_results():
    """생성된 결과 분석"""
    print("\n" + "="*80)
    print("📊 결과 분석")
    print("="*80)
    
    # 프롬프트 로드
    prompts_path = os.path.join(project_root, "outputs/image_prompts/image_prompts.json")
    
    if not os.path.exists(prompts_path):
        print("❌ 프롬프트 파일 없음")
        return
    
    with open(prompts_path, 'r', encoding='utf-8') as f:
        prompts = json.load(f)
    
    print(f"\n📈 통계:")
    print(f"  총 이미지: {len(prompts)}개")
    
    # 프롬프트 길이 분석
    lengths = [len(p['image_prompt']) for p in prompts]
    print(f"\n📏 프롬프트 길이:")
    print(f"  평균: {sum(lengths) / len(lengths):.0f} 문자")
    print(f"  최소: {min(lengths)} 문자")
    print(f"  최대: {max(lengths)} 문자")
    
    # 타임라인 분석
    timeline_path = os.path.join(project_root, "outputs/timeline/timeline.json")
    
    if os.path.exists(timeline_path):
        with open(timeline_path, 'r', encoding='utf-8') as f:
            timeline = json.load(f)
        
        print(f"\n⏰ 타임라인:")
        for entry in timeline:
            print(f"  {entry['timestamp']} ~ {entry['end_timestamp']}: {entry['image_id']}")


def main():
    """메인 함수"""
    print("\n🚀 Phase 3 통합 테스트 (새로운 설계)")
    print("="*80)
    
    print("\n옵션:")
    print("1. 전체 파이프라인 실행")
    print("2. 결과 분석")
    
    choice = input("\n선택 (1, 2, 기본=1): ").strip()
    
    if choice == "2":
        analyze_results()
    else:
        # 파이프라인 실행
        results = run_new_pipeline()
        
        if results:
            print("\n" + "="*80)
            input("Enter를 눌러 결과 분석 보기...")
            analyze_results()


if __name__ == "__main__":
    main()