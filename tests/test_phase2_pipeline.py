"""
Phase 2 통합 테스트: 텍스트 → 이미지 전체 파이프라인
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.abspath('.'))

from app.pipelines.pipeline_phase2 import (
    DocumentToImagePipeline,
    quick_pipeline,
    batch_pipeline
)
from app.nodes.document_analysis_node import SourceDocument
import vertexai


# ============================================================================
# 테스트 샘플 텍스트
# ============================================================================

SAMPLE_TEXT_SHORT = """
AI 기술의 미래

인공지능(AI) 기술은 빠르게 발전하고 있습니다. 
머신러닝과 딥러닝의 발전으로 다양한 분야에 적용되고 있으며,
특히 자연어 처리, 이미지 인식, 음성 인식 등에서 혁신적인 성과를 보이고 있습니다.

앞으로 AI는 의료, 교육, 금융 등 모든 산업을 변화시킬 것으로 예상됩니다.
그러나 윤리적 문제와 일자리 대체 등의 과제도 함께 고려해야 합니다.
"""

SAMPLE_TEXT_LONG = """
인공지능의 역사와 발전

1. 초기 AI (1950-1970년대)
인공지능이라는 용어는 1956년 다트머스 회의에서 처음 사용되었습니다.
초기 AI 연구는 주로 논리적 추론과 문제 해결에 집중했습니다.
그러나 당시 컴퓨팅 파워의 한계로 실용적인 응용은 제한적이었습니다.

2. AI의 겨울 (1970-1990년대)
1970년대와 1980년대에 AI 연구는 두 번의 "AI 겨울"을 겪었습니다.
과도한 기대와 실망이 반복되면서 연구 자금이 크게 줄어들었습니다.
그러나 이 시기에도 전문가 시스템과 같은 실용적인 AI가 등장했습니다.

3. 머신러닝의 부상 (1990-2010년대)
1990년대부터 머신러닝 기법이 주목받기 시작했습니다.
특히 서포트 벡터 머신(SVM)과 랜덤 포레스트 같은 알고리즘이 발전했습니다.
데이터가 증가하고 컴퓨팅 파워가 향상되면서 실용적인 응용이 가능해졌습니다.

4. 딥러닝 혁명 (2010년대-현재)
2012년 ImageNet 대회에서 딥러닝 모델이 획기적인 성과를 거두면서
AI 분야에 새로운 혁명이 일어났습니다.

딥러닝은 다음 분야에서 특히 뛰어난 성과를 보였습니다:
- 이미지 인식: 얼굴 인식, 객체 탐지, 의료 영상 분석
- 자연어 처리: 번역, 요약, 질의응답
- 음성 인식: 음성 비서, 자동 자막 생성
- 게임: AlphaGo의 바둑 정복

5. 대규모 언어 모델 시대 (2020년대)
GPT, BERT, Claude 등 대규모 언어 모델의 등장으로
AI는 인간 수준의 언어 이해와 생성 능력을 보여주고 있습니다.
이러한 모델들은 거의 모든 텍스트 기반 작업에서 뛰어난 성능을 발휘합니다.

6. 미래 전망
향후 AI는 다음과 같은 방향으로 발전할 것으로 예상됩니다:
- AGI(인공 일반 지능)를 향한 발전
- 멀티모달 AI (텍스트, 이미지, 음성 통합)
- 설명 가능한 AI (Explainable AI)
- 윤리적이고 공정한 AI

그러나 AI 발전과 함께 다음과 같은 도전 과제도 존재합니다:
- 데이터 프라이버시 보호
- 알고리즘 편향성 제거
- 일자리 변화에 대한 대응
- AI의 악용 방지

결론적으로, AI 기술은 계속 발전하고 있으며
우리 사회의 모든 영역에 깊은 영향을 미칠 것입니다.
이러한 변화에 대비하고 긍정적인 방향으로 이끌어가는 것이 중요합니다.
"""

SAMPLE_MULTI_TEXTS = [
    """
AI 기초 개념
인공지능은 컴퓨터가 인간처럼 학습하고 추론하며 문제를 해결하는 기술입니다.
머신러닝과 딥러닝은 AI의 핵심 기술이며, 데이터를 통해 패턴을 학습합니다.
    """,
    """
AI의 실제 응용
AI는 의료 진단, 자율주행차, 음성 비서, 추천 시스템 등에 활용되고 있습니다.
특히 의료 분야에서는 질병 조기 진단과 신약 개발에 큰 도움을 주고 있습니다.
    """,
    """
AI 윤리
AI 기술이 발전하면서 윤리적 문제가 대두되고 있습니다.
알고리즘 편향성, 프라이버시 침해, 일자리 대체 등이 주요 관심사입니다.
    """
]


# ============================================================================
# 테스트 함수들
# ============================================================================

def test_quick_pipeline():
    """빠른 파이프라인 테스트"""
    print("\n" + "="*80)
    print("🧪 테스트 1: 빠른 파이프라인 (짧은 텍스트)")
    print("="*80)
    
    result = quick_pipeline(
        text=SAMPLE_TEXT_SHORT,
        output_dir="./test_output/quick",
        generation_strategy="fast"  # Gemini만 사용
    )
    
    print(f"\n✅ 완료!")
    print(f"   이미지: {len(result['images'])}개")
    print(f"   갤러리: {result['paths']['gallery_html']}")


def test_full_pipeline():
    """전체 파이프라인 테스트 (긴 텍스트)"""
    print("\n" + "="*80)
    print("🧪 테스트 2: 전체 파이프라인 (긴 텍스트)")
    print("="*80)
    
    vertexai.init(
        project="alan-document-lab",
        location="us-central1"
    )
    
    pipeline = DocumentToImagePipeline(
        output_dir="./test_output/full",
        image_default_method="gemini"
    )
    
    sources = [
        SourceDocument(
            id="ai_history",
            content=SAMPLE_TEXT_LONG,
            doc_type="text"
        )
    ]
    
    result = pipeline.run(
        sources=sources,
        min_topics=8,
        max_topics=15,
        generation_strategy="auto"
    )
    
    print(f"\n✅ 완료!")
    print(f"   토픽: {len(result['topics'])}개")
    print(f"   이미지: {len(result['images'])}개")
    print(f"   갤러리: {result['paths']['gallery_html']}")


def test_batch_pipeline():
    """배치 파이프라인 테스트 (멀티 텍스트)"""
    print("\n" + "="*80)
    print("🧪 테스트 3: 배치 파이프라인 (3개 텍스트)")
    print("="*80)
    
    result = batch_pipeline(
        texts=SAMPLE_MULTI_TEXTS,
        output_dir="./test_output/batch",
        generation_strategy="hybrid"  # 중요도에 따라 혼합
    )
    
    print(f"\n✅ 완료!")
    print(f"   토픽: {len(result['topics'])}개")
    print(f"   이미지: {len(result['images'])}개")
    print(f"   갤러리: {result['paths']['gallery_html']}")


def test_custom_text():
    """사용자 입력 텍스트 테스트"""
    print("\n" + "="*80)
    print("🧪 테스트 4: 커스텀 텍스트 입력")
    print("="*80)
    
    print("\n분석할 텍스트를 입력하세요:")
    print("(여러 줄 입력 가능, 완료하려면 빈 줄에 'END' 입력)")
    print("-" * 80)
    
    lines = []
    while True:
        line = input()
        if line.strip().upper() == 'END':
            break
        lines.append(line)
    
    content = "\n".join(lines)
    
    if not content.strip():
        print("⚠️  입력이 없습니다. 샘플 텍스트를 사용합니다.")
        content = SAMPLE_TEXT_SHORT
    
    print("\n생성 전략 선택:")
    print("1. fast (빠름 - Gemini만)")
    print("2. quality (고품질 - Imagen 4만)")
    print("3. auto (자동 - 스타일에 따라)")
    print("4. hybrid (혼합 - 중요도에 따라)")
    
    strategy_choice = input("\n번호 입력 (1-4, 기본=3): ").strip()
    strategy_map = {
        "1": "fast",
        "2": "quality",
        "3": "auto",
        "4": "hybrid"
    }
    strategy = strategy_map.get(strategy_choice, "auto")
    
    print(f"\n선택된 전략: {strategy}")
    print("파이프라인 실행 중...")
    
    result = quick_pipeline(
        text=content,
        output_dir="./test_output/custom",
        generation_strategy=strategy
    )
    
    print(f"\n✅ 완료!")
    print(f"   토픽: {len(result['topics'])}개")
    print(f"   이미지: {len(result['images'])}개")
    print(f"   갤러리: {result['paths']['gallery_html']}")


def test_strategy_comparison():
    """전략 비교 테스트"""
    print("\n" + "="*80)
    print("🧪 테스트 5: 전략 비교 (fast vs quality)")
    print("="*80)
    
    vertexai.init(
        project="alan-document-lab",
        location="us-central1"
    )
    
    strategies = [
        ("fast", "Gemini만 (빠름)"),
        ("quality", "Imagen 4만 (고품질)")
    ]
    
    for strategy, desc in strategies:
        print(f"\n{'='*80}")
        print(f"전략: {strategy} - {desc}")
        print(f"{'='*80}")
        
        pipeline = DocumentToImagePipeline(
            output_dir=f"./test_output/strategy_{strategy}"
        )
        
        sources = [
            SourceDocument(
                id="test_doc",
                content=SAMPLE_TEXT_SHORT,
                doc_type="text"
            )
        ]
        
        result = pipeline.run(
            sources=sources,
            min_topics=3,
            max_topics=5,
            generation_strategy=strategy
        )
        
        print(f"\n✅ {strategy} 완료: {len(result['images'])}개 이미지")
    
    print("\n" + "="*80)
    print("비교:")
    print("  fast: ./test_output/strategy_fast/gallery.html")
    print("  quality: ./test_output/strategy_quality/gallery.html")
    print("="*80)


def test_topic_extraction_only():
    """토픽 추출만 테스트 (이미지 생성 안 함)"""
    print("\n" + "="*80)
    print("🧪 테스트 6: 토픽 추출만 (이미지 X)")
    print("="*80)
    
    vertexai.init(
        project="alan-document-lab",
        location="us-central1"
    )
    
    from app.nodes.document_analysis_node import DocumentAnalysisNode
    from app.nodes.topic_extraction_node import TopicExtractionNode
    from dataclasses import asdict
    
    # Step 1: 분석
    print("\n1. 문서 분석 중...")
    analyzer = DocumentAnalysisNode()
    sources = [SourceDocument(id="doc", content=SAMPLE_TEXT_LONG, doc_type="text")]
    analysis = analyzer.analyze_documents(sources)
    
    # Step 2: 토픽 추출
    print("\n2. 토픽 추출 중...")
    topic_extractor = TopicExtractionNode()
    topics = topic_extractor.extract_topics_from_analysis(
        asdict(analysis),
        min_topics=5,
        max_topics=15
    )
    
    # 결과 출력
    from app.nodes.topic_extraction_node import print_topics_summary, save_topics_to_json
    print_topics_summary(topics)
    
    # JSON 저장
    os.makedirs("./test_output/topics_only", exist_ok=True)
    save_topics_to_json(topics, "./test_output/topics_only/topics.json")
    
    print("\n✅ 토픽 추출 완료 (이미지 생성하지 않음)")


# ============================================================================
# 메인 실행
# ============================================================================

def main():
    """메인 테스트 실행"""
    print("="*80)
    print("🚀 Phase 2: 텍스트 → 이미지 파이프라인 테스트")
    print("="*80)
    
    # 출력 폴더 생성
    os.makedirs("./test_output", exist_ok=True)
    
    print("\n⚠️  주의: 이미지 생성은 시간이 걸립니다!")
    print("   - 짧은 텍스트: 약 2-3분")
    print("   - 긴 텍스트: 약 5-10분")
    print()
    
    print("테스트 선택:")
    print("1. 빠른 파이프라인 (짧은 텍스트, 3개 이미지)")
    print("2. 전체 파이프라인 (긴 텍스트, 10개 이미지)")
    print("3. 배치 파이프라인 (3개 텍스트)")
    print("4. 커스텀 텍스트 입력")
    print("5. 전략 비교 (fast vs quality)")
    print("6. 토픽 추출만 (이미지 생성 안 함)")
    
    choice = input("\n번호 입력 (1-6): ").strip()
    
    try:
        if choice == "1":
            test_quick_pipeline()
        elif choice == "2":
            test_full_pipeline()
        elif choice == "3":
            test_batch_pipeline()
        elif choice == "4":
            test_custom_text()
        elif choice == "5":
            test_strategy_comparison()
        elif choice == "6":
            test_topic_extraction_only()
        else:
            print("❌ 잘못된 입력입니다.")
    
    except Exception as e:
        print(f"\n❌ 에러 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("✨ 테스트 완료!")
    print("📁 출력 폴더: ./test_output/")
    print("🌐 브라우저에서 gallery.html을 열어보세요!")
    print("="*80)


if __name__ == "__main__":
    # Vertex AI 초기화
    vertexai.init(
        project="alan-document-lab",
        location="us-central1"
    )
    
    main()
