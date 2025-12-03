"""
스크립트 파서 테스트
실제 업로드된 팟캐스트 스크립트 파일 파싱
"""

import sys
import os
from pathlib import Path

# 스크립트 파서 직접 import
sys.path.insert(0, '/mnt/user-data/outputs')

from script_parser_node import ScriptParserNode, print_scene_detail


def test_parse_uploaded_script():
    """
    업로드된 스크립트 파일 파싱 테스트
    """
    print("="*80)
    print("🧪 스크립트 파서 테스트")
    print("="*80)
    
    # 업로드된 파일 경로
    script_path = "/mnt/user-data/uploads/podcast_episode_merged_https___ai_데일리_스크럼_보고_인턴이승찬_2025_11_21_____팟캐스트_에이전트_PRD.txt"
    
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
    
    # JSON 저장
    output_dir = "./test_output/script_parser"
    os.makedirs(output_dir, exist_ok=True)
    
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


def test_filter_functions():
    """
    필터 함수 테스트
    """
    from script_parser_node import filter_by_speaker, filter_by_duration, get_total_duration
    
    print("\n" + "="*80)
    print("🧪 필터 함수 테스트")
    print("="*80)
    
    script_path = "/mnt/user-data/uploads/podcast_episode_merged_https___ai_데일리_스크럼_보고_인턴이승찬_2025_11_21_____팟캐스트_에이전트_PRD.txt"
    
    parser = ScriptParserNode()
    scenes = parser.parse_from_file(script_path)
    
    if not scenes:
        return
    
    # 화자별 필터
    print("\n🎤 화자별 필터:")
    for speaker in set(s.speaker for s in scenes):
        speaker_scenes = filter_by_speaker(scenes, speaker)
        duration = get_total_duration(speaker_scenes)
        print(f"  {speaker}: {len(speaker_scenes)}개 장면, {duration}초")
    
    # Duration 필터
    print("\n⏱️  Duration 필터:")
    
    short_scenes = filter_by_duration(scenes, max_duration=10)
    print(f"  짧은 장면 (≤10초): {len(short_scenes)}개")
    
    medium_scenes = filter_by_duration(scenes, min_duration=11, max_duration=20)
    print(f"  중간 장면 (11-20초): {len(medium_scenes)}개")
    
    long_scenes = filter_by_duration(scenes, min_duration=21)
    print(f"  긴 장면 (≥21초): {len(long_scenes)}개")


def test_langgraph_node():
    """
    LangGraph 노드 인터페이스 테스트
    """
    print("\n" + "="*80)
    print("🧪 LangGraph 노드 테스트")
    print("="*80)
    
    parser = ScriptParserNode()
    
    # State 준비
    state = {
        "script_path": "/mnt/user-data/uploads/podcast_episode_merged_https___ai_데일리_스크럼_보고_인턴이승찬_2025_11_21_____팟캐스트_에이전트_PRD.txt"
    }
    
    # 노드 실행
    result_state = parser(state)
    
    print(f"\n✅ 노드 실행 완료")
    print(f"  총 장면: {result_state['total_scenes']}개")
    print(f"  총 길이: {result_state['total_duration']}초")
    
    return result_state


if __name__ == "__main__":
    # 1. 기본 파싱 테스트
    scenes = test_parse_uploaded_script()
    
    # 2. 필터 함수 테스트
    test_filter_functions()
    
    # 3. LangGraph 노드 테스트
    test_langgraph_node()
