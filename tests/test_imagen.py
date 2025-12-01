import os
import sys
import time

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.imagen_service import ImagenService

def test_imagen_basic(method="imagen"):
    """기본 Imagen 테스트"""
    
    print("🔧 Imagen 서비스 초기화...")
    
    imagen = ImagenService(
        project_id="alan-document-lab",
        credentials_path="./vertex-ai-service-account.json"
    )
    
    print("✅ 초기화 완료!\n")
    
    topic = "AI 연구의 최신 동향"
    description = "대규모 언어 모델과 Transformer 아키텍처의 발전"
    keywords = ["AI", "연구", "LLM", "Transformer"]
    
    print(f"📌 토픽: {topic}")
    print(f"📝 설명: {description}\n")
    
    print("🎨 이미지 생성 중...\n")
    
    result = imagen.generate_topic_image(
        topic=topic,
        description=description,
        keywords=keywords,
        style="abstract",
        method=method,
        output_dir="./output_images"
    )
    
    print(f"\n✅ 이미지 생성 완료!")
    print(f"📁 저장 위치: {result['image_path']}")
    print(f"📝 Imagen 프롬프트: {result['annotation']['imagen_prompt']}")

def test_various_topics(method="imagen"):
    """다양한 토픽과 설명 길이 테스트"""
    
    imagen = ImagenService(
        project_id="alan-document-lab",
        credentials_path="./vertex-ai-service-account.json"
    )
    
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
                method=method,
                output_dir="./output_images"
            )
            
            print(f"\n✅ 성공!")
            print(f"📁 저장: {result['image_path']}")
            
        except Exception as e:
            print(f"\n❌ 실패: {str(e)}")
        
        print()


def test_all_styles_same_topic(method="imagen"):
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
                topic=f"{topic}_{style}",
                description=description,
                keywords=keywords,
                style=style,
                method=method,
                output_dir="./output_images"
            )
            
            print(f"✅ 성공: {result['image_path']}")
            
        except Exception as e:
            print(f"❌ 실패: {str(e)}")


def test_edge_cases(method="imagen"):
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
                method=method,
                output_dir="./output_images"
            )
            
            print(f"✅ 성공: {result['image_path']}")
            
        except Exception as e:
            print(f"❌ 실패: {str(e)}")


def test_scene_illustrations(method="imagen"):
    """구체적인 장면 일러스트 테스트"""
    
    imagen = ImagenService(
        project_id="alan-document-lab",
        credentials_path="./vertex-ai-service-account.json"
    )
    
    scene_cases = [
        {
            "name": "신데렐라 - 구박받는 장면",
            "topic": "신데렐라 이야기",
            "description": "신데렐라가 계모와 의붓언니들에게 집안일을 강요당하며 구박받는 장면. 낡은 옷을 입은 신데렐라가 바닥을 닦고 있고, 화려한 드레스를 입은 언니들이 비웃으며 서있다. 어두운 부엌 배경.",
            "keywords": ["신데렐라", "동화", "구박", "청소"],
            "style": "scene"
        },
        {
            "name": "AI 연구자 - 브레인스토밍",
            "topic": "AI 연구실의 하루",
            "description": "화이트보드 앞에서 열띤 토론을 하는 AI 연구원들. 복잡한 수식과 신경망 다이어그램이 그려진 화이트보드, 노트북들, 커피잔들이 놓인 책상. 밤늦은 연구실의 분위기.",
            "keywords": ["연구", "토론", "AI", "연구실"],
            "style": "scene"
        },
        {
            "name": "데이터 과학자 - 문제 해결",
            "topic": "버그를 찾는 순간",
            "description": "여러 모니터 앞에 앉은 개발자가 마침내 버그를 발견하고 환호하는 장면. 복잡한 코드가 가득한 화면들, 에너지 드링크 캔들, 어질러진 책상. 새벽의 사무실.",
            "keywords": ["개발자", "디버깅", "성공", "코딩"],
            "style": "scene"
        },
        {
            "name": "로봇과 인간 - 협업",
            "topic": "미래의 협업",
            "description": "현대적인 사무실에서 휴머노이드 로봇과 인간 직원이 함께 회의하는 장면. 홀로그램 프로젝션으로 데이터를 공유하며 대화하고 있다. 밝고 미래적인 분위기.",
            "keywords": ["로봇", "인간", "협업", "미래"],
            "style": "scene"
        },
        {
            "name": "팟캐스트 녹음",
            "topic": "팟캐스트 녹음실",
            "description": "방음 부스 안에서 마이크 앞에 앉아 진지하게 대화하는 두 명의 호스트. 헤드폰을 쓰고 열정적으로 제스처를 취하며 이야기 중. 따뜻한 조명의 스튜디오.",
            "keywords": ["팟캐스트", "녹음", "대화", "스튜디오"],
            "style": "scene"
        }
    ]
    
    print("\n" + "="*60)
    print("장면 일러스트 테스트")
    print("="*60)
    
    for i, test_case in enumerate(scene_cases, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(scene_cases)}] {test_case['name']}")
        print(f"{'='*60}")
        print(f"📌 토픽: {test_case['topic']}")
        print(f"📝 장면:\n{test_case['description']}")
        
        try:
            result = imagen.generate_topic_image(
                topic=test_case["topic"],
                description=test_case["description"],
                keywords=test_case["keywords"],
                style=test_case["style"],
                method=method,
                output_dir="./output_images"
            )
            
            print(f"\n✅ 성공!")
            print(f"📁 저장: {result['image_path']}")
            
        except Exception as e:
            print(f"\n❌ 실패: {str(e)}")


if __name__ == "__main__":
    print("="*60)
    print("Imagen API 종합 테스트")
    print("="*60 + "\n")
    
    os.makedirs("./output_images", exist_ok=True)
    
    # 1단계: 생성 방식 선택
    print("🎨 이미지 생성 방식 선택:")
    print("1. Imagen (Google Imagen 3.0)")
    print("2. Gemini (나노바나나 🍌)")
    print("3. 둘 다 비교")
    
    method_choice = input("\n번호 입력 (1-3): ").strip()
    
    if method_choice == "1":
        selected_method = "imagen"
        print("\n✅ Imagen 방식 선택됨\n")
    elif method_choice == "2":
        selected_method = "gemini"
        print("\n✅ Gemini 나노바나나 🍌 방식 선택됨\n")
    elif method_choice == "3":
        selected_method = "both"
        print("\n✅ 둘 다 비교 모드\n")
    else:
        print("❌ 잘못된 입력")
        exit()
    
    # 2단계: 테스트 선택
    print("테스트 선택:")
    print("1. 기본 테스트 (1개)")
    print("2. 다양한 토픽 테스트 (6개)")
    print("3. 같은 토픽, 다양한 스타일 (4개)")
    print("4. 엣지 케이스 테스트 (3개)")
    print("5. 전체 테스트 (14개)")
    print("6. 장면 일러스트 테스트 (5개)")
    
    test_choice = input("\n번호 입력 (1-6): ").strip()
    
    # 테스트 실행
    def run_test(test_func, method):
        """선택된 방식으로 테스트 실행"""
        if method == "both":
            # Imagen으로 실행
            print("\n" + "="*60)
            print("🎨 Imagen 방식으로 실행")
            print("="*60)
            test_func(method="imagen")
            
            time.sleep(3)
            
            # Gemini로 실행
            print("\n" + "="*60)
            print("🍌 Gemini 나노바나나 방식으로 실행")
            print("="*60)
            test_func(method="gemini")
        else:
            test_func(method=method)
    
    # 선택에 따라 실행
    if test_choice == "1":
        run_test(test_imagen_basic, selected_method)
    elif test_choice == "2":
        run_test(test_various_topics, selected_method)
    elif test_choice == "3":
        run_test(test_all_styles_same_topic, selected_method)
    elif test_choice == "4":
        run_test(test_edge_cases, selected_method)
    elif test_choice == "5":
        print("\n🚀 전체 테스트 시작!\n")
        run_test(test_imagen_basic, selected_method)
        run_test(test_various_topics, selected_method)
        run_test(test_all_styles_same_topic, selected_method)
        run_test(test_edge_cases, selected_method)
    elif test_choice == "6":
        run_test(test_scene_illustrations, selected_method)
    else:
        print("❌ 잘못된 입력입니다.")
    
    print("\n" + "="*60)
    print("테스트 완료!")
    print(f"📁 생성된 이미지: ./output_images/")
    print("="*60)