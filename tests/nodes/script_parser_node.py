"""
스크립트 파싱 노드 (LangGraph)
타임스탬프 포함 팟캐스트 스크립트를 구조화된 Scene 데이터로 변환
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json


@dataclass
class PodcastScene:
    """팟캐스트 장면 (이미지 매핑 단위)"""
    scene_id: str              # "scene_001"
    timestamp_start: str       # "00:00:00"
    timestamp_end: str         # "00:00:24"
    duration: int              # 24 (초)
    
    # 스크립트 정보
    speaker: str               # "진행자" or "게스트"
    text: str                  # 발화 내용
    
    # 이미지 정보 (나중에 채워짐)
    image_required: bool = False
    image_title: Optional[str] = None
    image_prompt: Optional[str] = None
    image_style: Optional[str] = None
    image_path: Optional[str] = None
    
    # 메타데이터
    importance: float = 0.5
    context: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PodcastScene':
        """딕셔너리에서 생성"""
        return cls(**data)


class ScriptParserNode:
    """
    타임스탬프 포함 팟캐스트 스크립트 파싱 노드
    
    입력 형식:
    [00:00:00] [진행자]: 안녕하세요! 지식 탐험가 여러분...
    [00:00:24] [게스트]: 네, 안녕하세요...
    
    출력: PodcastScene 리스트
    """
    
    def __init__(self):
        # 정규식 패턴
        # [HH:MM:SS] [화자]: 내용
        self.pattern = re.compile(
            r'\[(\d{2}:\d{2}:\d{2})\]\s*\[([^\]]+)\]:\s*(.+?)(?=\[\d{2}:\d{2}:\d{2}\]|$)',
            re.DOTALL
        )
    
    def parse_from_file(self, file_path: str) -> List[PodcastScene]:
        """
        파일에서 스크립트 읽고 파싱
        
        Args:
            file_path: 스크립트 파일 경로 (txt)
        
        Returns:
            PodcastScene 리스트
        """
        print(f"\n📄 스크립트 파일 읽기: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                script_text = f.read()
            
            print(f"✅ 파일 읽기 완료 ({len(script_text)} 문자)")
            
            return self.parse_from_text(script_text)
        
        except FileNotFoundError:
            print(f"❌ 파일을 찾을 수 없습니다: {file_path}")
            return []
        except Exception as e:
            print(f"❌ 파일 읽기 실패: {str(e)}")
            return []
    
    def parse_from_text(self, script_text: str) -> List[PodcastScene]:
        """
        텍스트에서 스크립트 파싱
        
        Args:
            script_text: 스크립트 전체 텍스트
        
        Returns:
            PodcastScene 리스트
        """
        print("\n🔍 스크립트 파싱 시작")
        
        # 정규식으로 매칭
        matches = self.pattern.findall(script_text)
        
        if not matches:
            print("⚠️  매칭된 장면이 없습니다. 형식을 확인하세요.")
            return []
        
        print(f"✅ {len(matches)}개 장면 발견")
        
        scenes = []
        
        for i, (timestamp, speaker, text) in enumerate(matches):
            # 다음 장면의 타임스탬프 (마지막이면 None)
            next_timestamp = matches[i + 1][0] if i + 1 < len(matches) else None
            
            # duration 계산
            duration = self._calculate_duration(timestamp, next_timestamp)
            
            # timestamp_end 계산
            timestamp_end = next_timestamp if next_timestamp else self._add_seconds(timestamp, duration)
            
            # PodcastScene 생성
            scene = PodcastScene(
                scene_id=f"scene_{i + 1:03d}",
                timestamp_start=timestamp,
                timestamp_end=timestamp_end,
                duration=duration,
                speaker=speaker.strip(),
                text=text.strip(),
                image_required=False,  # 기본값, 나중에 AI가 판단
                importance=0.5,
                context=""
            )
            
            scenes.append(scene)
        
        print(f"\n📊 파싱 완료:")
        print(f"  총 장면: {len(scenes)}개")
        print(f"  총 길이: {self._format_duration(sum(s.duration for s in scenes))}")
        print(f"  화자 수: {len(set(s.speaker for s in scenes))}명")
        
        return scenes
    
    def _calculate_duration(self, start_time: str, end_time: Optional[str]) -> int:
        """
        두 타임스탬프 사이의 duration 계산 (초)
        
        Args:
            start_time: "00:00:00" 형식
            end_time: "00:00:24" 형식 또는 None
        
        Returns:
            duration in seconds
        """
        if end_time is None:
            # 마지막 장면이면 기본 30초
            return 30
        
        start_seconds = self._time_to_seconds(start_time)
        end_seconds = self._time_to_seconds(end_time)
        
        return end_seconds - start_seconds
    
    def _time_to_seconds(self, time_str: str) -> int:
        """
        "HH:MM:SS" → 초 변환
        
        Args:
            time_str: "00:01:30" 형식
        
        Returns:
            총 초
        """
        h, m, s = map(int, time_str.split(':'))
        return h * 3600 + m * 60 + s
    
    def _seconds_to_time(self, seconds: int) -> str:
        """
        초 → "HH:MM:SS" 변환
        
        Args:
            seconds: 총 초
        
        Returns:
            "HH:MM:SS" 형식
        """
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    
    def _add_seconds(self, time_str: str, seconds: int) -> str:
        """
        타임스탬프에 초 더하기
        
        Args:
            time_str: "00:00:00" 형식
            seconds: 더할 초
        
        Returns:
            새 타임스탬프
        """
        total_seconds = self._time_to_seconds(time_str) + seconds
        return self._seconds_to_time(total_seconds)
    
    def _format_duration(self, seconds: int) -> str:
        """
        초를 읽기 쉬운 형식으로 (예: "6분 20초")
        
        Args:
            seconds: 총 초
        
        Returns:
            "X분 Y초" 형식
        """
        m = seconds // 60
        s = seconds % 60
        return f"{m}분 {s}초"
    
    def save_to_json(self, scenes: List[PodcastScene], output_path: str):
        """
        장면 리스트를 JSON으로 저장
        
        Args:
            scenes: PodcastScene 리스트
            output_path: 저장 경로
        """
        print(f"\n💾 JSON 저장: {output_path}")
        
        data = {
            "total_scenes": len(scenes),
            "total_duration": sum(s.duration for s in scenes),
            "speakers": list(set(s.speaker for s in scenes)),
            "scenes": [scene.to_dict() for scene in scenes]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 저장 완료")
    
    def load_from_json(self, input_path: str) -> List[PodcastScene]:
        """
        JSON에서 장면 리스트 로드
        
        Args:
            input_path: JSON 파일 경로
        
        Returns:
            PodcastScene 리스트
        """
        print(f"\n📂 JSON 로드: {input_path}")
        
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        scenes = [PodcastScene.from_dict(scene_data) for scene_data in data['scenes']]
        
        print(f"✅ {len(scenes)}개 장면 로드")
        
        return scenes
    
    def print_summary(self, scenes: List[PodcastScene]):
        """
        장면 요약 출력
        
        Args:
            scenes: PodcastScene 리스트
        """
        print("\n" + "="*80)
        print("📊 스크립트 요약")
        print("="*80)
        
        total_duration = sum(s.duration for s in scenes)
        speakers = list(set(s.speaker for s in scenes))
        
        print(f"\n📝 기본 정보:")
        print(f"  총 장면: {len(scenes)}개")
        print(f"  총 길이: {self._format_duration(total_duration)}")
        print(f"  화자: {', '.join(speakers)} ({len(speakers)}명)")
        
        print(f"\n🎬 장면별 정보:")
        print(f"{'ID':<12} {'시작':<10} {'길이':<6} {'화자':<10} {'내용 미리보기':<50}")
        print("-" * 88)
        
        for scene in scenes[:10]:  # 처음 10개만
            preview = scene.text[:47] + "..." if len(scene.text) > 50 else scene.text
            print(f"{scene.scene_id:<12} {scene.timestamp_start:<10} {scene.duration:>4}초 {scene.speaker:<10} {preview}")
        
        if len(scenes) > 10:
            print(f"... (총 {len(scenes)}개 중 10개 표시)")
        
        print("="*80)
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph 노드로 실행
        
        Args:
            state: {
                "script_path": str,  # 스크립트 파일 경로
            }
        
        Returns:
            state with scenes added
        """
        script_path = state.get("script_path")
        
        if not script_path:
            print("❌ script_path가 제공되지 않았습니다.")
            return {**state, "scenes": [], "error": "No script_path provided"}
        
        # 파일에서 파싱
        scenes = self.parse_from_file(script_path)
        
        # 요약 출력
        if scenes:
            self.print_summary(scenes)
        
        return {
            **state,
            "scenes": scenes,
            "total_scenes": len(scenes),
            "total_duration": sum(s.duration for s in scenes)
        }


# ============================================================================
# 헬퍼 함수들
# ============================================================================

def print_scene_detail(scene: PodcastScene):
    """단일 장면 상세 출력"""
    print(f"\n{'='*80}")
    print(f"🎬 {scene.scene_id}")
    print(f"{'='*80}")
    print(f"⏰ 시간: {scene.timestamp_start} → {scene.timestamp_end} ({scene.duration}초)")
    print(f"🎤 화자: {scene.speaker}")
    print(f"💬 내용:\n{scene.text}")
    if scene.image_required:
        print(f"\n🖼️  이미지:")
        print(f"  제목: {scene.image_title}")
        print(f"  스타일: {scene.image_style}")
        print(f"  프롬프트: {scene.image_prompt[:100]}...")
    print(f"{'='*80}")


def filter_by_speaker(scenes: List[PodcastScene], speaker: str) -> List[PodcastScene]:
    """특정 화자의 장면만 필터링"""
    return [s for s in scenes if s.speaker == speaker]


def filter_by_duration(scenes: List[PodcastScene], min_duration: int = 0, max_duration: int = 999) -> List[PodcastScene]:
    """duration 범위로 필터링"""
    return [s for s in scenes if min_duration <= s.duration <= max_duration]


def get_total_duration(scenes: List[PodcastScene]) -> int:
    """총 duration 계산 (초)"""
    return sum(s.duration for s in scenes)


if __name__ == "__main__":
    # 테스트
    parser = ScriptParserNode()
    
    # 샘플 스크립트
    sample_script = """[00:00:00] [진행자]: 안녕하세요! 지식 탐험가 여러분, 스마트 지식 라디오입니다.
[00:00:24] [게스트]: 네, 안녕하세요. 여러분의 지식 습득을 더욱 쉽고 즐겁게 만들어 줄 기술에 대해 이야기하게 되어 기쁩니다.
[00:00:33] [진행자]: 와, 듣기만 해도 벌써부터 귀가 솔깃해지는데요!"""
    
    scenes = parser.parse_from_text(sample_script)
    parser.print_summary(scenes)
    
    if scenes:
        print_scene_detail(scenes[0])
