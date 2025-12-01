"""
토픽 추출 노드 (LangGraph)
문서 분석 결과에서 이미지 생성용 토픽 추출
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from vertexai.generative_models import GenerativeModel


@dataclass
class ImageTopic:
    """이미지 생성용 토픽"""
    topic_id: str
    title: str
    description: str
    keywords: List[str]
    style: str  # abstract, technical, illustration, photo, scene
    importance: float  # 0.0 ~ 1.0
    context: Optional[str] = None  # 추가 컨텍스트


class TopicExtractionNode:
    """요약 결과에서 이미지 생성용 토픽 추출"""
    
    # 토픽 추출 프롬프트
    TOPIC_EXTRACTION_PROMPT = """당신은 팟캐스트 비디오 제작을 위한 이미지 토픽 추출 전문가입니다.

문서 분석 결과가 주어지면, **비디오 오버레이용 이미지를 생성하기 위한 토픽**을 추출하세요.

[입력]
문서 분석 요약 결과 (통합 요약 섹션 중심)

[목표]
1. 통합 요약의 각 주요 섹션/개념에서 **시각화할 수 있는 토픽** 추출
2. 각 토픽은 하나의 이미지로 표현 가능해야 함
3. 팟캐스트 비디오 오버레이로 사용될 것을 고려

[토픽 추출 기준]
✅ 포함해야 할 토픽:
- 핵심 개념 (예: "AI 기술", "머신러닝 프로세스")
- 주요 주제 전환점 (예: "역사적 배경", "현재 트렌드", "미래 전망")
- 중요한 데이터/통계 (시각화 가능한)
- 구체적인 사례/응용 분야
- 논의의 핵심 포인트

❌ 제외해야 할 토픽:
- 너무 추상적이거나 모호한 개념
- 시각화가 불가능한 내용
- 중복되는 개념

[토픽 개수]
- 최소: 5개
- 최대: 20개
- 권장: 분당 1.5개 (10분 콘텐츠 = 15개 토픽)
- 문서 길이와 복잡도에 따라 조절

[스타일 선택 기준]
각 토픽에 가장 적합한 이미지 스타일을 선택하세요:

1. **abstract** (추상적 미니멀)
   - 개념적 주제: "AI의 미래", "디지털 혁신"
   - 배경/분위기 이미지
   - 장점: 빠른 생성, 비용 효율적

2. **technical** (기술 다이어그램)
   - 프로세스/워크플로우: "머신러닝 파이프라인"
   - 구조/아키텍처: "신경망 구조"
   - 장점: 정보 전달력, 교육적

3. **illustration** (창의적 일러스트)
   - 개념 설명: "딥러닝의 작동 원리"
   - 비유/은유: "AI를 정원 가꾸기에 비유"
   - 장점: 친근함, 이해하기 쉬움

4. **photo** (포토리얼리스틱)
   - 실제 사례: "의료 현장의 AI"
   - 제품/서비스: "AI 스피커"
   - 장점: 현실감, 공감대

5. **scene** (장면 일러스트)
   - 스토리텔링: "연구원이 AI 모델 훈련하는 장면"
   - 상황 묘사: "미래 도시의 자율주행차"
   - 장점: 몰입감, 서사

[출력 형식]
JSON 배열로 출력하세요. 각 토픽은 다음 구조:

```json
[
  {{
    "topic_id": "topic_01_opening",
    "title": "AI 기술의 시작",
    "description": "인공지능 기술의 역사적 배경과 초기 발전 과정을 나타내는 추상적 시각화",
    "keywords": ["AI", "history", "technology", "innovation"],
    "style": "abstract",
    "importance": 0.9,
    "context": "오프닝 장면, 전체 내용의 도입부"
  }},
  {{
    "topic_id": "topic_02_ml_process",
    "title": "머신러닝 프로세스",
    "description": "데이터 수집, 전처리, 학습, 평가 단계를 보여주는 워크플로우 다이어그램",
    "keywords": ["machine learning", "process", "workflow", "data"],
    "style": "technical",
    "importance": 0.85,
    "context": "핵심 개념 설명 섹션"
  }}
]
```

[중요 규칙]
1. **topic_id는 순서를 나타내는 넘버링 포함** (topic_01, topic_02...)
2. **description은 이미지 생성 프롬프트의 기반**이 됨 (구체적으로)
3. **keywords는 5~10개** 정도
4. **importance는 0.0~1.0** (0.8 이상이 핵심 토픽)
5. **style은 반드시 5가지 중 하나**: abstract, technical, illustration, photo, scene
6. **중복 개념은 통합**, 하나의 토픽으로

[분석할 요약 결과]
{summary_content}

위 요약 결과를 분석하여 이미지 토픽을 추출하세요.
JSON 배열만 출력하세요. 다른 설명은 불필요합니다."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        """
        Args:
            model_name: 사용할 Gemini 모델
        """
        self.model = GenerativeModel(model_name)
        self.model_name = model_name
    
    def extract_topics_from_analysis(
        self,
        analysis_result: Dict[str, Any],
        min_topics: int = 5,
        max_topics: int = 20,
        **generation_config
    ) -> List[ImageTopic]:
        """
        분석 결과에서 토픽 추출
        
        Args:
            analysis_result: CompleteAnalysis (dict 형태)
            min_topics: 최소 토픽 개수
            max_topics: 최대 토픽 개수
            **generation_config: Gemini 설정
        
        Returns:
            ImageTopic 리스트
        """
        print(f"\n🔍 토픽 추출 시작")
        
        # 1. 통합 요약 추출
        integrated_summary = analysis_result.get('integrated_summary', {})
        
        # 원본 출력이 있으면 사용 (더 풍부한 정보)
        raw_output = analysis_result.get('metadata', {}).get('raw_output', '')
        
        if raw_output:
            # 원본에서 통합 요약 부분만 추출 (있다면)
            summary_content = self._extract_summary_section(raw_output)
        else:
            # 구조화된 데이터 사용
            summary_content = self._format_integrated_summary(integrated_summary)
        
        print(f"📝 요약 길이: {len(summary_content)} 문자")
        
        # 2. 프롬프트 생성
        prompt = self.TOPIC_EXTRACTION_PROMPT.format(
            summary_content=summary_content
        )
        
        # 3. Gemini 호출
        print("🤖 Gemini로 토픽 추출 중...")
        
        config = {
            "temperature": 0.4,  # 적당히 창의적
            "top_p": 0.9,
            "max_output_tokens": 4096,
            **generation_config
        }
        
        response = self.model.generate_content(prompt, generation_config=config)
        raw_topics = response.text
        
        print(f"✅ 토픽 추출 완료")
        
        # 4. JSON 파싱
        topics = self._parse_topics(raw_topics)
        
        # 5. 개수 제한
        if len(topics) < min_topics:
            print(f"⚠️  토픽 개수 부족 ({len(topics)} < {min_topics})")
        elif len(topics) > max_topics:
            print(f"⚠️  토픽 개수 초과, 상위 {max_topics}개만 사용")
            topics = sorted(topics, key=lambda t: t.importance, reverse=True)[:max_topics]
        
        print(f"📊 최종 토픽 개수: {len(topics)}")
        
        return topics
    
    def _extract_summary_section(self, raw_output: str) -> str:
        """원본 출력에서 통합 요약 섹션 추출"""
        # "최종 통합 요약" 또는 "4. 📌" 이후 부분 추출
        markers = [
            "4. 📌 최종 통합 요약",
            "최종 통합 요약",
            "## 최종 통합 요약",
            "### 최종 통합 요약"
        ]
        
        for marker in markers:
            if marker in raw_output:
                parts = raw_output.split(marker, 1)
                if len(parts) > 1:
                    return marker + parts[1]
        
        # 마커를 찾지 못하면 전체 반환
        return raw_output
    
    def _format_integrated_summary(self, integrated_summary: Dict) -> str:
        """구조화된 통합 요약을 텍스트로 변환"""
        sections = integrated_summary.get('sections', [])
        conclusion = integrated_summary.get('conclusion', '')
        
        text_parts = []
        
        for section in sections:
            title = section.get('title', '')
            content = section.get('content', '')
            key_points = section.get('key_points', [])
            
            text_parts.append(f"## {title}")
            text_parts.append(content)
            if key_points:
                text_parts.append("핵심 포인트:")
                for point in key_points:
                    text_parts.append(f"- {point}")
            text_parts.append("")
        
        if conclusion:
            text_parts.append("## 결론")
            text_parts.append(conclusion)
        
        return "\n".join(text_parts)
    
    def _parse_topics(self, raw_topics: str) -> List[ImageTopic]:
        """JSON 문자열을 ImageTopic 리스트로 파싱"""
        import json
        import re
        
        # JSON 추출 (markdown 코드 블록 제거)
        json_text = raw_topics
        
        # ```json ... ``` 제거
        json_text = re.sub(r'```json\s*', '', json_text)
        json_text = re.sub(r'```\s*', '', json_text)
        json_text = json_text.strip()
        
        try:
            topics_data = json.loads(json_text)
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON 파싱 실패: {e}")
            print(f"원본 텍스트: {json_text[:200]}...")
            return []
        
        # ImageTopic 객체 생성
        topics = []
        for data in topics_data:
            try:
                topic = ImageTopic(
                    topic_id=data.get('topic_id', f"topic_{len(topics)+1:02d}"),
                    title=data.get('title', ''),
                    description=data.get('description', ''),
                    keywords=data.get('keywords', []),
                    style=data.get('style', 'abstract'),
                    importance=float(data.get('importance', 0.5)),
                    context=data.get('context')
                )
                topics.append(topic)
            except Exception as e:
                print(f"⚠️  토픽 파싱 실패: {e}")
                continue
        
        return topics
    
    def __call__(self, state: dict) -> dict:
        """
        LangGraph 노드 실행
        
        Expected state:
            - analysis_result: CompleteAnalysis (dict)
        
        Returns:
            - image_topics: List[ImageTopic]
        """
        analysis_result = state.get("analysis_result")
        
        if not analysis_result:
            raise ValueError("No analysis_result in state")
        
        # CompleteAnalysis가 dataclass면 dict로 변환
        if hasattr(analysis_result, '__dict__'):
            from dataclasses import asdict
            analysis_result = asdict(analysis_result)
        
        topics = self.extract_topics_from_analysis(analysis_result)
        
        return {
            **state,
            "image_topics": topics
        }


# ============================================================================
# 헬퍼 함수
# ============================================================================

def print_topics_summary(topics: List[ImageTopic]):
    """토픽 요약 출력"""
    print("\n" + "="*80)
    print("📊 추출된 이미지 토픽")
    print("="*80)
    
    print(f"\n총 {len(topics)}개 토픽")
    
    # 스타일별 분포
    style_counts = {}
    for topic in topics:
        style_counts[topic.style] = style_counts.get(topic.style, 0) + 1
    
    print("\n스타일 분포:")
    for style, count in sorted(style_counts.items()):
        print(f"  {style}: {count}개")
    
    # 토픽 목록
    print("\n" + "-"*80)
    print("토픽 상세")
    print("-"*80)
    
    for i, topic in enumerate(topics, 1):
        print(f"\n[{i}] {topic.topic_id}")
        print(f"  제목: {topic.title}")
        print(f"  스타일: {topic.style}")
        print(f"  중요도: {topic.importance:.2f}")
        print(f"  설명: {topic.description[:100]}...")
        print(f"  키워드: {', '.join(topic.keywords[:5])}")
        if topic.context:
            print(f"  컨텍스트: {topic.context}")


def save_topics_to_json(topics: List[ImageTopic], output_path: str):
    """토픽을 JSON으로 저장"""
    import json
    from dataclasses import asdict
    
    topics_dict = [asdict(topic) for topic in topics]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(topics_dict, f, ensure_ascii=False, indent=2)
    
    print(f"💾 토픽 저장: {output_path}")
