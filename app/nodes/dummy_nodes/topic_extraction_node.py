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
    
    # 토픽 추출 프롬프트 (스마트 컨텍스트 버전)
    TOPIC_EXTRACTION_PROMPT = """당신은 팟캐스트 비디오 제작을 위한 이미지 토픽 추출 전문가입니다.

문서 분석 결과에서 **비디오 오버레이용 이미지 생성을 위한 토픽**을 추출하세요.

**토픽 추출 기준**:
✅ 포함: 핵심 개념, 주요 포인트, 구체적 사례, 시각화 가능한 아이디어
❌ 제외: 추상적 개념, 중복 아이디어, 시각화 불가능한 내용

**토픽 개수**: 5-20개 (내용 길이에 따라 조절)

**스타일** (각 토픽마다 하나 선택):
1. **abstract** - 개념적 주제, 배경 이미지
2. **technical** - 다이어그램, 프로세스, 워크플로우
3. **illustration** - 설명 그래픽, 비유적 표현
4. **photo** - 실제 장면, 구체적 예시
5. **scene** - 스토리텔링 장면, 상황 묘사

**⚠️ description 작성 규칙** (매우 중요!):
1. **언어**: 영어로 작성 (이미지 생성 모델 성능 최적화)
2. **정확한 장면 묘사**: 원본 내용을 정확하고 상세하게 설명 (50-100단어)
3. **텍스트 제거**: "no text, text-free" 포함
4. **한국 컨텍스트**: 
   - ✅ 한국 관련 내용만 "Korean", "Seoul", "in Korea" 추가
   - ❌ 서양 문화/역사/동화/인명은 그대로 유지
   
**한국 컨텍스트 적용 기준**:
- ✅ 적용: "한국 기업", "서울", "K-pop", "한국 의사", "국내 산업"
- ❌ 미적용: "신데렐라", "피카소", "파리", "르네상스", "그리스 신화"

**예시 1 - 한국 내용**:
{{
  "title": "AI 헬스케어 혁신",
  "description": "Modern Korean medical professional using advanced AI diagnostic system in a Seoul hospital, holographic medical displays showing patient data, clean clinical environment, professional Korean doctor, no text, realistic photography style"
}}

**예시 2 - 서양 동화**:
{{
  "title": "신데렐라의 변신",
  "description": "Cinderella's magical transformation scene at midnight, sparkling fairy godmother magic turning pumpkin into golden carriage, glass slippers glowing, enchanted atmosphere with stars and sparkles, classic European fairy tale setting, no text, illustrated storybook style"
}}

**예시 3 - 추상 개념**:
{{
  "title": "AI의 미래",
  "description": "Abstract futuristic visualization of artificial intelligence concept, flowing neural networks and data streams in blue and purple tones, geometric patterns and glowing nodes, minimalist modern design, no text, digital art style"
}}

**출력 형식** (JSON만, 마크다운 없이):
[
  {{
    "topic_id": "topic_01",
    "title": "토픽 제목 (한글)",
    "description": "Detailed scene description in English, specific and visual, 50-100 words, no text",
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "style": "abstract",
    "importance": 0.9,
    "context": "맥락 설명 (한글)"
  }}
]

**규칙**:
- topic_id는 순차적 넘버링 (topic_01, topic_02...)
- description은 원본 내용을 정확히 반영, 구체적으로
- keywords는 5-10개 (영어)
- importance는 0.0-1.0 (0.8 이상이 핵심 토픽)
- style은 반드시: abstract, technical, illustration, photo, scene 중 하나

**분석할 요약**:
{summary_content}

위 내용을 분석하여 이미지 토픽을 JSON 배열로 추출하세요. 
원본 내용의 맥락과 의미를 정확히 보존하세요.
JSON만 출력하세요."""

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
            "max_output_tokens": 8192,  # 토큰 제한 증가 (MAX_TOKENS 에러 방지)
            **generation_config
        }
        
        try:
            response = self.model.generate_content(prompt, generation_config=config)
            
            # 응답 확인
            if not response.candidates:
                print("⚠️  응답 후보가 없습니다.")
                return []
            
            candidate = response.candidates[0]
            
            # finish_reason 확인
            if candidate.finish_reason != 1:  # 1 = STOP (정상 완료)
                finish_reason_map = {
                    2: "MAX_TOKENS",
                    3: "SAFETY",
                    4: "RECITATION",
                    5: "OTHER"
                }
                reason = finish_reason_map.get(candidate.finish_reason, "UNKNOWN")
                print(f"⚠️  비정상 종료: {reason}")
                
                if reason == "MAX_TOKENS":
                    print("💡 토큰 제한 초과 - 프롬프트를 줄이거나 max_output_tokens를 더 늘려보세요")
                
                # MAX_TOKENS인 경우 부분 응답이라도 파싱 시도
                if reason == "MAX_TOKENS" and hasattr(candidate.content, 'parts'):
                    try:
                        raw_topics = candidate.content.parts[0].text
                        print(f"⚠️  부분 응답 사용 시도 ({len(raw_topics)} 문자)")
                    except:
                        return []
                else:
                    return []
            else:
                raw_topics = response.text
        
        except Exception as e:
            print(f"❌ Gemini 호출 실패: {str(e)}")
            return []
        
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