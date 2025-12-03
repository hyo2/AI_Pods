# Phase 3-1: 스크립트 파싱 노드

## ✅ 완료 사항

**타임스탬프 포함 팟캐스트 스크립트 → 구조화된 Scene 데이터 변환**

---

## 📂 생성된 파일

### 1. **script_parser_node.py** (메인)
- `ScriptParserNode`: 스크립트 파싱 노드
- `PodcastScene`: 장면 데이터 클래스
- 헬퍼 함수들 (필터링, 통계 등)

### 2. **test_script_parser.py** (테스트)
- 실제 스크립트 파일 파싱 테스트
- 필터 함수 테스트
- LangGraph 노드 테스트

---

## 🎯 기능

### **ScriptParserNode**

```python
parser = ScriptParserNode()

# 1. 파일에서 파싱
scenes = parser.parse_from_file("script.txt")

# 2. 텍스트에서 파싱
scenes = parser.parse_from_text(script_text)

# 3. JSON 저장/로드
parser.save_to_json(scenes, "scenes.json")
scenes = parser.load_from_json("scenes.json")

# 4. 요약 출력
parser.print_summary(scenes)

# 5. LangGraph 노드로 사용
state = {"script_path": "script.txt"}
result = parser(state)
```

### **PodcastScene 데이터 구조**

```python
@dataclass
class PodcastScene:
    scene_id: str              # "scene_001"
    timestamp_start: str       # "00:00:00"
    timestamp_end: str         # "00:00:24"
    duration: int              # 24 (초)
    
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
```

### **헬퍼 함수들**

```python
# 장면 상세 출력
print_scene_detail(scene)

# 화자별 필터
진행자_scenes = filter_by_speaker(scenes, "진행자")

# duration 범위 필터
짧은_scenes = filter_by_duration(scenes, max_duration=10)
긴_scenes = filter_by_duration(scenes, min_duration=21)

# 총 duration
total = get_total_duration(scenes)
```

---

## 📊 테스트 결과

**현수님 스크립트 파일 파싱 성공!**

```
총 장면: 28개
총 길이: 6분 50초 (410초)
화자 수: 3명 (진행자, 게스트, 진행자 이름)

화자별 발화:
  - 진행자: 14회 (161초)
  - 게스트: 13회 (245초)
  - 진행자 이름: 1회 (4초)

장면 길이 분포:
  - 평균: 14.6초
  - 최소: 3초
  - 최대: 30초
  - 짧은 장면 (≤10초): 9개
  - 중간 장면 (11-20초): 13개
  - 긴 장면 (≥21초): 6개
```

---

## 🚀 사용 방법

### **1. 기본 사용**

```python
from script_parser_node import ScriptParserNode

parser = ScriptParserNode()

# 스크립트 파일 파싱
scenes = parser.parse_from_file("podcast_script.txt")

# 요약 확인
parser.print_summary(scenes)

# JSON 저장
parser.save_to_json(scenes, "parsed_scenes.json")
```

### **2. 필터링**

```python
from script_parser_node import filter_by_speaker, filter_by_duration

# 진행자 발화만
host_scenes = filter_by_speaker(scenes, "진행자")

# 20초 이상 긴 장면만
long_scenes = filter_by_duration(scenes, min_duration=20)
```

### **3. LangGraph 통합**

```python
from langgraph.graph import StateGraph

# State 정의
class State(TypedDict):
    script_path: str
    scenes: List[PodcastScene]
    total_scenes: int
    total_duration: int

# Graph 구성
workflow = StateGraph(State)

parser = ScriptParserNode()
workflow.add_node("parse_script", parser)

# 실행
result = workflow.invoke({
    "script_path": "podcast_script.txt"
})

scenes = result["scenes"]
```

---

## 📁 파일 위치

```
/mnt/user-data/outputs/
├── script_parser_node.py           # 메인 노드
├── test_script_parser.py           # 테스트 코드
└── test_output/
    └── script_parser/
        └── parsed_scenes.json      # 파싱 결과
```

---

## 🎯 다음 단계 (Phase 3-2)

**장면 선택 노드 (SceneSelectionNode)**

```
입력: List[PodcastScene]
  ↓
AI 판단: 어떤 장면에 이미지가 필요한가?
  ↓
출력: image_required=True로 마킹된 장면들
```

**판단 기준:**
- ✅ 구체적 설명, 사례
- ✅ 숫자, 데이터
- ✅ 핵심 개념 도입
- ❌ 인사, 반응
- ❌ 짧은 질문

---

## 💡 테스트 명령어

```bash
# 프로젝트 루트에서

# 1. 파일 복사
cp /mnt/user-data/outputs/script_parser_node.py app/nodes/

# 2. 테스트 실행
python /mnt/user-data/outputs/test_script_parser.py
```

---

## 📊 JSON 출력 예시

```json
{
  "total_scenes": 28,
  "total_duration": 410,
  "speakers": ["진행자", "게스트", "진행자 이름"],
  "scenes": [
    {
      "scene_id": "scene_001",
      "timestamp_start": "00:00:00",
      "timestamp_end": "00:00:24",
      "duration": 24,
      "speaker": "진행자",
      "text": "안녕하세요! 지식 탐험가 여러분...",
      "image_required": false,
      "image_title": null,
      "image_prompt": null,
      "image_style": null,
      "image_path": null,
      "importance": 0.5,
      "context": ""
    }
  ]
}
```

---

**✅ Phase 3-1 완료! 다음은 장면 선택 노드입니다! 🚀**
