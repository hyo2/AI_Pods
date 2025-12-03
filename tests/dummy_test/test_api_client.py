"""
API 테스트 클라이언트
백엔드 API 엔드포인트 테스트
"""

import requests
import json
from typing import List, Dict, Any


class DocumentAnalysisClient:
    """문서 분석 API 클라이언트"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def health_check(self) -> Dict:
        """헬스 체크"""
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def analyze(
        self, 
        sources: List[Dict[str, Any]],
        model_name: str = "gemini-2.5-flash"
    ) -> Dict:
        """전체 분석"""
        payload = {
            "sources": sources,
            "model_name": model_name
        }
        
        response = self.session.post(
            f"{self.base_url}/api/v1/analyze",
            json=payload,
            timeout=120  # 2분 타임아웃
        )
        response.raise_for_status()
        return response.json()
    
    def quick_analyze(self, content: str) -> Dict:
        """빠른 분석"""
        payload = {
            "content": content
        }
        
        response = self.session.post(
            f"{self.base_url}/api/v1/analyze/quick",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        return response.json()
    
    def raw_analyze(self, sources: List[Dict[str, Any]]) -> Dict:
        """원본 출력만"""
        payload = {
            "sources": sources
        }
        
        response = self.session.post(
            f"{self.base_url}/api/v1/analyze/raw",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        return response.json()


# ============================================================================
# 테스트 샘플 데이터
# ============================================================================

SAMPLE_SOURCES_SINGLE = [
    {
        "id": "ai_overview",
        "content": """
AI 기술의 발전과 미래 전망

인공지능(AI) 기술은 최근 몇 년 사이 급격한 발전을 이루었습니다. 
특히 대규모 언어 모델(LLM)의 등장으로 자연어 처리 분야에서 혁신적인 성과를 보이고 있습니다.

현재 AI 기술은 의료, 금융, 교육, 제조업 등 거의 모든 산업 분야에 적용되고 있습니다.
그러나 AI 기술의 발전과 함께 윤리적 문제도 대두되고 있습니다.

전문가들은 향후 5년 내에 AI 기술이 현재보다 훨씬 더 발전하여 
AGI(Artificial General Intelligence)에 한 걸음 더 다가갈 것으로 예측하고 있습니다.
        """,
        "doc_type": "text"
    }
]

SAMPLE_SOURCES_MULTI = [
    {
        "id": "ai_overview",
        "content": """
AI 기술의 발전과 미래 전망
인공지능 기술은 급격히 발전하고 있으며, 모든 산업에 적용되고 있습니다.
        """,
        "doc_type": "text"
    },
    {
        "id": "ml_basics",
        "content": """
머신러닝과 딥러닝
머신러닝은 데이터로부터 학습하여 패턴을 찾는 기술입니다.
딥러닝은 신경망을 여러 층으로 쌓아 복잡한 패턴을 학습합니다.
        """,
        "doc_type": "text"
    },
    {
        "id": "ai_ethics",
        "content": """
AI 윤리와 규제
AI 기술 확산과 함께 윤리적 고려사항이 중요해지고 있습니다.
데이터 프라이버시, 알고리즘 편향성, 투명성 등이 주요 이슈입니다.
        """,
        "doc_type": "text"
    }
]


# ============================================================================
# 테스트 함수들
# ============================================================================

def test_health_check():
    """헬스 체크 테스트"""
    print("\n" + "="*80)
    print("🧪 테스트: 헬스 체크")
    print("="*80)
    
    client = DocumentAnalysisClient()
    result = client.health_check()
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("✅ 헬스 체크 성공")


def test_quick_analyze():
    """빠른 분석 테스트"""
    print("\n" + "="*80)
    print("🧪 테스트: 빠른 분석")
    print("="*80)
    
    client = DocumentAnalysisClient()
    
    content = "AI는 미래의 핵심 기술입니다. 모든 산업에 혁신을 가져올 것입니다."
    
    print(f"입력 텍스트: {content[:50]}...")
    print("분석 중...")
    
    result = client.quick_analyze(content)
    
    print(f"\n✅ {result['message']}")
    
    # 원본 출력 확인
    raw_output = result['data']['metadata']['raw_output']
    print("\n📄 Gemini 원본 출력:")
    print("-" * 80)
    print(raw_output[:500] + "..." if len(raw_output) > 500 else raw_output)
    
    # JSON 저장
    with open("./test_output/api_quick_analysis.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print("\n💾 결과 저장: ./test_output/api_quick_analysis.json")


def test_single_document():
    """단일 문서 분석 테스트"""
    print("\n" + "="*80)
    print("🧪 테스트: 단일 문서 전체 분석")
    print("="*80)
    
    client = DocumentAnalysisClient()
    
    print("분석 중...")
    result = client.analyze(SAMPLE_SOURCES_SINGLE)
    
    print(f"\n✅ {result['message']}")
    
    # 원본 출력 확인
    raw_output = result['data']['metadata']['raw_output']
    print("\n📄 Gemini 원본 출력:")
    print("-" * 80)
    print(raw_output)
    
    # JSON 저장
    with open("./test_output/api_single_doc.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print("\n💾 결과 저장: ./test_output/api_single_doc.json")


def test_multi_documents():
    """멀티 문서 분석 테스트"""
    print("\n" + "="*80)
    print("🧪 테스트: 멀티 문서 전체 분석 (3개)")
    print("="*80)
    
    client = DocumentAnalysisClient()
    
    print(f"문서 개수: {len(SAMPLE_SOURCES_MULTI)}")
    print("분석 중...")
    
    result = client.analyze(SAMPLE_SOURCES_MULTI)
    
    print(f"\n✅ {result['message']}")
    
    # 원본 출력 확인
    raw_output = result['data']['metadata']['raw_output']
    print("\n📄 Gemini 원본 출력:")
    print("-" * 80)
    print(raw_output)
    
    # JSON 저장
    with open("./test_output/api_multi_docs.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print("\n💾 결과 저장: ./test_output/api_multi_docs.json")


def test_raw_output():
    """원본 출력만 테스트"""
    print("\n" + "="*80)
    print("🧪 테스트: 원본 출력만 (파싱 없이)")
    print("="*80)
    
    client = DocumentAnalysisClient()
    
    print("분석 중...")
    result = client.raw_analyze(SAMPLE_SOURCES_MULTI)
    
    print(f"\n✅ 성공 (문서 {result['source_count']}개)")
    
    # 원본 출력
    print("\n📄 Gemini 원본 출력:")
    print("-" * 80)
    print(result['raw_output'])
    
    # 저장
    with open("./test_output/api_raw_output.txt", "w", encoding="utf-8") as f:
        f.write(result['raw_output'])
    
    print("\n💾 원본 출력 저장: ./test_output/api_raw_output.txt")


def test_custom_input():
    """사용자 입력 테스트"""
    print("\n" + "="*80)
    print("🧪 테스트: 사용자 커스텀 입력")
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
        print("⚠️  입력이 없습니다.")
        return
    
    client = DocumentAnalysisClient()
    
    print("\n분석 중...")
    result = client.quick_analyze(content)
    
    print(f"\n✅ {result['message']}")
    
    # 원본 출력
    raw_output = result['data']['metadata']['raw_output']
    print("\n📄 Gemini 원본 출력:")
    print("-" * 80)
    print(raw_output)


def test_error_handling():
    """에러 핸들링 테스트"""
    print("\n" + "="*80)
    print("🧪 테스트: 에러 핸들링")
    print("="*80)
    
    client = DocumentAnalysisClient()
    
    # 케이스 1: 빈 소스
    print("\n--- 케이스 1: 빈 소스 리스트 ---")
    try:
        result = client.analyze([])
        print("❌ 에러가 발생하지 않음 (예상치 못함)")
    except requests.exceptions.HTTPError as e:
        print(f"✅ 예상된 에러 발생: {e.response.status_code}")
        print(f"   메시지: {e.response.json().get('detail')}")
    
    # 케이스 2: 잘못된 엔드포인트
    print("\n--- 케이스 2: 잘못된 엔드포인트 ---")
    try:
        response = requests.get(f"{client.base_url}/api/v1/nonexistent")
        response.raise_for_status()
        print("❌ 에러가 발생하지 않음 (예상치 못함)")
    except requests.exceptions.HTTPError as e:
        print(f"✅ 예상된 에러 발생: {e.response.status_code}")
    
    print("\n✅ 에러 핸들링 테스트 완료")


# ============================================================================
# 메인 실행
# ============================================================================

def main():
    """메인 테스트"""
    import os
    
    print("="*80)
    print("🧪 API 테스트 클라이언트")
    print("="*80)
    
    # 출력 폴더 생성
    os.makedirs("./test_output", exist_ok=True)
    
    print("\n⚠️  서버가 실행 중인지 확인하세요:")
    print("   python api_phase1.py")
    print()
    
    print("테스트 선택:")
    print("1. 헬스 체크")
    print("2. 빠른 분석")
    print("3. 단일 문서 분석")
    print("4. 멀티 문서 분석")
    print("5. 원본 출력만")
    print("6. 커스텀 입력")
    print("7. 에러 핸들링")
    print("8. 전체 테스트")
    
    choice = input("\n번호 입력 (1-8): ").strip()
    
    try:
        if choice == "1":
            test_health_check()
        elif choice == "2":
            test_quick_analyze()
        elif choice == "3":
            test_single_document()
        elif choice == "4":
            test_multi_documents()
        elif choice == "5":
            test_raw_output()
        elif choice == "6":
            test_custom_input()
        elif choice == "7":
            test_error_handling()
        elif choice == "8":
            print("\n🚀 전체 테스트 시작!\n")
            test_health_check()
            input("\n계속하려면 Enter...")
            test_quick_analyze()
            input("\n계속하려면 Enter...")
            test_single_document()
            input("\n계속하려면 Enter...")
            test_multi_documents()
            input("\n계속하려면 Enter...")
            test_raw_output()
            input("\n계속하려면 Enter...")
            test_error_handling()
        else:
            print("❌ 잘못된 입력입니다.")
    
    except requests.exceptions.ConnectionError:
        print("\n❌ 서버에 연결할 수 없습니다.")
        print("   서버를 먼저 실행하세요: python api_phase1.py")
    
    except Exception as e:
        print(f"\n❌ 에러 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("✨ 테스트 완료!")
    print("📁 출력 파일: ./test_output/")
    print("="*80)


if __name__ == "__main__":
    main()
