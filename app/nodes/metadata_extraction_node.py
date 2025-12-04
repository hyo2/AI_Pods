"""
메타데이터 추출 노드 (LangGraph)
전체 스크립트를 분석하여 Global Visual Guidelines + Content Metadata 생성
"""

import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

# Vertex AI import
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    VERTEXAI_AVAILABLE = True
except ImportError:
    VERTEXAI_AVAILABLE = False
    print("⚠️  vertexai 패키지가 없습니다.")


# PodcastScene import
try:
    from script_parser_node import PodcastScene
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from script_parser_node import PodcastScene
    except ImportError:
        print("⚠️  script_parser_node를 찾을 수 없습니다.")
        PodcastScene = None


@dataclass
class ColorPalette:
    """색상 팔레트"""
    primary: str        # 주 색상 (HEX)
    secondary: str      # 보조 색상
    accent: str         # 강조 색상
    background: str     # 배경 색상
    text_safe: str      # 텍스트 영역 색상


@dataclass
class GlobalVisualGuidelines:
    """전역 비주얼 가이드라인"""
    art_style: str                      # "Flat isometric illustration"
    art_style_description: str          # 스타일 상세 설명
    art_style_details: Dict[str, str]   # primary, secondary, avoid
    color_palette: ColorPalette
    color_mood: str
    overall_mood: str
    emotional_tone: str
    lighting_style: str                 # 조명 스타일
    composition_guidelines: str         # 구도 가이드라인
    recurring_elements: Dict[str, Any]
    reference_style: str


@dataclass
class Chapter:
    """챕터 정보"""
    id: str
    title: str
    start_time: str
    end_time: str
    duration: int
    scene_ids: List[str]
    key_topics: List[str]
    summary: str
    importance: float
    expected_images: int


@dataclass
class KeyConcept:
    """핵심 개념"""
    term: str
    full_name: Optional[str]
    first_appearance: str
    importance: float
    should_visualize: bool
    visual_priority: str  # "high", "medium", "low"


@dataclass
class CriticalMoment:
    """임계 순간"""
    timestamp: str
    scene_id: str
    type: str           # "핵심 기술 도입", "전환점"
    description: str


@dataclass
class ContentAnalysis:
    """콘텐츠 분석 결과"""
    total_duration: str
    total_scenes: int
    content_type: str           # educational, news, story, business
    main_topic: str             # 주제 (1-2줄, 간결)
    summary: str                # 한 줄 요약
    detailed_summary: str       # 상세 요약 (스크립트 길이에 따라 조절)
    target_audience: str
    chapters: List[Chapter]
    key_concepts: List[KeyConcept]
    critical_moments: List[CriticalMoment]


@dataclass
class PodcastMetadata:
    """전체 팟캐스트 메타데이터"""
    podcast_id: str
    created_at: str
    content: ContentAnalysis
    visual: GlobalVisualGuidelines


class MetadataExtractionNode:
    """
    메타데이터 추출 노드
    
    전체 스크립트를 분석하여:
    1. Global Visual Guidelines 생성
    2. Content Analysis (챕터, 핵심 개념)
    3. Critical Moments 추출
    """
    
    # Global Visual Metadata 생성 프롬프트
    VISUAL_GUIDELINES_PROMPT = """당신은 전문 비디오 아트 디렉터입니다.
YouTube 교육 콘텐츠, NotebookLM 스타일 비디오 제작 경험이 풍부합니다.

다음 팟캐스트 스크립트를 분석하고, 전체 비디오에 일관되게 적용할 **비주얼 가이드라인**을 생성하세요.

**스크립트:**
{script}

**목표:**
- 모든 이미지가 같은 시리즈처럼 보이도록 통일감 유지
- NotebookLM 스타일: 깔끔하고, 교육적이며, engaging
- 나노바나나(Gemini 2.5 Flash Image) 최적화

**나노바나나 아트 스타일 선택 가이드:**

**1. 매체/기법 기반 스타일:**
- "3D animation" - 입체적인 만화 스타일 (교육/기술 콘텐츠 적합)
- "Flat vector illustration" - 깔끔한 평면 벡터, WPA 포스터 스타일 (정보 전달 최적)
- "Isometric illustration" - 아이소메트릭 입체 일러스트 (기술/프로세스 설명)
- "Watercolor painting" - 수채화 번짐 효과 (감성적/예술 콘텐츠)
- "Oil painting" - 유화 질감 (고급스러운 느낌)
- "Line art" - 선 위주의 단순한 그림 (미니멀 디자인)
- "Comic sequence" - 만화책 스타일 (스토리텔링)

**2. 사진 기반 스타일:**
- "Photorealistic" - 극사실적 사진 (제품/현실 묘사)
- "Cinematic wide-angle" - 영화 같은 구도 (드라마틱한 효과)
- "Product photography" - 깔끔한 제품 사진 (비즈니스)

**3. 디자인/콘셉트 스타일:**
- "Technical diagram" - 기술 도식/청사진 (엔지니어링/과학)
- "Infographic style" - 인포그래픽 스타일 (데이터 시각화)
- "Children's picture book style" - 동화책 삽화 (교육/아동)
- "Modern minimalist design" - 현대적 미니멀 디자인 (세련된 브랜드)

**스타일 선택 기준:**
- 기술/AI/교육 → "Flat vector illustration" 또는 "3D animation" 또는 "Isometric illustration"
- 스토리/감성 → "Watercolor painting" 또는 "Children's picture book style"
- 비즈니스/전문 → "Modern minimalist design" 또는 "Photorealistic"
- 과학/엔지니어링 → "Technical diagram" 또는 "Isometric illustration"

**다음 정보를 JSON으로 생성하세요:**

```json
{{
    "art_style": "Flat vector illustration",
    "art_style_description": "깔끔하고 현대적인 평면 벡터 일러스트레이션. 단순한 형태와 명확한 색상 구분으로 정보 전달에 최적화.",
    "art_style_details": {{
        "primary": "부드러운 곡선과 기하학적 형태",
        "secondary": "그라데이션 최소화, 플랫한 색상 블록",
        "avoid": "과도한 디테일, 사실적 텍스처, 복잡한 그림자"
    }},
    "color_palette": {{
        "primary": "#6366f1",
        "secondary": "#8b5cf6",
        "accent": "#ec4899",
        "background": "#f8fafc",
        "text_safe": "#ffffff"
    }},
    "color_mood": "밝고 친근하면서도 전문적인",
    "overall_mood": "Professional and engaging, 미래지향적이면서도 접근 가능한",
    "emotional_tone": "낙관적이고 자신감 있는, 교육적",
    "lighting_style": "밝고 균일한 조명, 부드러운 그림자, 명확한 색감",
    "composition_guidelines": "16:9 비율, 중앙 집중 구도, 충분한 여백, 시각적 위계 명확",
    "recurring_elements": {{
        "character": "반복 등장할 캐릭터/아이콘 (있으면)",
        "motifs": ["기하학적 패턴", "데이터 흐름선"],
        "icons_style": "둥근 모서리, 채워진 스타일"
    }},
    "reference_style": "NotebookLM Video Overview style, Kurzgesagt educational videos"
}}
```

**중요:**
- **단일 아트 스타일 선택** (스크립트 콘텐츠에 가장 적합한 것)
- 색상은 반드시 HEX 코드로 (#RRGGBB)
- art_style_description은 나노바나나가 이해하기 쉽게 구체적으로
- **🔴 CRITICAL: 이미지 내 모든 텍스트/라벨/다이어그램은 영어로만 표기** (한글 텍스트는 렌더링 품질 저하)
- 모든 필드를 빠짐없이 작성
- JSON만 출력 (다른 설명 없이)
"""

    # Content Analysis 프롬프트
    CONTENT_ANALYSIS_PROMPT = """당신은 콘텐츠 분석 전문가입니다.

다음 팟캐스트 스크립트를 분석하여 콘텐츠 구조를 파악하세요.

**스크립트:**
{script}

**분석 목표:**
1. 팟캐스트의 핵심 주제 파악
2. 전체 내용 요약 (길이에 따라 적절히 조절)
3. 의미 단위로 챕터 분할 (보통 5-8개)
4. 각 챕터의 핵심 주제 파악
5. 시각화가 필요한 핵심 개념 추출
6. 임계 순간 (Critical Moments) 찾기

**다음 정보를 JSON으로 생성하세요:**

```json
{{
    "total_duration": "X분 Y초",
    "total_scenes": 숫자,
    "content_type": "educational/news/story/business/interview 중 선택",
    
    "main_topic": "팟캐스트의 핵심 주제 (1-2줄, 간결하게)",
    "summary": "한 줄 요약 (50-80자)",
    "detailed_summary": "상세 요약 (스크립트 길이에 따라 조절: 5분 미만=2-3문장, 5-10분=3-5문장, 10-20분=5-7문장, 20분 이상=7-10문장)",
    
    "target_audience": "타겟 청중 설명",
    
    "chapters": [
        {{
            "id": "ch_01",
            "title": "챕터 제목 (예: 오프닝)",
            "start_time": "00:00:00",
            "end_time": "00:00:48",
            "duration": 48,
            "scene_ids": ["scene_001", "scene_002"],
            "key_topics": ["토픽1", "토픽2"],
            "summary": "이 챕터 요약",
            "importance": 0.0-1.0 (중요도),
            "expected_images": 예상 이미지 개수
        }}
    ],
    
    "key_concepts": [
        {{
            "term": "개념 이름 (예: TTS)",
            "full_name": "전체 이름 (있으면)",
            "first_appearance": "00:01:48",
            "importance": 0.0-1.0,
            "should_visualize": true/false,
            "visual_priority": "high/medium/low"
        }}
    ],
    
    "critical_moments": [
        {{
            "timestamp": "00:01:48",
            "scene_id": "scene_008",
            "type": "핵심 기술 도입/전환점/결론 등",
            "description": "무슨 일이 일어나는가"
        }}
    ]
}}
```

**주의:**
- main_topic: 이 팟캐스트가 무엇에 관한 것인지 명확하게
- summary: 핵심만 간결하게 한 줄로
- detailed_summary: 전체 흐름을 상세히, 길이는 팟캐스트 길이에 비례
- 챕터는 의미 단위로 (3-5개 장면씩)
- expected_images는 챕터 중요도에 비례
- key_concepts는 시각화 가능한 것만
- JSON만 출력
"""

    def __init__(
        self,
        project_id: str = None,  # None이면 환경변수에서 읽기
        location: str = "us-central1",
        model_name: str = "gemini-2.0-flash-exp"
    ):
        """
        메타데이터 추출 노드 초기화
        
        Args:
            project_id: Google Cloud 프로젝트 ID (None이면 환경변수 사용)
            location: Vertex AI 리전
            model_name: 사용할 Gemini 모델
        """
        # 프로젝트 ID 결정
        if project_id is None:
            import os
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
            if not project_id:
                print("⚠️  프로젝트 ID가 없습니다. 환경변수 GOOGLE_CLOUD_PROJECT를 설정하거나 명시적으로 전달하세요.")
                project_id = "dummy-project"  # fallback
        """
        메타데이터 추출 노드 초기화
        """
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        
        # Vertex AI 초기화
        if VERTEXAI_AVAILABLE:
            try:
                vertexai.init(project=project_id, location=location)
                self.model = GenerativeModel(model_name)
                print(f"✅ Vertex AI 초기화 완료: {model_name}")
            except Exception as e:
                print(f"⚠️  Vertex AI 초기화 실패: {str(e)}")
                self.model = None
        else:
            self.model = None
    
    def _prepare_script_text(self, scenes: List[PodcastScene]) -> str:
        """
        장면 리스트를 텍스트로 변환
        """
        lines = []
        for scene in scenes:
            lines.append(f"[{scene.timestamp_start}] {scene.speaker}: {scene.text}")
        
        return "\n".join(lines)
    
    def _clean_json_response(self, text: str) -> str:
        """JSON 응답 정리 (마크다운 제거 + 이스케이핑)"""
        # ```json ... ``` 제거
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()
        
        # JSON 문자열 내부의 줄바꿈 문제 수정 시도
        # (이건 완벽한 해결책은 아니지만 대부분의 경우 도움됨)
        try:
            # 이미 유효한 JSON이면 그대로 반환
            json.loads(text)
            return text
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 그대로 반환 (재시도 로직이 처리함)
            return text
    
    def extract_visual_guidelines(
        self,
        scenes: List[PodcastScene],
        max_retries: int = 3
    ) -> Optional[GlobalVisualGuidelines]:
        """
        Global Visual Guidelines 생성 (재시도 로직 포함)
        """
        if not self.model:
            raise RuntimeError("Vertex AI 모델이 초기화되지 않았습니다. GOOGLE_CLOUD_PROJECT 및 인증 정보를 확인하세요.")
        
        print("\n🎨 Global Visual Guidelines 생성 중...")
        
        # 스크립트 준비
        script_text = self._prepare_script_text(scenes)
        
        # 프롬프트 생성
        prompt = self.VISUAL_GUIDELINES_PROMPT.format(script=script_text)
        
        # 재시도 루프
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"   재시도 {attempt + 1}/{max_retries}...")
                
                # Gemini 호출
                response = self.model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "max_output_tokens": 4096,
                        "response_mime_type": "application/json"  # JSON 응답 강제
                    }
                )
                
                # 응답 파싱
                response_text = self._clean_json_response(response.text)
                data = json.loads(response_text)
                
                # GlobalVisualGuidelines 객체 생성
                visual = GlobalVisualGuidelines(
                    art_style=data["art_style"],
                    art_style_description=data.get("art_style_description", ""),
                    art_style_details=data["art_style_details"],
                    color_palette=ColorPalette(**data["color_palette"]),
                    color_mood=data["color_mood"],
                    overall_mood=data["overall_mood"],
                    emotional_tone=data["emotional_tone"],
                    lighting_style=data.get("lighting_style", "밝고 균일한 조명"),
                    composition_guidelines=data.get("composition_guidelines", "16:9 비율"),
                    recurring_elements=data["recurring_elements"],
                    reference_style=data["reference_style"]
                )
                
                print("✅ Visual Guidelines 생성 완료")
                self._print_visual_summary(visual)
                
                return visual
            
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON 파싱 실패 (시도 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    print(f"   응답 일부: {response_text[:200]}...")
                    continue
                else:
                    print(f"❌ Visual Guidelines 생성 최종 실패")
                    raise RuntimeError(f"Visual Guidelines 생성 실패: JSON 파싱 에러 ({str(e)})")
            
            except KeyError as e:
                print(f"⚠️  필수 필드 누락 (시도 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    continue
                else:
                    print(f"❌ Visual Guidelines 생성 최종 실패")
                    raise RuntimeError(f"Visual Guidelines 생성 실패: 필수 필드 누락 ({str(e)})")
            
            except Exception as e:
                print(f"⚠️  생성 실패 (시도 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    continue
                else:
                    print(f"❌ Visual Guidelines 생성 최종 실패")
                    raise RuntimeError(f"Visual Guidelines 생성 실패: {str(e)}")
        
        # 여기 도달하면 실패
        raise RuntimeError("Visual Guidelines 생성 실패: 최대 재시도 횟수 초과")
    
    def extract_content_analysis(
        self,
        scenes: List[PodcastScene],
        max_retries: int = 3
    ) -> Optional[ContentAnalysis]:
        """
        Content Analysis 생성 (재시도 로직 포함)
        """
        if not self.model:
            raise RuntimeError("Vertex AI 모델이 초기화되지 않았습니다. GOOGLE_CLOUD_PROJECT 및 인증 정보를 확인하세요.")
        
        print("\n📊 Content Analysis 생성 중...")
        
        # 스크립트 준비
        script_text = self._prepare_script_text(scenes)
        
        # 프롬프트 생성
        prompt = self.CONTENT_ANALYSIS_PROMPT.format(script=script_text)
        
        # 재시도 루프
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"   재시도 {attempt + 1}/{max_retries}...")
                
                # Gemini 호출
                response = self.model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.3,  # 분석은 일관성 중요
                        "top_p": 0.8,
                        "max_output_tokens": 8192,  # 6144 → 8192
                        "response_mime_type": "application/json"  # JSON 응답 강제
                    }
                )
                
                # 응답 파싱
                response_text = self._clean_json_response(response.text)
                data = json.loads(response_text)
                
                # ContentAnalysis 객체 생성
                content = ContentAnalysis(
                    total_duration=data["total_duration"],
                    total_scenes=data["total_scenes"],
                    content_type=data["content_type"],
                    main_topic=data["main_topic"],
                    summary=data["summary"],
                    detailed_summary=data["detailed_summary"],
                    target_audience=data["target_audience"],
                    chapters=[Chapter(**ch) for ch in data["chapters"]],
                    key_concepts=[KeyConcept(**kc) for kc in data["key_concepts"]],
                    critical_moments=[CriticalMoment(**cm) for cm in data["critical_moments"]]
                )
                
                print("✅ Content Analysis 생성 완료")
                self._print_content_summary(content)
                
                return content
            
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON 파싱 실패 (시도 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    print(f"   응답 일부: {response_text[:200]}...")
                    continue
                else:
                    print(f"❌ Content Analysis 생성 최종 실패")
                    raise RuntimeError(f"Content Analysis 생성 실패: JSON 파싱 에러 ({str(e)})")
            
            except KeyError as e:
                print(f"⚠️  필수 필드 누락 (시도 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    continue
                else:
                    print(f"❌ Content Analysis 생성 최종 실패")
                    raise RuntimeError(f"Content Analysis 생성 실패: 필수 필드 누락 ({str(e)})")
            
            except Exception as e:
                print(f"⚠️  생성 실패 (시도 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    continue
                else:
                    print(f"❌ Content Analysis 생성 최종 실패")
                    raise RuntimeError(f"Content Analysis 생성 실패: {str(e)}")
        
        # 여기 도달하면 실패
        raise RuntimeError("Content Analysis 생성 실패: 최대 재시도 횟수 초과")
    
    def extract_metadata(
        self,
        scenes: List[PodcastScene],
        podcast_id: str = "podcast_001"
    ) -> PodcastMetadata:
        """
        전체 메타데이터 추출 (Visual + Content)
        """
        print("\n" + "="*80)
        print("🔍 메타데이터 추출 시작")
        print("="*80)
        print(f"총 장면: {len(scenes)}개")
        
        # Visual Guidelines 생성
        visual = self.extract_visual_guidelines(scenes)
        
        # Content Analysis 생성
        content = self.extract_content_analysis(scenes)
        
        # 통합
        import datetime
        metadata = PodcastMetadata(
            podcast_id=podcast_id,
            created_at=datetime.datetime.now().isoformat(),
            content=content,
            visual=visual
        )
        
        print("\n" + "="*80)
        print("✅ 메타데이터 추출 완료")
        print("="*80)
        
        return metadata
    
    def _print_visual_summary(self, visual: GlobalVisualGuidelines):
        """Visual Guidelines 요약 출력"""
        print(f"\n🎨 Visual Guidelines:")
        print(f"  Art Style: {visual.art_style}")
        print(f"  Primary Color: {visual.color_palette.primary}")
        print(f"  Mood: {visual.overall_mood}")
    
    def _print_content_summary(self, content: ContentAnalysis):
        """Content Analysis 요약 출력"""
        print(f"\n📊 Content Analysis:")
        print(f"  Duration: {content.total_duration}")
        print(f"  Type: {content.content_type}")
        print(f"  Topic: {content.main_topic}")
        print(f"  Summary: {content.summary}")
        print(f"  Chapters: {len(content.chapters)}개")
        print(f"  Key Concepts: {len(content.key_concepts)}개")
        print(f"  Critical Moments: {len(content.critical_moments)}개")
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph 노드로 실행
        """
        scenes = state.get("scenes", [])
        
        if not scenes:
            print("⚠️  장면이 없습니다.")
            return {**state, "metadata": None}
        
        # 메타데이터 추출
        metadata = self.extract_metadata(scenes)
        
        return {
            **state,
            "metadata": metadata
        }


# ============================================================================
# 헬퍼 함수들
# ============================================================================

def save_metadata(metadata: PodcastMetadata, output_path: str):
    """메타데이터를 JSON 파일로 저장"""
    
    # dataclass를 dict로 변환
    def to_dict(obj):
        if hasattr(obj, '__dict__'):
            return {k: to_dict(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, list):
            return [to_dict(item) for item in obj]
        else:
            return obj
    
    data = to_dict(metadata)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 메타데이터 저장: {output_path}")


def print_metadata_summary(metadata: PodcastMetadata):
    """메타데이터 요약 출력"""
    print("\n" + "="*80)
    print("📋 메타데이터 요약")
    print("="*80)
    
    print(f"\n📊 콘텐츠 정보:")
    print(f"  타입: {metadata.content.content_type}")
    print(f"  길이: {metadata.content.total_duration}")
    print(f"  주제: {metadata.content.main_topic}")
    print(f"  요약: {metadata.content.summary}")
    
    print(f"\n📝 상세 요약:")
    # 상세 요약을 적절히 줄바꿈해서 출력
    summary_lines = metadata.content.detailed_summary.split('. ')
    for line in summary_lines:
        if line.strip():
            print(f"  {line.strip()}{'.' if not line.endswith('.') else ''}")
    
    print(f"\n📚 챕터: {len(metadata.content.chapters)}개")
    for ch in metadata.content.chapters:
        print(f"  - {ch.title} ({ch.start_time}-{ch.end_time})")
        print(f"    중요도: {ch.importance:.2f}, 예상 이미지: {ch.expected_images}개")
    
    print(f"\n🔑 핵심 개념: {len(metadata.content.key_concepts)}개")
    for kc in metadata.content.key_concepts:
        if kc.should_visualize:
            print(f"  - {kc.term} (우선순위: {kc.visual_priority})")
    
    print(f"\n🎨 비주얼 스타일:")
    print(f"  아트: {metadata.visual.art_style}")
    print(f"  주 색상: {metadata.visual.color_palette.primary}")
    print(f"  무드: {metadata.visual.overall_mood}")


if __name__ == "__main__":
    print("Metadata Extraction Node - 메타데이터 추출 노드")
    print("Import해서 사용하세요: from metadata_extraction_node import MetadataExtractionNode")