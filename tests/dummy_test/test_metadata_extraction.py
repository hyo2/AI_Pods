"""
Phase 3-0 테스트: 메타데이터 추출 노드
전체 스크립트 → Global Visual + Content Analysis
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 찾기
current_dir = Path(__file__).parent
project_root = current_dir.parent if current_dir.name == "tests" else current_dir

sys.path.insert(0, str(project_root))

# Import
try:
    from app.nodes.script_parser_node import ScriptParserNode
    from app.nodes.metadata_extraction_node import (
        MetadataExtractionNode,
        save_metadata,
        print_metadata_summary
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
        print("✅ 현재 디렉토리에서 import 성공")
    except ImportError as e:
        print(f"❌ Import 실패: {str(e)}")
        sys.exit(1)


def test_metadata_from_json():
    """
    Phase 3-1 결과(JSON)에서 메타데이터 추출
    """
    print("="*80)
    print("🧪 Phase 3-0 테스트: 메타데이터 추출")
    print("="*80)
    
    # Phase 3-1 JSON 찾기
    possible_paths = [
        "outputs/parsed_scripts/parsed_scenes.json",
        os.path.join(project_root, "outputs/parsed_scripts/parsed_scenes.json"),
    ]
    
    json_path = None
    for path in possible_paths:
        if os.path.exists(path):
            json_path = path
            break
    
    if not json_path:
        print("\n⚠️  Phase 3-1 결과를 찾을 수 없습니다.")
        print("먼저 test_script_parser_local.py를 실행하세요.")
        return None
    
    print(f"\n📂 Phase 3-1 결과 로드: {json_path}")
    
    # 장면 로드
    parser = ScriptParserNode()
    scenes = parser.load_from_json(json_path)
    
    print(f"✅ {len(scenes)}개 장면 로드 완료")
    
    # 메타데이터 추출 노드 초기화
    print("\n🔍 메타데이터 추출 노드 초기화...")
    extractor = MetadataExtractionNode(
        project_id="alan-document-lab",
        location="us-central1",
        model_name="gemini-2.5-flash"
    )
    
    # 메타데이터 추출
    print("\n🤖 AI가 전체 스크립트를 분석합니다...")
    print("(이 작업은 30초-1분 소요됩니다)")
    
    metadata = extractor.extract_metadata(scenes)
    
    # 요약 출력
    print_metadata_summary(metadata)
    
    # 저장
    output_dir = os.path.join(project_root, "outputs", "metadata")
    os.makedirs(output_dir, exist_ok=True)
    
    metadata_path = os.path.join(output_dir, "podcast_metadata.json")
    save_metadata(metadata, metadata_path)
    
    # 상세 출력
    print("\n" + "="*80)
    print("📊 상세 정보")
    print("="*80)
    
    # Visual Guidelines 상세
    print("\n🎨 Visual Guidelines (상세):")
    print(f"\n  아트 스타일:")
    print(f"    메인: {metadata.visual.art_style}")
    print(f"    상세: {metadata.visual.art_style_details}")
    
    print(f"\n  색상 팔레트:")
    print(f"    Primary: {metadata.visual.color_palette.primary}")
    print(f"    Secondary: {metadata.visual.color_palette.secondary}")
    print(f"    Accent: {metadata.visual.color_palette.accent}")
    print(f"    Background: {metadata.visual.color_palette.background}")
    print(f"    Text Safe: {metadata.visual.color_palette.text_safe}")
    
    print(f"\n  구도 규칙 (텍스트 오버레이):")
    print(f"    위치: {metadata.visual.composition_rules.text_position}")
    print(f"    안전 영역: {metadata.visual.composition_rules.safe_zone}")
    print(f"    선호: {metadata.visual.composition_rules.preference}")
    print(f"    피할 것: {metadata.visual.composition_rules.avoid}")
    
    print(f"\n  반복 요소:")
    for key, value in metadata.visual.recurring_elements.items():
        print(f"    {key}: {value}")
    
    # Chapters 상세
    print(f"\n📚 챕터 상세:")
    for i, ch in enumerate(metadata.content.chapters, 1):
        print(f"\n  [{i}] {ch.title}")
        print(f"      시간: {ch.start_time} ~ {ch.end_time} ({ch.duration}초)")
        print(f"      장면: {len(ch.scene_ids)}개 ({', '.join(ch.scene_ids[:3])}...)")
        print(f"      주제: {', '.join(ch.key_topics)}")
        print(f"      요약: {ch.summary}")
        print(f"      중요도: {ch.importance:.2f}")
        print(f"      예상 이미지: {ch.expected_images}개")
    
    # Key Concepts 상세
    print(f"\n🔑 핵심 개념 상세:")
    for kc in metadata.content.key_concepts:
        print(f"\n  - {kc.term}")
        if kc.full_name:
            print(f"    전체 이름: {kc.full_name}")
        print(f"    첫 등장: {kc.first_appearance}")
        print(f"    중요도: {kc.importance:.2f}")
        print(f"    시각화: {'✅ 필요' if kc.should_visualize else '❌ 불필요'}")
        if kc.should_visualize:
            print(f"    우선순위: {kc.visual_priority}")
    
    # Critical Moments 상세
    if metadata.content.critical_moments:
        print(f"\n⚡ 임계 순간 상세:")
        for cm in metadata.content.critical_moments:
            print(f"\n  [{cm.timestamp}] {cm.scene_id}")
            print(f"    타입: {cm.type}")
            print(f"    설명: {cm.description}")
    
    print("\n" + "="*80)
    print("✅ Phase 3-0 완료!")
    print("="*80)
    
    return metadata


def test_full_pipeline():
    """
    스크립트부터 전체 파이프라인 실행
    """
    print("="*80)
    print("🧪 전체 파이프라인 (Phase 3-1 + 3-0)")
    print("="*80)
    
    # 샘플 스크립트 찾기
    possible_paths = [
        "data/sample_scripts/podcast_script_sample.txt",
        os.path.join(project_root, "data/sample_scripts/podcast_script_sample.txt"),
    ]
    
    script_path = None
    for path in possible_paths:
        if os.path.exists(path):
            script_path = path
            break
    
    if not script_path:
        print("\n⚠️  샘플 스크립트를 찾을 수 없습니다.")
        return
    
    # Phase 3-1: 파싱
    print("\n" + "="*80)
    print("📄 Phase 3-1: 스크립트 파싱")
    print("="*80)
    
    parser = ScriptParserNode()
    scenes = parser.parse_from_file(script_path)
    
    if not scenes:
        print("❌ 파싱 실패")
        return
    
    parser.print_summary(scenes)
    
    # Phase 3-0: 메타데이터 추출
    print("\n" + "="*80)
    print("🔍 Phase 3-0: 메타데이터 추출")
    print("="*80)
    
    extractor = MetadataExtractionNode()
    metadata = extractor.extract_metadata(scenes)
    
    print_metadata_summary(metadata)
    
    # 저장
    output_dir = os.path.join(project_root, "outputs", "metadata")
    os.makedirs(output_dir, exist_ok=True)
    
    metadata_path = os.path.join(output_dir, "full_pipeline_metadata.json")
    save_metadata(metadata, metadata_path)
    
    print("\n" + "="*80)
    print("✅ 전체 파이프라인 완료!")
    print("="*80)


def analyze_metadata(metadata_path: str):
    """
    저장된 메타데이터 분석
    """
    import json
    
    print("\n" + "="*80)
    print("📊 메타데이터 분석")
    print("="*80)
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    content = data['content']
    visual = data['visual']
    
    print(f"\n📈 통계:")
    print(f"  전체 길이: {content['total_duration']}")
    print(f"  전체 장면: {content['total_scenes']}개")
    print(f"  챕터: {len(content['chapters'])}개")
    print(f"  핵심 개념: {len(content['key_concepts'])}개")
    
    # 챕터별 예상 이미지
    print(f"\n📚 챕터별 이미지 배분:")
    total_expected = 0
    for ch in content['chapters']:
        print(f"  {ch['title']}: {ch['expected_images']}개 (중요도: {ch['importance']:.2f})")
        total_expected += ch['expected_images']
    
    print(f"\n  총 예상 이미지: {total_expected}개")
    
    # 시각화 필요 개념
    print(f"\n🎨 시각화 필요 개념:")
    visualize_needed = [kc for kc in content['key_concepts'] if kc['should_visualize']]
    for kc in visualize_needed:
        print(f"  - {kc['term']} (우선순위: {kc['visual_priority']})")
    
    # Visual 스타일 요약
    print(f"\n🎨 비주얼 스타일:")
    print(f"  스타일: {visual['art_style']}")
    print(f"  무드: {visual['overall_mood']}")
    print(f"  주 색상: {visual['color_palette']['primary']}")
    print(f"  텍스트 위치: {visual['composition_rules']['text_position']}")


def main():
    """메인 함수"""
    print("\n🚀 Phase 3-0: 메타데이터 추출 테스트")
    print("="*80)
    
    print("\n테스트 옵션:")
    print("1. Phase 3-1 결과(JSON)에서 시작 (빠름, 추천)")
    print("2. 스크립트부터 전체 실행 (느림)")
    print("3. 저장된 메타데이터 분석")
    
    choice = input("\n선택 (1, 2, 3, 기본=1): ").strip()
    
    if choice == "2":
        test_full_pipeline()
    
    elif choice == "3":
        metadata_path = os.path.join(project_root, "outputs/metadata/podcast_metadata.json")
        if os.path.exists(metadata_path):
            analyze_metadata(metadata_path)
        else:
            print(f"❌ 메타데이터를 찾을 수 없습니다: {metadata_path}")
            print("먼저 옵션 1 또는 2를 실행하세요.")
    
    else:
        # 옵션 1 (기본)
        metadata = test_metadata_from_json()
        
        # 분석도 함께
        if metadata:
            metadata_path = os.path.join(project_root, "outputs/metadata/podcast_metadata.json")
            if os.path.exists(metadata_path):
                analyze_metadata(metadata_path)


if __name__ == "__main__":
    main()
