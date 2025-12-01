"""
문서 분석 노드 (LangGraph)
Phase 1: 텍스트 기반 단일/멀티 소스 분석
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from vertexai.generative_models import GenerativeModel
import json


@dataclass
class SourceDocument:
    """소스 문서 데이터 클래스"""
    id: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    doc_type: Optional[str] = None  # "text", "pdf", "url" 등


@dataclass
class DocumentAnalysis:
    """문서 분석 결과"""
    source_id: str
    doc_type: str
    core_topic: str
    detailed_summary: str
    key_sentences: List[str]
    keywords: List[str]
    raw_analysis: str


@dataclass
class RelationshipAnalysis:
    """문서 간 관계 분석"""
    common_themes: List[str]
    complementary_content: str
    differences: str
    contradictions: Optional[str]
    mega_topic: str
    raw_analysis: str


@dataclass
class ClusteringResult:
    """클러스터링 결과"""
    topic_clusters: List[Dict[str, Any]]
    sub_clusters: List[Dict[str, Any]]
    raw_analysis: str


@dataclass
class IntegratedSummary:
    """최종 통합 요약"""
    sections: List[Dict[str, Any]]
    conclusion: str
    raw_analysis: str


@dataclass
class CompleteAnalysis:
    """전체 분석 결과"""
    individual_analyses: List[DocumentAnalysis]
    relationship_analysis: Optional[RelationshipAnalysis]
    clustering: ClusteringResult
    integrated_summary: IntegratedSummary
    metadata: Dict[str, Any]


class DocumentAnalysisNode:
    """문서 분석 노드"""
    
    # 프롬프트 템플릿
    ANALYSIS_PROMPT = """당신에게 여러 개의 문서가 입력됩니다. 문서의 형식(PDF, 웹페이지, 기사, 노트, 보고서 등)은 서로 다르며, 길이와 정보량 역시 제각각입니다.
이 문서들을 분석하여, "전문 팟캐스트를 위한 베이스 정보 구조"를 생성하는 것이 목표입니다.
-----------------------------------------
[핵심 목표]
문서 전체를 다음 네 단계로 처리하세요:
1) 문서별 개별 분석  
2) 문서 간 관계 분석  
3) 정보 클러스터링을 통한 전체 구조화  
4) 최종 통합 요약 생성
문서 개수가 많아도 일관된 출력이 유지되도록 하세요.
-----------------------------------------
[출력 형식]
1. 📌 소스별 핵심 분석 (문서 개수만큼 반복)
   - 문서 ID: (문서 명칭 또는 번호)
   - 문서 유형 추정(PDF/웹/보고서 등)
   - **핵심 주제 한 줄 요약**
   - 상세 요약 (5~7문장)
   - 문서에서 가장 중요한 문장 3개 발췌
   - 문서 내 핵심 키워드(5~10개)
---
2. 📌 소스 간 관계 분석
   - 문서들 사이의 공통 주제
   - 서로 보완하는 내용
   - 관점·주장·데이터 차이
   - 모순 또는 충돌 지점(있을 경우)
   - 전체 문서들이 함께 형성하는 "메가 주제"
---
3. 📌 전체 문서 통합 클러스터링  
모든 소스를 하나로 묶어 "자동 주제 클러스터링"을 수행하세요.
아래 구조를 반드시 유지하세요:
### 3-1. 토픽 클러스터(최상위 그룹)
- 클러스터 이름:
- 설명: (1~2문장)
- 포함된 문서 또는 섹션:
- 이 클러스터에서 중요한 핵심 인사이트 3~5개
### 3-2. 서브 클러스터(필요한 만큼)
- 하위 주제 이름:
- 핵심 내용 3~5줄
- 사용자에게 의미 있는 이유
(문서가 많으면 클러스터 수를 자동 조절)
---
4. 📌 최종 통합 요약 (사용자 청취/학습용)
아래 원칙을 지켜 작성하세요:
- 하나의 일관된 문서처럼 자연스럽게 이어지게 작성
- 정보량은 풍부하되 명확하고 간결하게
- 이야기 흐름이 있도록 구성
- 중요한 개념, 트렌드, 인사이트는 빠짐없이 포함
구조는 다음과 같이:
1) 전체 내용을 4~6개 섹션으로 나눈 논리적 구성  
2) 각 섹션은 '주제 한 문장 → 상세 설명 → 핵심 포인트 3개'로 구성  
3) 통합 결론(사용자가 얻어갈 핵심 메시지)
-----------------------------------------
[추가 조건]
- 문서가 1개여도 동일한 구조를 유지하세요.  
- 문서가 10개 이상이어도 요약 품질을 유지하세요.  
- 중복된 정보는 통합하고, 시각 차이는 분명하게 보여주세요.  
- 표면적 요약이 아니라, "구조적 재해석"을 목표로 하세요.
- 문서의 길이·품질·형식이 서로 달라도 일관된 출력 제공.
-----------------------------------------
이제 위 구조에 따라 입력된 모든 소스를 통합 분석하세요.

[입력 문서들]
{documents}

분석을 시작하세요."""
    
    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        """
        Args:
            model_name: 사용할 Gemini 모델
        """
        self.model = GenerativeModel(model_name)
        self.model_name = model_name
    
    def format_documents(self, sources: List[SourceDocument]) -> str:
        """문서들을 프롬프트용 포맷으로 변환"""
        formatted = []
        
        for i, source in enumerate(sources, 1):
            doc_info = f"""
=== 문서 {i} ===
문서 ID: {source.id}
문서 유형: {source.doc_type or "텍스트"}
내용:
{source.content}
{'='*50}
"""
            formatted.append(doc_info)
        
        return "\n".join(formatted)
    
    def analyze_documents(
        self, 
        sources: List[SourceDocument],
        **generation_config
    ) -> CompleteAnalysis:
        """
        문서 분석 실행
        
        Args:
            sources: 분석할 문서 리스트
            **generation_config: Gemini 생성 설정
        
        Returns:
            완전한 분석 결과
        """
        print(f"\n📊 문서 분석 시작: {len(sources)}개 문서")
        
        # 1. 프롬프트 생성
        documents_text = self.format_documents(sources)
        prompt = self.ANALYSIS_PROMPT.format(documents=documents_text)
        
        # 2. Gemini 호출
        print("🤖 Gemini 분석 중...")
        
        config = {
            "temperature": 0.3,  # 일관성 있는 분석
            "top_p": 0.95,
            "max_output_tokens": 8192,
            **generation_config
        }
        
        response = self.model.generate_content(
            prompt,
            generation_config=config
        )
        
        raw_text = response.text
        print(f"✅ 분석 완료 ({len(raw_text)} 문자)")
        
        # 3. 결과 파싱
        print("📝 결과 파싱 중...")
        parsed = self._parse_analysis(raw_text, sources)
        
        return parsed
    
    def _parse_analysis(
        self, 
        raw_text: str, 
        sources: List[SourceDocument]
    ) -> CompleteAnalysis:
        """
        Gemini 응답을 구조화된 데이터로 파싱
        
        Note: 실제로는 더 정교한 파싱이 필요할 수 있음
        현재는 기본 구조만 제공
        """
        # TODO: 실제 파싱 로직 구현
        # 지금은 기본 구조만 반환
        
        # 개별 분석 (임시)
        individual_analyses = []
        for source in sources:
            individual_analyses.append(DocumentAnalysis(
                source_id=source.id,
                doc_type=source.doc_type or "text",
                core_topic="[파싱 필요]",
                detailed_summary="[파싱 필요]",
                key_sentences=["[파싱 필요]"],
                keywords=["[파싱 필요]"],
                raw_analysis=raw_text
            ))
        
        # 관계 분석 (임시)
        relationship_analysis = None
        if len(sources) > 1:
            relationship_analysis = RelationshipAnalysis(
                common_themes=["[파싱 필요]"],
                complementary_content="[파싱 필요]",
                differences="[파싱 필요]",
                contradictions=None,
                mega_topic="[파싱 필요]",
                raw_analysis=raw_text
            )
        
        # 클러스터링 (임시)
        clustering = ClusteringResult(
            topic_clusters=[{
                "name": "[파싱 필요]",
                "description": "[파싱 필요]",
                "documents": [],
                "insights": []
            }],
            sub_clusters=[],
            raw_analysis=raw_text
        )
        
        # 통합 요약 (임시)
        integrated_summary = IntegratedSummary(
            sections=[{
                "title": "[파싱 필요]",
                "content": "[파싱 필요]",
                "key_points": []
            }],
            conclusion="[파싱 필요]",
            raw_analysis=raw_text
        )
        
        return CompleteAnalysis(
            individual_analyses=individual_analyses,
            relationship_analysis=relationship_analysis,
            clustering=clustering,
            integrated_summary=integrated_summary,
            metadata={
                "source_count": len(sources),
                "model": self.model_name,
                "raw_output_length": len(raw_text),
                "raw_output": raw_text  # 전체 원본 저장
            }
        )
    
    def __call__(self, state: dict) -> dict:
        """
        LangGraph 노드 실행
        
        Expected state:
            - sources: List[SourceDocument]
        
        Returns:
            - analysis_result: CompleteAnalysis
        """
        sources = state.get("sources", [])
        
        if not sources:
            raise ValueError("No sources provided for analysis")
        
        result = self.analyze_documents(sources)
        
        return {
            **state,
            "analysis_result": result
        }


# ============================================================================
# 헬퍼 함수
# ============================================================================

def create_source_from_text(text: str, doc_id: str = None) -> SourceDocument:
    """텍스트에서 SourceDocument 생성"""
    import hashlib
    
    if doc_id is None:
        doc_id = hashlib.md5(text[:100].encode()).hexdigest()[:8]
    
    return SourceDocument(
        id=doc_id,
        content=text,
        doc_type="text"
    )


def create_sources_from_texts(texts: List[str]) -> List[SourceDocument]:
    """여러 텍스트에서 SourceDocument 리스트 생성"""
    return [
        create_source_from_text(text, f"doc_{i+1}")
        for i, text in enumerate(texts)
    ]


def save_analysis_to_json(analysis: CompleteAnalysis, output_path: str):
    """분석 결과를 JSON 파일로 저장"""
    import json
    from dataclasses import asdict
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(analysis), f, ensure_ascii=False, indent=2)
    
    print(f"💾 분석 결과 저장: {output_path}")


def print_analysis_summary(analysis: CompleteAnalysis):
    """분석 결과 요약 출력"""
    print("\n" + "="*80)
    print("📊 문서 분석 결과 요약")
    print("="*80)
    
    print(f"\n📄 분석된 문서 수: {len(analysis.individual_analyses)}")
    print(f"🤖 사용 모델: {analysis.metadata.get('model')}")
    print(f"📝 원본 출력 길이: {analysis.metadata.get('raw_output_length')} 문자")
    
    print("\n" + "-"*80)
    print("📌 개별 문서 분석")
    print("-"*80)
    for i, doc_analysis in enumerate(analysis.individual_analyses, 1):
        print(f"\n[문서 {i}] {doc_analysis.source_id}")
        print(f"  유형: {doc_analysis.doc_type}")
        print(f"  핵심 주제: {doc_analysis.core_topic}")
    
    if analysis.relationship_analysis:
        print("\n" + "-"*80)
        print("📌 문서 간 관계")
        print("-"*80)
        print(f"메가 주제: {analysis.relationship_analysis.mega_topic}")
    
    print("\n" + "-"*80)
    print("📌 클러스터링")
    print("-"*80)
    print(f"토픽 클러스터 수: {len(analysis.clustering.topic_clusters)}")
    print(f"서브 클러스터 수: {len(analysis.clustering.sub_clusters)}")
    
    print("\n" + "-"*80)
    print("📌 통합 요약")
    print("-"*80)
    print(f"섹션 수: {len(analysis.integrated_summary.sections)}")
    
    print("\n" + "="*80)
    print("💡 전체 원본 출력은 metadata['raw_output']에서 확인하세요")
    print("="*80)
