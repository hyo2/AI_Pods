"""
프롬프트 생성 노드 (LangGraph)
ImagePlan + PodcastMetadata.visual → 나노바나나용 한글 프롬프트 텍스트
"""

import os
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Vertex AI import
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    VERTEXAI_AVAILABLE = True
except ImportError:
    VERTEXAI_AVAILABLE = False
    print("⚠️  vertexai 패키지가 없습니다.")

# ImagePlan import (상대/직접 실행 둘 다 대응)
try:
    from .image_planning_node import ImagePlan  # 패키지 import
except Exception:
    # 원본
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from image_planning_node import ImagePlan
    except ImportError:
        print("⚠️  image_planning_node import 실패")
        ImagePlan = None

# 변경 
#     try:
#         from image_planning_node import ImagePlan  # 스크립트 직접 실행용
#     except Exception:
#         print("⚠️  image_planning_node import 실패")
#         ImagePlan = None

# from dataclasses import asdict

IMAGE_PROMPT_GENERATION = """
당신은 나노바나나(Gemini 2.5 Flash Image) 프롬프트 전문가입니다.

나노바나나는:
- 한글 프롬프트를 완벽하게 이해합니다
- 대화형/서술형 프롬프트를 선호합니다
- "~해주세요", "~로 만들어주세요" 같은 자연스러운 표현을 이해합니다
- Gemini의 세계 지식을 활용합니다

주어진 이미지 계획을 바탕으로 나노바나나에 최적화된 **한글 프롬프트**를 생성하세요.

## 입력 정보:

**Global Visual Guidelines:**
{visual_guidelines}

**이미지 계획:**
- Title: {title}
- Description: {description}
- Visual Concept: {visual_concept}
- Key Concepts: {key_concepts}

## 프롬프트 생성 가이드라인:

1. **한글 사용**: 영어가 아닌 한글로 작성!
2. **대화형/서술형**: "이런 이미지를 만들어주세요" 스타일
3. **구체적 묘사**: 색상, 구도, 스타일 명확히
4. **Art Style 적용**: Global Guidelines의 스타일 반영
5. **Color Palette 적용**: 지정된 색상 사용
6. **순수 이미지**: 텍스트 오버레이 걱정 없이 이미지 품질에만 집중

## 출력 형식 (JSON):

{{
  "image_title": "간결한 제목",
  "visual_elements": ["요소1", "요소2", "요소3"],
  "composition": "구도 설명",
  "lighting": "조명 설명",
  "image_prompt": "최종 한글 프롬프트 (150-200자)"
}}

**프롬프트 형식 예시:**
"{visual_concept}를 표현한 {art_style} 스타일의 이미지를 만들어주세요.
구도는 {composition}이고, {key_elements}가 포함되어야 합니다.
색상은 {colors}를 사용하고, 조명은 {lighting}으로 해주세요.
전체적으로 {mood} 느낌의 고품질, 전문적인 디자인으로 만들어주세요."

**좋은 예시:**
"텍스트가 음성 파형으로 변환되는 TTS 파이프라인을 플랫 아이소메트릭 일러스트 스타일로 만들어주세요. 
왼쪽에서 오른쪽으로 흐르는 구도로, 문서 아이콘 → Gemini API 배지 → 음성 파형이 연결되어 있습니다.
밝은 파란색(#3498DB)과 초록색(#2ECC71)을 주로 사용하고, 밝고 깨끗한 조명으로 해주세요.
현대적이고 친근한 느낌의 고품질 디자인으로 만들어주세요."

**중요:**
- JSON만 출력
- 한글 프롬프트 생성 (영어 금지!)
- 구체적이고 명확하게
- 16:9 비율 고려
- 대화형/서술형 문체

이제 프롬프트를 생성하세요:
"""

class PromptGenerationNode:
    """
    프롬프트 생성 노드 (이미지 계획 기반)

    기능:
    1. 이미지 계획 → Imagen 4 프롬프트
    2. Global Visual Guidelines 적용
    3. 텍스트 오버레이 공간 제거

    - 입력:
        state["image_plans"]: List[ImagePlan]
        state["metadata"]: PodcastMetadata (metadata.visual 사용)
    - 출력:
        state["image_prompts"]: List[Dict]
          [
            {
              "image_id": str,
              "image_title": str,
              "image_prompt": str,
              "primary_timestamp": str,
              "covered_timestamps": List[str],
              "duration": int,
              ...
            },
            ...
          ]
    """

    def __init__(
        self,
        project_id: str = None,
        location: str = "us-central1",
        model_name: str = "gemini-2.5-flash",
    ):
        # 프로젝트 ID 자동 탐지
        if project_id is None:
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
            if not project_id:
                cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                if cred_path and os.path.exists(cred_path):
                    try:
                        with open(cred_path, "r", encoding="utf-8") as f:
                            creds = json.load(f)
                            project_id = creds.get("project_id")
                    except Exception:
                        pass

            if not project_id:
                print("⚠️  PromptGenerationNode: 프로젝트 ID를 찾을 수 없습니다.")

        self.project_id = project_id
        self.location = location
        self.model_name = model_name

        # Vertex AI 초기화
        if VERTEXAI_AVAILABLE and project_id:
            try:
                vertexai.init(project=project_id, location=location)
                self.model = GenerativeModel(model_name)
                print(f"✅ 프롬프트 생성 노드 초기화: {model_name}")
            except Exception as e:
                print(f"⚠️  PromptGenerationNode 초기화 실패: {str(e)}")
                self.model = None
        else:
            self.model = None
            if not project_id:
                print("⚠️  Gemini 모델 없음 (프로젝트 ID 없음)")

    # ------------------------------------------------------------
    # 내부 유틸: visual_guidelines 추출
    # ------------------------------------------------------------
    def _extract_visual_guidelines(self, metadata: Any) -> Dict[str, Any]:
        """
        PodcastMetadata에서 visual(GlobalVisualGuidelines)만 dict로 변환
        """
        if metadata is None:
            return {}

        # metadata.visual이 있으면 그 부분만 사용
        visual = getattr(metadata, "visual", None)
        if visual is None:
            # 혹시 이미 dict로 들어온 경우 대비
            if isinstance(metadata, dict) and "visual" in metadata:
                visual = metadata["visual"]
            else:
                return {}

        # dataclass → dict
        if hasattr(visual, "__dataclass_fields__"):
            return asdict(visual)
        if isinstance(visual, dict):
            return visual

        return {}

    # ------------------------------------------------------------
    # 핵심: ImagePlan + visual_guidelines → 한글 프롬프트 문자열
    # ------------------------------------------------------------
    def generate_prompt_from_plan(
        self,
        plan: ImagePlan,
        visual_guidelines: Dict[str, Any],
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """이미지 계획으로부터 프롬프트 생성 (재시도 로직 포함)"""
        if not self.model:
            raise RuntimeError("Vertex AI 모델이 초기화되지 않았습니다.")

        # 글로벌 스타일 추출
        art_style = visual_guidelines.get("art_style", "Flat vector illustration")
        art_style_description = visual_guidelines.get('art_style_description', '')
        lighting_style = visual_guidelines.get("lighting_style", "밝고 균일한 조명")
        composition_guidelines = visual_guidelines.get('composition_guidelines', '16:9 비율, 중앙 집중 구도')

        # 프롬프트 생성
        prompt = f"""
    당신은 나노바나나(Gemini 2.5 Flash Image) 프롬프트 전문가입니다.

    **이미지 계획:**
    - 제목: {plan.title}
    - 설명: {plan.description}
    - 시각 개념: {plan.visual_concept}
    - 핵심 개념: {', '.join(plan.key_concepts)}

    **글로벌 비주얼 스타일 (모든 이미지에 통일):**
    - 아트 스타일: **{art_style}**
    - 스타일 설명: {art_style_description}
    - 조명: {lighting_style}
    - 구도 가이드: {composition_guidelines}

    **전체 색상 팔레트:**
    {json.dumps(visual_guidelines.get('color_palette', {}), ensure_ascii=False, indent=2)}

    위 정보를 바탕으로 나노바나나에 최적화된 **한글 프롬프트**를 생성하세요.

    **중요 규칙:**
    1. **반드시 "{art_style}" 스타일**을 프롬프트에 명시하세요
    2. 글로벌 조명/구도 가이드라인 준수
    3. 한글 대화형 프롬프트 ("~해주세요")
    4. 구체적인 시각 요소 포함
    5. 색상은 HEX 코드 또는 색상 이름으로
    6. **JSON 문자열 내부에 줄바꿈 금지**
    7. **🔴 CRITICAL: 이미지 내 모든 텍스트/라벨/다이어그램은 반드시 영어로만 표기** (한글 텍스트는 렌더링 품질 저하)

    출력 형식 (JSON, 한 줄로):
    {{
    "image_title": "제목",
    "style": "{art_style}",
    "visual_elements": ["요소1", "요소2", "요소3", "요소4"],
    "composition": "구도 상세 설명",
    "lighting": "조명 상세 설명",
    "color_usage": "주요 색상",
    "image_prompt": "완전한 한글 프롬프트 (200-300자). 단, 이미지 내 텍스트는 영어로만 표기하도록 명시할 것."
    }}

    **반드시 유효한 JSON만 출력하세요. 줄바꿈 없이.**
    """

        # 재시도 루프
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"   재시도 {attempt + 1}/{max_retries}...")

                # ⭐ 토큰 한계 증가
                response = self.model.generate_content(
                    prompt,
                    generation_config={ 
                        "temperature": 0.6,  # 0.7 → 0.6
                        "max_output_tokens": 4096,  # 2048 → 4096 (2배 증가)
                        "response_mime_type": "application/json"
                    }
                )

                # ⭐ finish_reason 체크
                if not response.candidates:
                    raise RuntimeError("응답에 candidates가 없습니다.")
                
                candidate = response.candidates[0]
                
                if candidate.finish_reason.name == "MAX_TOKENS":
                    print(f"   ⚠️  MAX_TOKENS 도달 (시도 {attempt + 1}/{max_retries}, {plan.image_id})")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        raise RuntimeError("MAX_TOKENS 한계로 인해 생성 실패")

                # JSON 파싱
                response_text = response.text.strip()

                # 마크다운 제거
                if response_text.startswith("```"):
                    response_text = response_text.split("```")[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                    response_text = response_text.strip()
                
                # ⭐ JSON 완전성 체크
                if not response_text.endswith("}"):
                    print(f"   ⚠️  JSON이 불완전합니다 ({plan.image_id})")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        raise json.JSONDecodeError("JSON이 완전하지 않음", response_text, len(response_text))
                
                result = json.loads(response_text)
                
                return {
                    'image_id': plan.image_id,
                    'image_title': result['image_title'],
                    'style': result.get('style', art_style),
                    'image_prompt': result['image_prompt'],
                    'visual_elements': result['visual_elements'],
                    'composition': result['composition'],
                    'lighting': result['lighting'],
                    'color_usage': result.get('color_usage', ''),
                    'primary_timestamp': plan.primary_timestamp,
                    'covered_timestamps': plan.covered_timestamps,
                    'duration': plan.duration
                }

            except json.JSONDecodeError as e:
                print(f"⚠️  JSON 파싱 실패 (시도 {attempt + 1}/{max_retries}, {plan.image_id}): {str(e)}")
                if attempt < max_retries - 1:
                    continue
                else:
                    raise RuntimeError(f"프롬프트 생성 실패 ({plan.image_id}): JSON 파싱 에러 {str(e)}")
            
            except Exception as e:
                print(f"⚠️  생성 실패 (시도 {attempt + 1}/{max_retries}, {plan.image_id}): {str(e)}")
                if attempt < max_retries - 1:
                    continue
                else:
                    raise RuntimeError(f"프롬프트 생성 실패 ({plan.image_id}): {str(e)}")

        raise RuntimeError(f"프롬프트 생성 실패 ({plan.image_id}): 최대 재시도 횟수 초과")

    # ------------------------------------------------------------
    # 여러 ImagePlan → 여러 프롬프트
    # ------------------------------------------------------------
    def generate_prompts_for_plans(
        self,
        plans: List[ImagePlan],
        metadata: Any, # PodcastMetadata
        show_progress: bool = True
    ) -> List[Dict[str, Any]]:
        """
        여러 이미지 계획으로부터 프롬프트 생성
        
        Args:
            plans: 이미지 계획 리스트
            metadata: 메타데이터 (PodcastMetadata 객체)
            show_progress: 진행 상황 표시
        
        Returns:
            프롬프트 리스트
        """
        print("\n" + "=" * 80)
        print("📝 프롬프트 생성 중...")
        print("=" * 80)

        # visual_guidelines = self._extract_visual_guidelines(metadata)

        # PodcastMetadata 객체에서 visual_guidelines 추출
        if hasattr(metadata, 'global_visual_guidelines'):
            visual_guidelines = metadata.global_visual_guidelines
            # dataclass를 dict로 변환
            if hasattr(visual_guidelines, '__dataclass_fields__'):
                from dataclasses import asdict
                visual_guidelines = asdict(visual_guidelines)
        else:
            visual_guidelines = {}
        
        # 원본
        prompts = []

        # 변경 -> prompts: List[Dict[str, Any]] = []

        for i, plan in enumerate(plans):
            if show_progress:
                print(f"\n[{i+1}/{len(plans)}] {plan.image_id} - {plan.title}")

            prompt_data = self.generate_prompt_from_plan(plan, visual_guidelines)
            prompts.append(prompt_data)

        print(f"\n✅ {len(prompts)}개 프롬프트 생성 완료")
        return prompts

    # ------------------------------------------------------------
    # LangGraph entry
    # ------------------------------------------------------------
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph에서 사용하는 호출 인터페이스

        입력 state:
          - image_plans: List[ImagePlan]
          - metadata: PodcastMetadata
        출력 state:
          - image_prompts: List[Dict]
        """
        plans = state.get("image_plans", [])
        metadata = state.get("metadata", []) # 변경 -> ("metadata")

        if not plans:
            print("⚠️  PromptGenerationNode: image_plans 비어 있음")
            return {**state, "image_prompts": []}

        prompts = self.generate_prompts_for_plans(plans, metadata)
        return {**state, "image_prompts": prompts}


# -------------------------------------------------------------------------
# 헬퍼 함수들 (옵션)
# -------------------------------------------------------------------------
def print_prompts_summary(prompts: List[Dict[str, Any]]):
    """프롬프트 요약 출력"""
    print("\n" + "=" * 80)
    print("📋 프롬프트 요약")
    print("=" * 80)

    print(f"\n총 프롬프트: {len(prompts)}개")

    for i, prompt in enumerate(prompts):
        print(f"\n[{i+1}] {prompt['image_id']} - {prompt['image_title']}")
        print(f"    타임스탬프: {prompt['primary_timestamp']}")
        print(f"    커버 범위: {len(prompt['covered_timestamps'])}개 장면")
        print(f"    지속 시간: {prompt['duration']}초")
        print(f"    프롬프트: {prompt['image_prompt'][:100]}...")


def export_prompts(prompts: List[Dict[str, Any]], output_path: str):
    """프롬프트를 JSON으로 저장"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)

    print(f"\n💾 프롬프트 저장: {output_path}")


if __name__ == "__main__":
    print("Prompt Generation Node - 프롬프트 생성 노드 (이미지 계획 기반)")
    print("Import해서 사용하세요: from prompt_generation_node import PromptGenerationNode")
