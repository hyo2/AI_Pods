"""
Phase 3-2 테스트: 장면 선택 노드
파싱된 장면 → AI 판단 → 이미지 필요 장면 선택
"""

import sys
import os
from pathlib import Path

# 현재 스크립트 위치 기준으로 프로젝트 루트 찾기
current_dir = Path(__file__).parent
project_root = current_dir.parent if current_dir.name == "tests" else current_dir

# app/nodes 경로 추가
sys.path.insert(0, str(project_root))

# Import 시도
try:
    from app.nodes.script_parser_node import ScriptParserNode, PodcastScene
    from app.nodes.scene_selection_node import SceneSelectionNode, print_selected_scenes, export_selection_report
    print("✅ app.nodes에서 import 성공")
except ImportError:
    # 현재 디렉토리에서
    try:
        sys.path.insert(0, str(current_dir))
        from script_parser_node import ScriptParserNode, PodcastScene
        from scene_selection_node import SceneSelectionNode, print_selected_scenes, export_selection_report
        print("✅ 현재 디렉토리에서 import 성공")
    except ImportError as e:
        print(f"❌ Import 실패: {str(e)}")
        print("필요한 파일: script_parser_node.py, scene_selection_node.py")
        sys.exit(1)


def test_scene_selection_from_json():
    """
    Phase 3-1 결과(JSON)를 로드하여 Phase 3-2 실행
    """
    print("="*80)
    print("🧪 Phase 3-2 테스트: 장면 선택")
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
        print("\n⚠️  Phase 3-1 결과(parsed_scenes.json)를 찾을 수 없습니다.")
        print("먼저 test_script_parser_local.py를 실행하세요.")
        return None, None
    
    print(f"\n📂 Phase 3-1 결과 로드: {json_path}")
    
    # 파서로 JSON 로드
    parser = ScriptParserNode()
    scenes = parser.load_from_json(json_path)
    
    print(f"✅ {len(scenes)}개 장면 로드 완료")
    
    # 장면 선택 노드 초기화
    print("\n🎬 장면 선택 노드 초기화...")
    selector = SceneSelectionNode(
        project_id="alan-document-lab",
        location="us-central1",
        model_name="gemini-2.5-flash"
    )
    
    # 장면 선택 실행
    print("\n🤖 AI가 각 장면을 분석합니다...")
    print("(이 작업은 1-2분 소요됩니다)")
    
    selected_scenes = selector.select_scenes(scenes, show_progress=True)
    
    # 선택된 장면 상세 출력
    if selected_scenes:
        print_selected_scenes(selected_scenes)
    
    # 결과 저장
    output_dir = os.path.join(project_root, "outputs", "scene_selection")
    os.makedirs(output_dir, exist_ok=True)
    
    report_path = os.path.join(output_dir, "selection_report.json")
    export_selection_report(scenes, selected_scenes, report_path)
    
    print("\n" + "="*80)
    print("✅ Phase 3-2 완료!")
    print("="*80)
    
    return scenes, selected_scenes


def test_scene_selection_from_script():
    """
    스크립트 파일부터 전체 파이프라인 실행
    """
    print("="*80)
    print("🧪 전체 파이프라인 테스트 (Phase 3-1 + 3-2)")
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
        print("test_script_parser_local.py를 먼저 실행하세요.")
        return
    
    # Phase 3-1: 스크립트 파싱
    print("\n" + "="*80)
    print("📄 Phase 3-1: 스크립트 파싱")
    print("="*80)
    
    parser = ScriptParserNode()
    scenes = parser.parse_from_file(script_path)
    
    if not scenes:
        print("❌ 파싱 실패")
        return
    
    parser.print_summary(scenes)
    
    # Phase 3-2: 장면 선택
    print("\n" + "="*80)
    print("🎬 Phase 3-2: 장면 선택")
    print("="*80)
    
    selector = SceneSelectionNode(
        project_id="alan-document-lab",
        location="us-central1"
    )
    
    selected_scenes = selector.select_scenes(scenes)
    
    if selected_scenes:
        print_selected_scenes(selected_scenes)
    
    # 결과 저장
    output_dir = os.path.join(project_root, "outputs", "scene_selection")
    os.makedirs(output_dir, exist_ok=True)
    
    report_path = os.path.join(output_dir, "full_pipeline_report.json")
    export_selection_report(scenes, selected_scenes, report_path)
    
    print("\n" + "="*80)
    print("✅ 전체 파이프라인 완료!")
    print("="*80)


def analyze_selection_results(report_path: str):
    """
    선택 결과 분석
    """
    import json
    
    print("\n" + "="*80)
    print("📊 선택 결과 분석")
    print("="*80)
    
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    print(f"\n기본 정보:")
    print(f"  총 장면: {report['total_scenes']}개")
    print(f"  선택된 장면: {report['selected_scenes']}개")
    print(f"  선택 비율: {report['selection_rate']*100:.1f}%")
    print(f"  평균 간격: {report['avg_interval']:.1f}초")
    
    # 선택된 장면들
    selected = [s for s in report['scenes'] if s['image_required']]
    
    if not selected:
        print("\n⚠️  선택된 장면이 없습니다.")
        return
    
    # 콘텐츠 타입별
    print(f"\n콘텐츠 타입별 분포:")
    content_types = {}
    for s in selected:
        ctype = s.get('content_nature', 'unknown')
        content_types[ctype] = content_types.get(ctype, 0) + 1
    
    for ctype, count in sorted(content_types.items(), key=lambda x: -x[1]):
        print(f"  {ctype}: {count}개")
    
    # 시각 타입별
    print(f"\n시각 타입별 분포:")
    visual_types = {}
    for s in selected:
        vtype = s.get('visual_type', 'none')
        visual_types[vtype] = visual_types.get(vtype, 0) + 1
    
    for vtype, count in sorted(visual_types.items(), key=lambda x: -x[1]):
        print(f"  {vtype}: {count}개")
    
    # 중요도별
    print(f"\n중요도별 분포:")
    high = len([s for s in selected if s['importance'] >= 0.8])
    medium = len([s for s in selected if 0.5 <= s['importance'] < 0.8])
    low = len([s for s in selected if s['importance'] < 0.5])
    
    print(f"  높음 (≥0.8): {high}개")
    print(f"  중간 (0.5-0.8): {medium}개")
    print(f"  낮음 (<0.5): {low}개")
    
    # 타임라인
    print(f"\n⏰ 타임라인:")
    for s in selected[:10]:  # 처음 10개만
        print(f"  [{s['timestamp_start']}] {s['scene_id']}: {s['text'][:50]}...")
    
    if len(selected) > 10:
        print(f"  ... (총 {len(selected)}개)")


def main():
    """메인 함수"""
    print("\n🚀 Phase 3-2: 장면 선택 테스트")
    print("="*80)
    
    # 메뉴
    print("\n테스트 옵션:")
    print("1. Phase 3-1 결과(JSON)에서 시작 (빠름)")
    print("2. 스크립트 파일부터 전체 실행 (느림)")
    print("3. 선택 결과 분석")
    
    choice = input("\n선택 (1, 2, 3, 기본=1): ").strip()
    
    if choice == "2":
        test_scene_selection_from_script()
    
    elif choice == "3":
        report_path = os.path.join(project_root, "outputs/scene_selection/selection_report.json")
        if os.path.exists(report_path):
            analyze_selection_results(report_path)
        else:
            print(f"❌ 리포트를 찾을 수 없습니다: {report_path}")
            print("먼저 옵션 1 또는 2를 실행하세요.")
    
    else:
        # 옵션 1 (기본)
        all_scenes, selected_scenes = test_scene_selection_from_json()
        
        # 분석도 함께 실행
        if selected_scenes:
            report_path = os.path.join(project_root, "outputs/scene_selection/selection_report.json")
            if os.path.exists(report_path):
                analyze_selection_results(report_path)


if __name__ == "__main__":
    main()
