"""
Phase 1 테스트: 단일/멀티 텍스트 분석
백엔드 단계별 테스트
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 path 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.nodes.document_analysis_node import (
    DocumentAnalysisNode,
    SourceDocument,
    create_source_from_text,
    create_sources_from_texts,
    save_analysis_to_json,
    print_analysis_summary
)


# ============================================================================
# 테스트 문서 샘플
# ============================================================================

SAMPLE_TEXT_1 = """
AI 기술의 발전과 미래 전망

인공지능(AI) 기술은 최근 몇 년 사이 급격한 발전을 이루었습니다. 특히 대규모 언어 모델(LLM)의 등장으로 
자연어 처리 분야에서 혁신적인 성과를 보이고 있습니다. 

GPT, Claude, Gemini 등의 모델들은 텍스트 생성, 번역, 요약, 질의응답 등 다양한 작업을 수행할 수 있으며,
그 정확도와 자연스러움은 이전 세대 모델들과 비교할 수 없을 정도로 향상되었습니다.

현재 AI 기술은 의료, 금융, 교육, 제조업 등 거의 모든 산업 분야에 적용되고 있습니다.
특히 의료 분야에서는 질병 진단, 신약 개발, 환자 데이터 분석 등에 AI가 활용되어 
진단의 정확도를 높이고 치료 효율을 개선하고 있습니다.

그러나 AI 기술의 발전과 함께 윤리적 문제도 대두되고 있습니다.
데이터 프라이버시, 알고리즘 편향성, 일자리 대체 등의 문제는 
AI 기술을 사회에 도입하는 과정에서 반드시 고려해야 할 사항들입니다.

전문가들은 향후 5년 내에 AI 기술이 현재보다 훨씬 더 발전하여 
AGI(Artificial General Intelligence)에 한 걸음 더 다가갈 것으로 예측하고 있습니다.
이러한 기술 발전은 인류에게 새로운 기회를 제공하는 동시에 
새로운 도전과제를 던질 것으로 보입니다.
"""

SAMPLE_TEXT_2 = """
머신러닝과 딥러닝의 이해

머신러닝(Machine Learning)은 컴퓨터가 명시적으로 프로그래밍되지 않고도 
데이터로부터 학습하여 패턴을 찾고 예측을 수행하는 기술입니다.

머신러닝의 주요 학습 방식은 세 가지로 나뉩니다:
1. 지도 학습(Supervised Learning): 레이블이 있는 데이터로 학습
2. 비지도 학습(Unsupervised Learning): 레이블 없는 데이터에서 패턴 발견
3. 강화 학습(Reinforcement Learning): 보상을 통한 시행착오 학습

딥러닝(Deep Learning)은 머신러닝의 한 분야로, 인공 신경망을 여러 층으로 쌓아
복잡한 패턴을 학습하는 기법입니다. 특히 이미지 인식, 음성 인식, 자연어 처리 등의
분야에서 탁월한 성능을 보이고 있습니다.

딥러닝의 핵심 구조인 신경망은 인간의 뇌 구조에서 영감을 받았습니다.
입력층, 은닉층, 출력층으로 구성되며, 각 층의 뉴런들이 가중치와 활성화 함수를 통해
정보를 처리합니다.

최근에는 트랜스포머(Transformer) 아키텍처가 등장하면서 자연어 처리 분야에 
혁명적인 변화가 일어났습니다. BERT, GPT 시리즈 등이 모두 트랜스포머 기반 모델이며,
어텐션(Attention) 메커니즘을 통해 문맥을 효과적으로 이해합니다.

머신러닝과 딥러닝 기술은 계속 발전하고 있으며, 앞으로도 더 많은 혁신이 
기대되는 분야입니다.
"""

SAMPLE_TEXT_3 = """
AI 윤리와 규제

AI 기술이 사회 전반에 빠르게 확산되면서 윤리적 고려사항과 규제의 필요성이 
점점 더 중요해지고 있습니다.

주요 AI 윤리 이슈는 다음과 같습니다:

1. 데이터 프라이버시
개인정보 보호는 AI 시스템 개발에서 가장 중요한 고려사항 중 하나입니다.
AI 모델을 학습시키기 위해서는 대량의 데이터가 필요한데, 
이 과정에서 개인정보가 무단으로 수집되거나 오용될 위험이 있습니다.

2. 알고리즘 편향성
AI 시스템은 학습 데이터의 편향을 그대로 학습할 수 있습니다.
예를 들어, 채용 AI가 특정 성별이나 인종을 차별하는 결과를 낳을 수 있으며,
이는 사회적 불평등을 심화시킬 수 있습니다.

3. 투명성과 설명가능성
많은 AI 모델, 특히 딥러닝 모델은 "블랙박스"로 작동합니다.
왜 그러한 결정을 내렸는지 설명하기 어려운 경우가 많아,
중요한 의사결정에 AI를 사용할 때 신뢰성 문제가 발생합니다.

4. 책임과 책무
AI 시스템이 잘못된 결정을 내렸을 때 누가 책임을 져야 하는가?
개발자, 사용자, 기업, 아니면 AI 자체인가? 
이는 법적, 윤리적으로 복잡한 문제입니다.

각국 정부와 국제기구들은 AI 규제 프레임워크를 개발하고 있습니다.
유럽연합의 AI Act, 미국의 AI 권리장전, 한국의 AI 윤리기준 등이 
대표적인 예입니다.

AI 윤리는 기술 발전만큼이나 중요하며, 지속가능한 AI 발전을 위해서는
기술과 윤리가 함께 발전해야 합니다.
"""


# ============================================================================
# 테스트 함수들
# ============================================================================

def test_single_document():
    """테스트 1: 단일 문서 분석"""
    print("\n" + "="*80)
    print("🧪 테스트 1: 단일 문서 분석")
    print("="*80)
    
    # 분석 노드 초기화
    analyzer = DocumentAnalysisNode(model_name="gemini-2.5-flash")
    
    # 단일 문서 생성
    source = create_source_from_text(SAMPLE_TEXT_1, "ai_technology_overview")
    
    # 분석 실행
    result = analyzer.analyze_documents([source])
    
    # 결과 출력
    print_analysis_summary(result)
    
    # 원본 출력 확인
    print("\n" + "="*80)
    print("📄 Gemini 원본 출력")
    print("="*80)
    print(result.metadata['raw_output'])
    
    # JSON 저장
    save_analysis_to_json(result, "./test_output/single_doc_analysis.json")
    
    return result


def test_multi_documents():
    """테스트 2: 멀티 문서 분석 (3개)"""
    print("\n" + "="*80)
    print("🧪 테스트 2: 멀티 문서 분석 (3개 문서)")
    print("="*80)
    
    # 분석 노드 초기화
    analyzer = DocumentAnalysisNode(model_name="gemini-2.5-flash")
    
    # 여러 문서 생성
    sources = [
        SourceDocument(id="doc_1_ai_overview", content=SAMPLE_TEXT_1, doc_type="text"),
        SourceDocument(id="doc_2_ml_dl", content=SAMPLE_TEXT_2, doc_type="text"),
        SourceDocument(id="doc_3_ai_ethics", content=SAMPLE_TEXT_3, doc_type="text"),
    ]
    
    # 분석 실행
    result = analyzer.analyze_documents(sources)
    
    # 결과 출력
    print_analysis_summary(result)
    
    # 원본 출력 확인
    print("\n" + "="*80)
    print("📄 Gemini 원본 출력")
    print("="*80)
    print(result.metadata['raw_output'])
    
    # JSON 저장
    save_analysis_to_json(result, "./test_output/multi_doc_analysis.json")
    
    return result


def test_custom_text():
    """테스트 3: 사용자 커스텀 텍스트 입력"""
    print("\n" + "="*80)
    print("🧪 테스트 3: 커스텀 텍스트 입력")
    print("="*80)
    
    print("\n텍스트를 입력하세요 (완료하려면 빈 줄에서 Ctrl+D 또는 Ctrl+Z):")
    print("-" * 80)
    
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    
    custom_text = "\n".join(lines)
    
    if not custom_text.strip():
        print("⚠️  텍스트가 입력되지 않았습니다. 샘플 텍스트를 사용합니다.")
        custom_text = SAMPLE_TEXT_1
    
    # 분석 노드 초기화
    analyzer = DocumentAnalysisNode(model_name="gemini-2.5-flash")
    
    # 문서 생성
    source = create_source_from_text(custom_text, "custom_input")
    
    # 분석 실행
    result = analyzer.analyze_documents([source])
    
    # 결과 출력
    print_analysis_summary(result)
    
    # 원본 출력 확인
    print("\n" + "="*80)
    print("📄 Gemini 원본 출력")
    print("="*80)
    print(result.metadata['raw_output'])
    
    # JSON 저장
    save_analysis_to_json(result, "./test_output/custom_text_analysis.json")
    
    return result


def test_langgraph_node():
    """테스트 4: LangGraph 노드로 실행"""
    print("\n" + "="*80)
    print("🧪 테스트 4: LangGraph 노드 형식으로 실행")
    print("="*80)
    
    # 분석 노드 초기화
    analyzer = DocumentAnalysisNode(model_name="gemini-2.5-flash")
    
    # State 준비
    state = {
        "sources": [
            SourceDocument(id="doc_1", content=SAMPLE_TEXT_1, doc_type="text"),
            SourceDocument(id="doc_2", content=SAMPLE_TEXT_2, doc_type="text"),
        ]
    }
    
    # 노드 실행 (__call__ 메서드)
    result_state = analyzer(state)
    
    # 결과 확인
    print("✅ LangGraph 노드 실행 완료")
    print(f"State keys: {list(result_state.keys())}")
    
    analysis_result = result_state['analysis_result']
    print_analysis_summary(analysis_result)
    
    # 원본 출력
    print("\n" + "="*80)
    print("📄 Gemini 원본 출력")
    print("="*80)
    print(analysis_result.metadata['raw_output'])
    
    return result_state


def test_edge_cases():
    """테스트 5: 엣지 케이스"""
    print("\n" + "="*80)
    print("🧪 테스트 5: 엣지 케이스")
    print("="*80)
    
    analyzer = DocumentAnalysisNode(model_name="gemini-2.5-flash")
    
    # 케이스 1: 매우 짧은 텍스트
    print("\n--- 케이스 1: 매우 짧은 텍스트 ---")
    short_source = create_source_from_text(
        "AI는 미래다.", 
        "very_short"
    )
    result1 = analyzer.analyze_documents([short_source])
    print(f"✅ 완료 (출력 길이: {len(result1.metadata['raw_output'])})")
    
    # 케이스 2: 매우 긴 텍스트
    print("\n--- 케이스 2: 긴 텍스트 (반복) ---")
    long_text = SAMPLE_TEXT_1 + "\n\n" + SAMPLE_TEXT_2 + "\n\n" + SAMPLE_TEXT_3
    long_text = long_text * 3  # 3배 반복
    long_source = create_source_from_text(long_text, "very_long")
    result2 = analyzer.analyze_documents([long_source])
    print(f"✅ 완료 (출력 길이: {len(result2.metadata['raw_output'])})")
    
    # 케이스 3: 많은 문서 (10개)
    print("\n--- 케이스 3: 많은 문서 (10개) ---")
    many_sources = create_sources_from_texts([
        SAMPLE_TEXT_1, SAMPLE_TEXT_2, SAMPLE_TEXT_3,
        SAMPLE_TEXT_1, SAMPLE_TEXT_2, SAMPLE_TEXT_3,
        SAMPLE_TEXT_1, SAMPLE_TEXT_2, SAMPLE_TEXT_3,
        SAMPLE_TEXT_1
    ])
    result3 = analyzer.analyze_documents(many_sources)
    print(f"✅ 완료 (출력 길이: {len(result3.metadata['raw_output'])})")
    
    print("\n" + "="*80)
    print("✅ 모든 엣지 케이스 테스트 완료")
    print("="*80)


# ============================================================================
# 메인 실행
# ============================================================================

def main():
    """메인 테스트 실행"""
    print("="*80)
    print("🚀 Phase 1: 단일/멀티 텍스트 분석 테스트")
    print("="*80)
    
    # 출력 폴더 생성
    os.makedirs("./test_output", exist_ok=True)
    
    print("\n테스트 선택:")
    print("1. 단일 문서 분석")
    print("2. 멀티 문서 분석 (3개)")
    print("3. 커스텀 텍스트 입력")
    print("4. LangGraph 노드 형식")
    print("5. 엣지 케이스")
    print("6. 전체 테스트")
    
    choice = input("\n번호 입력 (1-6): ").strip()
    
    try:
        if choice == "1":
            test_single_document()
        elif choice == "2":
            test_multi_documents()
        elif choice == "3":
            test_custom_text()
        elif choice == "4":
            test_langgraph_node()
        elif choice == "5":
            test_edge_cases()
        elif choice == "6":
            print("\n🚀 전체 테스트 시작!\n")
            test_single_document()
            input("\n계속하려면 Enter...")
            test_multi_documents()
            input("\n계속하려면 Enter...")
            test_langgraph_node()
            input("\n계속하려면 Enter...")
            test_edge_cases()
        else:
            print("❌ 잘못된 입력입니다.")
    
    except Exception as e:
        print(f"\n❌ 에러 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("✨ 테스트 완료!")
    print("📁 출력 파일: ./test_output/")
    print("="*80)


if __name__ == "__main__":
    # Vertex AI 초기화 (credentials 필요)
    import vertexai
    
    vertexai.init(
        project="alan-document-lab",
        location="us-central1"
    )
    
    main()
