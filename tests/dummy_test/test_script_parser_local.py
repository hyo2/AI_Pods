"""
스크립트 파서 테스트 (로컬 환경용)
"""

import sys
import os
from pathlib import Path

# 현재 스크립트 위치 기준으로 프로젝트 루트 찾기
current_dir = Path(__file__).parent
project_root = current_dir.parent if current_dir.name == "tests" else current_dir

# app/nodes 경로 추가
sys.path.insert(0, str(project_root))

try:
    from app.nodes.script_parser_node import ScriptParserNode, print_scene_detail
    print("✅ app.nodes에서 import 성공")
except ImportError:
    # app/nodes에 없으면 현재 디렉토리에서
    try:
        from script_parser_node import ScriptParserNode, print_scene_detail
        print("✅ 현재 디렉토리에서 import 성공")
    except ImportError:
        print("❌ script_parser_node를 찾을 수 없습니다.")
        print(f"현재 경로: {os.getcwd()}")
        print(f"sys.path: {sys.path[:3]}")
        sys.exit(1)


def test_with_sample_script():
    """
    샘플 스크립트로 테스트
    """
    print("="*80)
    print("🧪 스크립트 파서 테스트 (샘플)")
    print("="*80)
    
    # 샘플 스크립트 경로 찾기
    possible_paths = [
        "data/sample_scripts/podcast_script_sample.txt",
        "sample_podcast_script.txt",
        "outputs/sample_podcast_script.txt",
        os.path.join(project_root, "data/sample_scripts/podcast_script_sample.txt"),
        os.path.join(project_root, "sample_podcast_script.txt"),
    ]
    
    script_path = None
    for path in possible_paths:
        if os.path.exists(path):
            script_path = path
            break
    
    if not script_path:
        print("\n⚠️  샘플 스크립트를 찾을 수 없습니다.")
        print("다음 중 한 곳에 스크립트 파일을 넣어주세요:")
        for path in possible_paths[:3]:
            print(f"  - {path}")
        print("\n📝 샘플 스크립트 형식:")
        print("[00:00:00] [진행자]: 안녕하세요!")
        print("[00:00:24] [게스트]: 네, 안녕하세요.")
        return
    
    print(f"\n📄 사용할 스크립트: {script_path}")
    
    # 파서 초기화
    parser = ScriptParserNode()
    
    # 파일에서 파싱
    scenes = parser.parse_from_file(script_path)
    
    if not scenes:
        print("❌ 파싱 실패!")
        return
    
    # 요약 출력
    parser.print_summary(scenes)
    
    # 처음 3개 장면 상세 출력
    print("\n" + "="*80)
    print("📝 장면 상세 (처음 3개)")
    print("="*80)
    
    for scene in scenes[:3]:
        print_scene_detail(scene)
    
    # 출력 디렉토리 생성
    output_dir = os.path.join(project_root, "outputs", "parsed_scripts")
    os.makedirs(output_dir, exist_ok=True)
    
    # JSON 저장
    json_path = os.path.join(output_dir, "parsed_scenes.json")
    parser.save_to_json(scenes, json_path)
    
    print(f"\n💾 JSON 저장 완료: {json_path}")
    
    # JSON 다시 로드 테스트
    print("\n🔄 JSON 로드 테스트...")
    loaded_scenes = parser.load_from_json(json_path)
    
    print(f"✅ {len(loaded_scenes)}개 장면 로드 성공")
    
    # 통계
    print("\n" + "="*80)
    print("📊 통계")
    print("="*80)
    
    from collections import Counter
    
    speaker_counts = Counter(s.speaker for s in scenes)
    print(f"\n화자별 발화 횟수:")
    for speaker, count in speaker_counts.items():
        print(f"  {speaker}: {count}회")
    
    durations = [s.duration for s in scenes]
    print(f"\n장면 길이:")
    print(f"  평균: {sum(durations) / len(durations):.1f}초")
    print(f"  최소: {min(durations)}초")
    print(f"  최대: {max(durations)}초")
    
    print("\n" + "="*80)
    print("✅ 테스트 완료!")
    print("="*80)
    
    return scenes


def test_with_custom_script():
    """
    사용자가 제공한 스크립트로 테스트
    """
    print("\n" + "="*80)
    print("🧪 커스텀 스크립트 테스트")
    print("="*80)
    
    print("\n스크립트 파일 경로를 입력하세요:")
    print("(예: C:\\Users\\USER\\Desktop\\script.txt)")
    print("또는 Enter를 눌러 샘플 스크립트로 진행")
    
    custom_path = input("\n파일 경로: ").strip()
    
    if not custom_path:
        print("샘플 스크립트로 진행합니다...")
        return test_with_sample_script()
    
    if not os.path.exists(custom_path):
        print(f"❌ 파일을 찾을 수 없습니다: {custom_path}")
        return
    
    parser = ScriptParserNode()
    scenes = parser.parse_from_file(custom_path)
    
    if scenes:
        parser.print_summary(scenes)
        
        # JSON 저장
        output_dir = os.path.join(project_root, "outputs", "parsed_scripts")
        os.makedirs(output_dir, exist_ok=True)
        
        filename = Path(custom_path).stem
        json_path = os.path.join(output_dir, f"{filename}_parsed.json")
        parser.save_to_json(scenes, json_path)
        
        print(f"\n💾 JSON 저장: {json_path}")
    
    return scenes


def main():
    """메인 함수"""
    print("\n🚀 스크립트 파서 테스트")
    print("="*80)
    print(f"프로젝트 루트: {project_root}")
    print(f"현재 디렉토리: {os.getcwd()}")
    print("="*80)
    
    # 메뉴
    print("\n테스트 옵션:")
    print("1. 샘플 스크립트로 테스트")
    print("2. 커스텀 스크립트로 테스트")
    
    choice = input("\n선택 (1 or 2, 기본=1): ").strip()
    
    if choice == "2":
        test_with_custom_script()
    else:
        test_with_sample_script()


if __name__ == "__main__":
    main()
