"""
타임스탬프 매퍼 (LangGraph)
이미지 계획을 타임라인에 매핑
"""

import json
from typing import List, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class TimelineEntry:
    """타임라인 항목"""
    timestamp: str  # HH:MM:SS
    image_id: str
    duration: int  # 초
    end_timestamp: str  # HH:MM:SS


def timestamp_to_seconds(timestamp: str) -> int:
    """
    타임스탬프를 초로 변환
    
    Args:
        timestamp: "HH:MM:SS" or "MM:SS"
    
    Returns:
        총 초
    """
    parts = timestamp.split(':')
    
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + int(seconds)
    else:
        return 0


def seconds_to_timestamp(seconds: int) -> str:
    """
    초를 타임스탬프로 변환
    
    Args:
        seconds: 총 초
    
    Returns:
        "HH:MM:SS" 형식
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class TimestampMapper:
    """
    타임스탬프 매퍼
    
    기능:
    1. 이미지 계획 → 타임라인 매핑
    2. 겹치지 않는 타임스탬프 배치
    3. 타임라인 검증
    """
    
    def __init__(self):
        """타임스탬프 매퍼 초기화"""
        pass
    
    def create_timeline(
        self,
        image_plans: List[Dict[str, Any]]
    ) -> List[TimelineEntry]:
        """
        이미지 계획으로부터 타임라인 생성
        
        Args:
            image_plans: 이미지 계획 리스트 (또는 프롬프트 리스트)
        
        Returns:
            타임라인 항목 리스트
        """
        print("\n" + "="*80)
        print("⏰ 타임라인 생성 중...")
        print("="*80)
        
        timeline = []
        
        for plan in image_plans:
            # primary_timestamp 추출
            timestamp = plan.get('primary_timestamp')
            image_id = plan.get('image_id')
            duration = plan.get('duration', 20)
            
            if not timestamp or not image_id:
                print(f"⚠️  {plan} - 타임스탬프 또는 ID 없음, 스킵")
                continue
            
            # 종료 시간 계산
            start_seconds = timestamp_to_seconds(timestamp)
            end_seconds = start_seconds + duration
            end_timestamp = seconds_to_timestamp(end_seconds)
            
            entry = TimelineEntry(
                timestamp=timestamp,
                image_id=image_id,
                duration=duration,
                end_timestamp=end_timestamp
            )
            
            timeline.append(entry)
        
        # 타임스탬프 순으로 정렬
        timeline.sort(key=lambda x: timestamp_to_seconds(x.timestamp))
        
        print(f"\n✅ {len(timeline)}개 타임라인 항목 생성")
        
        # 겹침 체크
        self._check_overlaps(timeline)
        
        return timeline
    
    def _check_overlaps(self, timeline: List[TimelineEntry]):
        """타임라인 겹침 체크"""
        for i in range(len(timeline) - 1):
            current = timeline[i]
            next_item = timeline[i + 1]
            
            current_end = timestamp_to_seconds(current.end_timestamp)
            next_start = timestamp_to_seconds(next_item.timestamp)
            
            if current_end > next_start:
                print(f"⚠️  겹침 발견:")
                print(f"    {current.image_id}: {current.timestamp} ~ {current.end_timestamp}")
                print(f"    {next_item.image_id}: {next_item.timestamp} ~ {next_item.end_timestamp}")
                print(f"    → {current_end - next_start}초 겹침")
    
    def create_video_manifest(
        self,
        timeline: List[TimelineEntry],
        image_paths: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        비디오 합성용 매니페스트 생성
        
        Args:
            timeline: 타임라인
            image_paths: {image_id: 이미지 경로} 매핑 (선택)
        
        Returns:
            비디오 매니페스트
        """
        manifest = {
            'total_images': len(timeline),
            'timeline': []
        }
        
        for entry in timeline:
            item = {
                'timestamp': entry.timestamp,
                'image_id': entry.image_id,
                'duration': entry.duration,
                'end_timestamp': entry.end_timestamp
            }
            
            # 이미지 경로 추가 (있으면)
            if image_paths and entry.image_id in image_paths:
                item['image_path'] = image_paths[entry.image_id]
            
            manifest['timeline'].append(item)
        
        return manifest
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph 노드로 실행
        
        Args:
            state: {
                "image_prompts": List[Dict],
                ...
            }
        
        Returns:
            state with timeline added
        """
        image_prompts = state.get("image_prompts", [])
        
        timeline = self.create_timeline(image_prompts)
        
        return {
            **state,
            "timeline": timeline
        }


# ============================================================================
# 헬퍼 함수들
# ============================================================================

def print_timeline_summary(timeline: List[TimelineEntry]):
    """타임라인 요약 출력"""
    print("\n" + "="*80)
    print("📋 타임라인 요약")
    print("="*80)
    
    print(f"\n총 항목: {len(timeline)}개")
    
    for i, entry in enumerate(timeline):
        print(f"\n[{i+1}] {entry.timestamp} ~ {entry.end_timestamp}")
        print(f"    이미지: {entry.image_id}")
        print(f"    지속: {entry.duration}초")


def export_timeline(timeline: List[TimelineEntry], output_path: str):
    """타임라인을 JSON으로 저장"""
    timeline_data = [asdict(entry) for entry in timeline]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(timeline_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 타임라인 저장: {output_path}")


def export_video_manifest(
    timeline: List[TimelineEntry],
    image_paths: Dict[str, str],
    output_path: str
):
    """비디오 매니페스트 저장"""
    mapper = TimestampMapper()
    manifest = mapper.create_video_manifest(timeline, image_paths)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 비디오 매니페스트 저장: {output_path}")


if __name__ == "__main__":
    print("Timestamp Mapper - 타임스탬프 매퍼")
    print("Import해서 사용하세요: from timestamp_mapper import TimestampMapper")