import os
import sys
import time

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.imagen_service import ImagenService

def test_imagen_basic():
    """기본 Imagen 테스트"""
    
    print("🔧 Imagen 서비스 초기화...")
    
    # ⚠️ 경로 수정 필요!
    imagen = ImagenService(
        project_id="alan-document-lab",
        credentials_path="./vertex-ai-service-account.json"  # 실제 경로로 수정
    )
    
    print("✅ 초기화 완료!\n")
    
    # 테스트 토픽
    topic = "AI 연구의 최신 동향"
    description = "대규모 언어 모델과 Transformer 아키텍처의 발전"
    keywords = ["AI", "연구", "LLM", "Transformer"]
    
    print(f"📌 토픽: {topic}")
    print(f"📝 설명: {description}\n")
    
    # 이미지 생성
    print("🎨 이미지 생성 중...\n")
    
    result = imagen.generate_topic_image(
        topic=topic,
        description=description,
        keywords=keywords,
        style="abstract",  # abstract, technical, illustration, photo
        output_dir="./output_images"  # 출력 폴더
    )
    
    print(f"\n✅ 이미지 생성 완료!")
    print(f"📁 저장 위치: {result['image_path']}")
    print(f"📝 Imagen 프롬프트: {result['annotation']['imagen_prompt']}")

def test_multiple_styles():
    """여러 스타일 테스트"""
    
    imagen = ImagenService(
        project_id="neat-shell-478809-u2",
        credentials_path="./vertex-ai-service-account.json"
    )
    
    styles = ["abstract", "technical", "illustration"]
    
    for style in styles:
        print(f"\n{'='*60}")
        print(f"🎨 스타일: {style}")
        print(f"{'='*60}\n")
        
        result = imagen.generate_topic_image(
            topic="AI 연구",
            description="인공지능 연구의 발전",
            keywords=["AI", "연구"],
            style=style,
            output_dir="./output_images"
        )
        
        print(f"✅ 저장: {result['image_path']}")

def test_various_topics():
    """다양한 토픽과 설명 길이 테스트"""
    
    imagen = ImagenService(
        project_id="alan-document-lab",
        credentials_path="./vertex-ai-service-account.json"
    )
    
    # 테스트 케이스들
    test_cases = [
        {
            "name": "간단한 주제",
            "topic": "AI 기초",
            "description": "인공지능의 기본 개념",
            "keywords": ["AI", "기초"],
            "style": "abstract"
        },
        {
            "name": "긴 설명 - 기술적",
            "topic": "Transformer 아키텍처의 내부 동작 원리",
            "description": "Transformer는 self-attention 메커니즘을 활용하여 입력 시퀀스의 모든 위치 간 관계를 병렬적으로 계산합니다. 인코더와 디코더로 구성되며, 각각 multi-head attention과 feed-forward 네트워크를 포함합니다. Positional encoding을 통해 순서 정보를 보존하고, layer normalization과 residual connection으로 학습 안정성을 확보합니다.",
            "keywords": ["Transformer", "attention", "neural network", "deep learning"],
            "style": "technical"
        },
        {
            "name": "복잡한 개념 - 추상적",
            "topic": "양자 컴퓨팅과 머신러닝의 융합",
            "description": "양자 컴퓨팅의 중첩과 얽힘 현상을 활용한 새로운 패러다임의 머신러닝 알고리즘. 큐비트의 상태 공간에서 고전 컴퓨터로는 불가능한 복잡도의 최적화 문제를 해결하며, 양자 회로를 통한 특징 추출과 분류가 가능합니다. Variational Quantum Eigensolver와 Quantum Approximate Optimization Algorithm이 대표적입니다.",
            "keywords": ["양자컴퓨팅", "머신러닝", "큐비트", "QAOA", "VQE"],
            "style": "abstract"
        },
        {
            "name": "실용적 주제 - 일러스트",
            "topic": "스마트 홈 IoT 생태계",
            "description": "가정 내 다양한 스마트 기기들이 상호 연결되어 자동화된 생활 환경을 구축하는 시스템",
            "keywords": ["IoT", "스마트홈", "자동화"],
            "style": "illustration"
        },
        {
            "name": "매우 긴 설명 - 논문 수준",
            "topic": "대규모 언어 모델의 창발적 능력",
            "description": "대규모 언어 모델(Large Language Models, LLMs)은 수십억에서 수조 개의 파라미터로 구성된 신경망으로, 방대한 텍스트 데이터로 학습됩니다. 모델의 규모가 특정 임계점을 넘어서면 few-shot learning, chain-of-thought reasoning, 복잡한 추론 능력 등 학습 단계에서 명시적으로 학습되지 않은 창발적 능력(emergent abilities)이 나타납니다. 이는 단순한 패턴 인식을 넘어 추상적 사고, 논리적 추론, 복잡한 문제 해결 능력을 포함하며, 모델 크기, 데이터 품질, 학습 방법론이 핵심 요소로 작용합니다. GPT-4, Claude, PaLM 등이 대표적이며, instruction tuning과 RLHF를 통해 인간의 의도에 더욱 부합하도록 조정됩니다.",
            "keywords": ["LLM", "창발성", "few-shot", "reasoning", "GPT", "Claude"],
            "style": "technical"
        },
        {
            "name": "비유적 표현",
            "topic": "데이터 파이프라인의 흐름",
            "description": "원시 데이터가 정제, 변환, 통합의 과정을 거쳐 최종 분석 가능한 형태로 흐르는 과정. 마치 강물이 여러 지류를 거쳐 바다로 흘러가듯, 데이터도 여러 처리 단계를 거쳐 최종 목적지에 도달합니다.",
            "keywords": ["데이터", "파이프라인", "ETL", "흐름"],
            "style": "abstract"
        }
    ]
    
    print("\n" + "="*60)
    print("다양한 토픽 테스트")
    print("="*60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(test_cases)}] {test_case['name']}")
        print(f"{'='*60}")
        print(f"📌 토픽: {test_case['topic']}")
        print(f"📝 설명 길이: {len(test_case['description'])}자")
        print(f"🎨 스타일: {test_case['style']}")
        print(f"\n설명:\n{test_case['description'][:100]}...")
        
        try:
            result = imagen.generate_topic_image(
                topic=test_case["topic"],
                description=test_case["description"],
                keywords=test_case["keywords"],
                style=test_case["style"],
                output_dir="./output_images"
            )
            
            print(f"\n✅ 성공!")
            print(f"📁 저장: {result['image_path']}")

            time.sleep(3)  # 3초 대기 ⭐
            
        except Exception as e:
            print(f"\n❌ 실패: {str(e)}")
        
        print()


def test_all_styles_same_topic():
    """같은 토픽으로 모든 스타일 테스트"""
    
    imagen = ImagenService(
        project_id="alan-document-lab",
        credentials_path="./vertex-ai-service-account.json"
    )
    
    topic = "인공지능의 미래"
    description = "인공지능 기술이 사회 전반에 미치는 영향과 앞으로의 발전 방향. 자동화, 의료, 교육, 엔터테인먼트 등 다양한 분야에서의 혁신적 변화."
    keywords = ["AI", "미래", "기술", "혁신"]
    
    styles = ["abstract", "technical", "illustration", "photo"]
    
    print("\n" + "="*60)
    print("같은 토픽, 다양한 스타일 비교")
    print("="*60)
    print(f"📌 토픽: {topic}")
    print(f"📝 설명: {description}\n")
    
    for style in styles:
        print(f"\n{'='*60}")
        print(f"🎨 스타일: {style}")
        print(f"{'='*60}")
        
        try:
            result = imagen.generate_topic_image(
                topic=f"{topic}_{style}",  # 파일명 구분
                description=description,
                keywords=keywords,
                style=style,
                output_dir="./output_images"
            )
            
            print(f"✅ 성공: {result['image_path']}")
            
        except Exception as e:
            print(f"❌ 실패: {str(e)}")

        time.sleep(3)  # 3초 대기 ⭐


def test_edge_cases():
    """엣지 케이스 테스트"""
    
    imagen = ImagenService(
        project_id="alan-document-lab",
        credentials_path="./vertex-ai-service-account.json"
    )
    
    edge_cases = [
        {
            "name": "매우 짧은 설명",
            "topic": "AI",
            "description": "인공지능",
            "keywords": ["AI"],
            "style": "abstract"
        },
        {
            "name": "한글 + 영어 혼합",
            "topic": "Multi-modal AI 시스템",
            "description": "Vision, Language, Audio를 통합한 멀티모달 인공지능 시스템의 구조와 학습 방법론",
            "keywords": ["multimodal", "vision", "language", "audio"],
            "style": "technical"
        },
        {
            "name": "특수문자 포함",
            "topic": "AI/ML 파이프라인",
            "description": "데이터 수집 → 전처리 → 학습 → 배포의 end-to-end 워크플로우",
            "keywords": ["pipeline", "MLOps", "workflow"],
            "style": "technical"
        }
    ]
    
    print("\n" + "="*60)
    print("엣지 케이스 테스트")
    print("="*60)
    
    for test_case in edge_cases:
        print(f"\n🔍 {test_case['name']}")
        
        try:
            result = imagen.generate_topic_image(
                topic=test_case["topic"],
                description=test_case["description"],
                keywords=test_case["keywords"],
                style=test_case["style"],
                output_dir="./output_images"
            )
            
            print(f"✅ 성공: {result['image_path']}")
            
        except Exception as e:
            print(f"❌ 실패: {str(e)}")

        time.sleep(3)  # 3초 대기 ⭐

if __name__ == "__main__":
    print("="*60)
    print("Imagen API 종합 테스트")
    print("="*60 + "\n")
    
    # 출력 폴더 생성
    os.makedirs("./output_images", exist_ok=True)
    
    # 선택: 어떤 테스트를 실행할까요?
    print("테스트 선택:")
    print("1. 기본 테스트 (1개)")
    print("2. 다양한 토픽 테스트 (6개)")
    print("3. 같은 토픽, 다양한 스타일 (4개)")
    print("4. 엣지 케이스 테스트 (3개)")
    print("5. 전체 테스트 (14개)")
    
    choice = input("\n번호 입력 (1-5): ").strip()
    
    if choice == "1":
        test_imagen_basic()
    elif choice == "2":
        test_various_topics()
    elif choice == "3":
        test_all_styles_same_topic()
    elif choice == "4":
        test_edge_cases()
    elif choice == "5":
        print("\n🚀 전체 테스트 시작!\n")
        test_imagen_basic()
        test_various_topics()
        test_all_styles_same_topic()
        test_edge_cases()
    else:
        print("❌ 잘못된 입력입니다.")
    
    print("\n" + "="*60)
    print("테스트 완료!")
    print(f"📁 생성된 이미지: ./output_images/")
    print("="*60)
