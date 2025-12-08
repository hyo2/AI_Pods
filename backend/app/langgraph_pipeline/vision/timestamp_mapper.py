"""
타임스탬프 매퍼 (podcast_generator 복사본)
"""

import json
from typing import List, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class TimelineEntry:
    timestamp: str
    image_id: str
    duration: int
    end_timestamp: str


def timestamp_to_seconds(timestamp: str) -> int:
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
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class TimestampMapper:
    def __init__(self):
        pass

    def create_timeline(self, image_plans: List[Dict[str, Any]]) -> List[TimelineEntry]:
        print("\n" + "="*80)
        print("⏰ 타임라인 생성 중...")
        print("="*80)

        timeline = []
        for plan in image_plans:
            timestamp = plan.get('primary_timestamp')
            image_id = plan.get('image_id')
            duration = plan.get('duration', 20)

            if not timestamp or not image_id:
                print(f"⚠️  {plan} - 타임스탬프 또는 ID 없음, 스킵")
                continue

            start_seconds = timestamp_to_seconds(timestamp)
            end_seconds = start_seconds + duration
            end_timestamp = seconds_to_timestamp(end_seconds)

            entry = TimelineEntry(timestamp=timestamp, image_id=image_id, duration=duration, end_timestamp=end_timestamp)
            timeline.append(entry)

        timeline.sort(key=lambda x: timestamp_to_seconds(x.timestamp))
        print(f"\n✅ {len(timeline)}개 타임라인 항목 생성")
        self._check_overlaps(timeline)
        return timeline

    def _check_overlaps(self, timeline: List[TimelineEntry]):
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

    def create_video_manifest(self, timeline: List[TimelineEntry], image_paths: Dict[str, str] = None) -> Dict[str, Any]:
        manifest = {'total_images': len(timeline), 'timeline': []}
        for entry in timeline:
            item = {'timestamp': entry.timestamp, 'image_id': entry.image_id, 'duration': entry.duration, 'end_timestamp': entry.end_timestamp}
            if image_paths and entry.image_id in image_paths:
                item['image_path'] = image_paths[entry.image_id]
            manifest['timeline'].append(item)
        return manifest

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        image_prompts = state.get("image_prompts", [])
        timeline = self.create_timeline(image_prompts)
        return {**state, "timeline": timeline}


# helper functions omitted for brevity

if __name__ == "__main__":
    print("Timestamp Mapper - 타임스탬프 매퍼")
    print("Import해서 사용하세요: from timestamp_mapper import TimestampMapper")