"""
통합 테스트: Phase 3-0 + 3-2 + 3-3
전체 파이프라인 - 메타데이터 → 장면 선택 → 프롬프트 생성
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
    from app.nodes.script_parser_node import ScriptParserNode
    from app.nodes.metadata_extraction_node import (
        MetadataExtractionNode,
        save_metadata,
        print_metadata_summary
    )
    from app.nodes.scene_selection_node import SceneSelectionNode
    from app.nodes.scene_description_node import (
        SceneDescriptionNode,
        print_prompts_summary,
        export_prompts
    )
    from app.nodes.image_generation_node import (
        ImageGenerationNode,
        save_generation_results,
        create_image_manifest
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
        from scene_selection_node import SceneSelectionNode
        from scene_description_node import (
            SceneDescriptionNode,
            print_prompts_summary,
            export_prompts
        )
        from image_generation_node import (
            ImageGenerationNode,
            save_generation_results,
            create_image_manifest
        )
        print("✅ 현재 디렉토리에서 import 성공")
    except ImportError as e:
        print(f"❌ Import 실패: {str(e)}")
        sys.exit(1)


def run_full_pipeline():
    """
    전체 파이프라인 실행
    Phase 3-1 → 3-0 → 3-2 → 3-3
    """
    print("\n" + "="*80)
    print("🚀 전체 파이프라인 실행")
    print("="*80)
    print("\nPhase 3-1: 스크립트 파싱")
    print("Phase 3-0: 메타데이터 추출")
    print("Phase 3-2: 장면 선택 (메타데이터 기반)")
    print("Phase 3-3: 이미지 프롬프트 생성")
    print("="*80)
    
    # ========================================================================
    # Phase 3-1: 스크립트 파싱
    # ========================================================================
    
    print("\n" + "="*80)
    print("📄 Phase 3-1: 스크립트 파싱")
    print("="*80)
    
    # JSON 로드
    json_path = os.path.join(project_root, "outputs/parsed_scripts/parsed_scenes.json")
    
    if not os.path.exists(json_path):
        print("⚠️  파싱된 스크립트를 찾을 수 없습니다.")
        print("먼저 test_script_parser_local.py를 실행하세요.")
        return
    
    parser = ScriptParserNode()
    scenes = parser.load_from_json(json_path)
    
    print(f"✅ {len(scenes)}개 장면 로드 완료")
    
    # ========================================================================
    # Phase 3-0: 메타데이터 추출
    # ========================================================================
    
    print("\n" + "="*80)
    print("🔍 Phase 3-0: 메타데이터 추출")
    print("="*80)
    
    # 프로젝트 ID 확인
    import os as os_module
    project_id = os_module.getenv("GOOGLE_CLOUD_PROJECT") or os_module.getenv("GCP_PROJECT")
    
    if not project_id:
        print("\n💡 프로젝트 ID를 입력하거나 Enter로 더미 데이터 사용")
        user_input = input("프로젝트 ID: ").strip()
        project_id = user_input if user_input else None
    
    extractor = MetadataExtractionNode(project_id=project_id)
    metadata = extractor.extract_metadata(scenes)
    
    print_metadata_summary(metadata)
    
    # 메타데이터 저장
    metadata_dir = os.path.join(project_root, "outputs", "metadata")
    os.makedirs(metadata_dir, exist_ok=True)
    metadata_path = os.path.join(metadata_dir, "podcast_metadata.json")
    save_metadata(metadata, metadata_path)
    
    # ========================================================================
    # Phase 3-2: 장면 선택 (메타데이터 기반)
    # ========================================================================
    
    print("\n" + "="*80)
    print("🎬 Phase 3-2: 메타데이터 기반 장면 선택")
    print("="*80)
    
    selector = SceneSelectionNode(project_id=project_id)
    selected_scenes = selector.select_scenes_with_metadata(
        scenes=scenes,
        metadata=metadata,
        show_progress=True
    )
    
    print(f"\n✅ {len(selected_scenes)}개 장면 선택 완료")
    
    # 선택 결과 저장
    selection_dir = os.path.join(project_root, "outputs", "scene_selection")
    os.makedirs(selection_dir, exist_ok=True)
    
    import json
    selection_data = {
        'total_scenes': len(scenes),
        'selected_scenes': len(selected_scenes),
        'scenes': [
            {
                'scene_id': s.scene_id,
                'timestamp': s.timestamp_start,
                'duration': s.duration,
                'text': s.text,
                'importance': s.importance,
                'chapter_id': getattr(s, 'chapter_id', 'unknown'),
                'reason': s.context
            }
            for s in selected_scenes
        ]
    }
    
    selection_path = os.path.join(selection_dir, "selected_scenes.json")
    with open(selection_path, 'w', encoding='utf-8') as f:
        json.dump(selection_data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 선택 결과 저장: {selection_path}")
    
    # ========================================================================
    # Phase 3-3: 이미지 프롬프트 생성
    # ========================================================================
    
    print("\n" + "="*80)
    print("🎨 Phase 3-3: 이미지 프롬프트 생성")
    print("="*80)
    
    describer = SceneDescriptionNode(project_id=project_id)
    scenes_with_prompts = describer.generate_prompts_for_scenes(
        scenes=selected_scenes,
        metadata=metadata,
        show_progress=True
    )
    
    # 프롬프트 출력
    print_prompts_summary(scenes_with_prompts)
    
    # 프롬프트 저장
    prompts_dir = os.path.join(project_root, "outputs", "image_prompts")
    os.makedirs(prompts_dir, exist_ok=True)
    prompts_path = os.path.join(prompts_dir, "image_prompts.json")
    export_prompts(scenes_with_prompts, prompts_path)
    
    # ========================================================================
    # Phase 4: 이미지 생성 (선택 사항)
    # ========================================================================
    
    print("\n" + "="*80)
    print("🖼️  Phase 4: 이미지 생성 (Gemini 2.5 Flash Image - Vertex AI)")
    print("="*80)
    
    # 이미지 생성 여부 확인
    generate = input("\n이미지 생성하시겠습니까? (y/n, 기본=y): ").strip().lower()
    
    if generate != 'n':
        generator = ImageGenerationNode()  # project_id 자동 탐지
        
        if not generator.client:
            print("⚠️  초기화 실패 - Phase 4 스킵")
            image_results = None
            results_path = None
            manifest_path = None
        else:
            # 프롬프트 데이터 변환
            prompts_data = [
                {
                    'scene_id': s.scene_id,
                    'timestamp': s.timestamp_start,
                    'duration': s.duration,
                    'image_title': s.image_title,
                    'image_prompt': s.image_prompt
                }
                for s in scenes_with_prompts
            ]
            
            # 이미지 생성
            image_results = generator.generate_images_from_prompts(
                prompts_data=prompts_data,
                show_progress=True
            )
            
            # 결과 저장
            results_dir = os.path.join(project_root, "outputs", "generation_results")
            os.makedirs(results_dir, exist_ok=True)
            
            results_path = os.path.join(results_dir, "generation_results.json")
            save_generation_results(image_results, results_path)
            
            manifest = create_image_manifest(image_results)
            manifest_path = os.path.join(results_dir, "image_manifest.json")
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
            
            print(f"💾 매니페스트 저장: {manifest_path}")
    else:
        print("⚠️  Phase 4 스킵")
        image_results = None
        results_path = None
        manifest_path = None
    
    # ========================================================================
    # 최종 요약
    # ========================================================================
    
    print("\n" + "="*80)
    print("🎉 전체 파이프라인 완료!")
    print("="*80)
    
    print(f"\n📊 최종 결과:")
    print(f"  입력: {len(scenes)}개 장면")
    print(f"  선택: {len(selected_scenes)}개 장면")
    print(f"  프롬프트 생성: {len(scenes_with_prompts)}개")
    
    if image_results:
        success_count = sum(1 for r in image_results if r['success'])
        print(f"  이미지 생성: {success_count}개")
    
    print(f"\n📁 생성된 파일:")
    print(f"  - 메타데이터: {metadata_path}")
    print(f"  - 선택 결과: {selection_path}")
    print(f"  - 이미지 프롬프트: {prompts_path}")
    
    if image_results:
        print(f"  - 이미지: outputs/images/*.png ({success_count}개)")
        print(f"  - 생성 결과: {results_path}")
        print(f"  - 매니페스트: {manifest_path}")
    
    print("\n" + "="*80)
    
    return {
        'scenes': scenes,
        'metadata': metadata,
        'selected_scenes': selected_scenes,
        'scenes_with_prompts': scenes_with_prompts,
        'image_results': image_results
    }


def analyze_results():
    """
    저장된 결과 분석
    """
    print("\n" + "="*80)
    print("📊 결과 분석")
    print("="*80)
    
    prompts_path = os.path.join(project_root, "outputs/image_prompts/image_prompts.json")
    
    if not os.path.exists(prompts_path):
        print("❌ 프롬프트 파일을 찾을 수 없습니다.")
        print("먼저 전체 파이프라인을 실행하세요.")
        return
    
    import json
    with open(prompts_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n📈 통계:")
    print(f"  총 이미지: {len(data)}개")
    
    # 타임라인
    print(f"\n⏰ 타임라인:")
    for i, item in enumerate(data, 1):
        print(f"  {i}. [{item['timestamp']}] {item['scene_id']}")
        print(f"     {item['image_title'][:80]}...")
    
    # 프롬프트 길이 분석
    prompt_lengths = [len(item['image_prompt'].split()) for item in data]
    avg_length = sum(prompt_lengths) / len(prompt_lengths) if prompt_lengths else 0
    
    print(f"\n📝 프롬프트 분석:")
    print(f"  평균 길이: {avg_length:.1f} 단어")
    print(f"  최소 길이: {min(prompt_lengths)} 단어")
    print(f"  최대 길이: {max(prompt_lengths)} 단어")
    
    # 샘플 프롬프트 출력
    if data:
        print(f"\n🎨 샘플 프롬프트:")
        sample = data[0]
        print(f"\n장면: {sample['scene_id']} [{sample['timestamp']}]")
        print(f"컨셉: {sample['image_title']}")
        print(f"\n프롬프트:")
        print(sample['image_prompt'])


def main():
    """메인 함수"""
    print("\n🚀 통합 테스트: 전체 파이프라인")
    print("="*80)
    
    print("\n옵션:")
    print("1. 전체 파이프라인 실행 (Phase 3-1 → 3-0 → 3-2 → 3-3)")
    print("2. 결과 분석")
    
    choice = input("\n선택 (1, 2, 기본=1): ").strip()
    
    if choice == "2":
        analyze_results()
    else:
        # 전체 파이프라인 실행
        result = run_full_pipeline()
        
        # 결과 분석도 함께
        if result:
            print("\n" + "="*80)
            input("Enter를 눌러 결과 분석 보기...")
            analyze_results()


if __name__ == "__main__":
    main()