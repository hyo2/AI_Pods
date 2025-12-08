"""
이미지 계획 노드 (LangGraph)
전체 스크립트를 분석하여 n개의 이미지 계획 생성
"""

import json
import os
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


@dataclass
class ImagePlan:
    """이미지 계획"""
    image_id: str
    title: str
    description: str
    key_concepts: List[str]
    covered_timestamps: List[str]  # 여러 타임스탬프!
    primary_timestamp: str  # 대표 시점
    duration: int  # 이미지 표시 시간 (초)
    visual_concept: str  # 시각적 개념


IMAGE_PLANNING_PROMPT = """
당신은 교육 콘텐츠 비디오 제작 전문가입니다.

주어진 팟캐스트 스크립트 전체를 분석하여, 핵심 개념을 효과적으로 설명하는 이미지들을 계획하세요.

## 입력 정보:

**전체 스크립트:**
{full_script}

**메타데이터:**
{metadata}

**팟캐스트 길이:** {duration_minutes}분

## 이미지 개수 가이드라인:

팟캐스트 길이에 따라 적절한 개수를 선택하세요:
- 3분 이하: 3-4개
- 3-5분: 5-6개
- 5-8분: 7-9개
- 8-12분: 10-13개
- 12-20분: 14-18개
- 20분 이상: 18-25개

**중요:** 무조건 많이 만들지 말고, 진짜 필요한 핵심만!

## 이미지 계획 가이드라인:

1. **맥락 중심**: 각 이미지는 여러 타임스탬프의 내용을 종합하여 하나의 완전한 개념을 설명
2. **핵심 개념 우선**: key_concepts (높은 priority)를 반드시 시각화
3. **적절한 지속 시간**: 각 이미지는 15-30초 정도 표시 (설명에 충분한 시간)
4. **시각화 가능성**: 추상적이지 않고 구체적으로 그릴 수 있는 개념

## 이미지 선정 기준:

**반드시 포함:**
- 핵심 개념 설명 (TTS, Gemini API 등)
- 프로세스/플로우 (단계별 진행)
- 아키텍처/구조

**피해야 할 것:**
- 단순 질문/대답 장면
- 추상적인 개념만
- 텍스트만으로 설명 가능한 것

## 출력 형식 (JSON):

{{
  "image_plans": [
    {{
      "image_id": "img_001",
      "title": "이미지 제목 (간결하게)",
      "description": "이 이미지가 설명하는 내용 (2-3문장)",
      "key_concepts": ["개념1", "개념2"],
      "covered_timestamps": ["00:01:48", "00:01:52", "00:01:58"],
      "primary_timestamp": "00:01:48",
      "duration": 20,
      "visual_concept": "구체적인 시각적 표현 (예: 텍스트 입력 → API 처리 → 음성 출력 플로우)"
    }}
  ],
  "total_images": 6,
  "reasoning": "이미지 계획 전략 (1-2문장)"
}}

**중요:** 
- JSON만 출력하세요 (다른 텍스트 포함 금지)
- covered_timestamps는 실제 스크립트에 있는 타임스탬프만 사용
- primary_timestamp는 covered_timestamps 중 가장 대표적인 시점
- duration은 다음 이미지까지의 시간 (초)

이제 이미지 계획을 JSON으로 생성하세요:
"""


class ImagePlanningNode:
    """
    이미지 계획 노드
    
    기능:
    1. 전체 스크립트 분석
    2. 메타데이터 기반 이미지 계획 생성
    3. 타임스탬프 매핑
    """
    
    def __init__(
        self,
        project_id: str = None,
        location: str = "us-central1",
        model_name: str = "gemini-2.5-flash"
    ):
        """
        이미지 계획 노드 초기화
        
        Args:
            project_id: Google Cloud 프로젝트 ID (자동 탐지)
            location: Vertex AI 리전
            model_name: Gemini 모델
        """
        # 프로젝트 ID 자동 탐지
        if project_id is None:
            # 1. 환경변수
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
            
            # 2. Service Account JSON
            if not project_id:
                credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                if credentials_path and os.path.exists(credentials_path):
                    try:
                        import json
                        with open(credentials_path, 'r') as f:
                            creds = json.load(f)
                            project_id = creds.get('project_id')
                    except Exception:
                        pass
            
            if not project_id:
                print("⚠️  프로젝트 ID를 찾을 수 없습니다.")
        
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        
        # Vertex AI 초기화
        if VERTEXAI_AVAILABLE and project_id:
            try:
                vertexai.init(project=project_id, location=location)
                self.model = GenerativeModel(model_name)
                print(f"✅ 이미지 계획 노드 초기화: {model_name}")
            except Exception as e:
                print(f"⚠️  초기화 실패: {str(e)}")
                self.model = None
        else:
            self.model = None
            if not project_id:
                print("⚠️  Gemini 모델 없음 (프로젝트 ID 없음)")
    
    def create_image_plans(
        self,
        full_script: str,
        metadata: Any,  # PodcastMetadata 객체
        target_image_count: int = None,
        max_retries: int = 3
    ) -> List[ImagePlan]:
        """
        전체 스크립트로부터 이미지 계획 생성 (재시도 로직 포함)
        
        Args:
            full_script: 전체 팟캐스트 스크립트
            metadata: 메타데이터 (PodcastMetadata 객체)
            target_image_count: 목표 이미지 개수 (None이면 자동)
            max_retries: 최대 재시도 횟수
        
        Returns:
            이미지 계획 리스트
        """
        if not self.model:
            raise RuntimeError("Vertex AI 모델이 초기화되지 않았습니다. GOOGLE_CLOUD_PROJECT 및 인증 정보를 확인하세요.")
        
        print("\n" + "="*80)
        print("🎬 이미지 계획 생성 중...")
        print("="*80)
        
        # 팟캐스트 길이 계산 (마지막 타임스탬프에서)
        duration_minutes = self._calculate_duration(full_script)
        print(f"   팟캐스트 길이: {duration_minutes}분")
        
        # metadata를 dict로 변환 (JSON 전달용)
        if hasattr(metadata, '__dataclass_fields__'):
            from dataclasses import asdict
            metadata_dict = asdict(metadata)
        else:
            metadata_dict = metadata
        
        # 프롬프트 생성
        prompt = IMAGE_PLANNING_PROMPT.format(
            full_script=full_script,
            metadata=json.dumps(metadata_dict, ensure_ascii=False, indent=2),
            duration_minutes=duration_minutes
        )
        
        # 재시도 루프
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"   재시도 {attempt + 1}/{max_retries}...")
                
                # Gemini 호출
                response = self.model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.3,
                        "max_output_tokens": 8192,
                        "response_mime_type": "application/json"  # JSON 응답 강제
                    }
                )
                
                # JSON 파싱
                response_text = response.text.strip()
                
                # 마크다운 코드 블록 제거
                if response_text.startswith("```"):
                    response_text = response_text.split("```")[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                    response_text = response_text.strip()
                
                result = json.loads(response_text)
                
                # ImagePlan 객체로 변환
                plans = []
                for plan_data in result.get("image_plans", []):
                    plan = ImagePlan(
                        image_id=plan_data["image_id"],
                        title=plan_data["title"],
                        description=plan_data["description"],
                        key_concepts=plan_data["key_concepts"],
                        covered_timestamps=plan_data["covered_timestamps"],
                        primary_timestamp=plan_data["primary_timestamp"],
                        duration=plan_data.get("duration", 20),
                        visual_concept=plan_data["visual_concept"]
                    )
                    plans.append(plan)
                
                print(f"\n✅ {len(plans)}개 이미지 계획 생성 완료")
                print(f"   전략: {result.get('reasoning', 'N/A')}")
                
                return plans
            
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON 파싱 실패 (시도 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    print(f"   응답 일부: {response_text[:200]}...")
                    continue
                else:
                    print(f"❌ 이미지 계획 생성 최종 실패")
                    raise RuntimeError(f"이미지 계획 생성 실패: JSON 파싱 에러 ({str(e)})")
            
            except KeyError as e:
                print(f"⚠️  필수 필드 누락 (시도 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    continue
                else:
                    print(f"❌ 이미지 계획 생성 최종 실패")
                    raise RuntimeError(f"이미지 계획 생성 실패: 필수 필드 누락 ({str(e)})")
            
            except Exception as e:
                print(f"⚠️  생성 실패 (시도 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    import traceback
                    traceback.print_exc()
                    continue
                else:
                    print(f"❌ 이미지 계획 생성 최종 실패")
                    raise RuntimeError(f"이미지 계획 생성 실패: {str(e)}")
        
        # 여기 도달하면 실패
        raise RuntimeError("이미지 계획 생성 실패: 최대 재시도 횟수 초과")
    
    def _calculate_duration(self, full_script: str) -> int:
        """
        스크립트에서 팟캐스트 길이 계산 (분)
        
        Args:
            full_script: 전체 스크립트
        
        Returns:
            길이 (분)
        """
        import re
        
        # 모든 타임스탬프 추출
        timestamps = re.findall(r'\[(\d{2}:\d{2}:\d{2})\]', full_script)
        
        if not timestamps:
            return 6  # 기본값
        
        # 마지막 타임스탬프 파싱
        last_timestamp = timestamps[-1]
        parts = last_timestamp.split(':')
        
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        
        total_minutes = hours * 60 + minutes + (1 if seconds > 0 else 0)
        
        return max(total_minutes, 1)  # 최소 1분
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph 노드로 실행
        
        Args:
            state: {
                "full_script": str,
                "metadata": PodcastMetadata,
                ...
            }
        
        Returns:
            state with image_plans added
        """
        full_script = state.get("full_script", "")
        metadata = state.get("metadata", {})
        
        plans = self.create_image_plans(full_script, metadata)
        
        return {
            **state,
            "image_plans": plans
        }


# ============================================================================
# 헬퍼 함수들
# ============================================================================

def print_image_plans_summary(plans: List[ImagePlan]):
    """이미지 계획 요약 출력"""
    print("\n" + "="*80)
    print("📋 이미지 계획 요약")
    print("="*80)
    
    print(f"\n총 이미지: {len(plans)}개")
    
    for i, plan in enumerate(plans):
        print(f"\n[{i+1}] {plan.image_id} - {plan.title}")
        print(f"    타임스탬프: {plan.primary_timestamp} (± {len(plan.covered_timestamps)}개 장면)")
        print(f"    지속 시간: {plan.duration}초")
        print(f"    핵심 개념: {', '.join(plan.key_concepts)}")
        print(f"    시각 개념: {plan.visual_concept[:80]}...")


def export_image_plans(plans: List[ImagePlan], output_path: str):
    """이미지 계획을 JSON으로 저장"""
    plans_data = [asdict(plan) for plan in plans]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(plans_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 이미지 계획 저장: {output_path}")


if __name__ == "__main__":
    print("Image Planning Node - 이미지 계획 노드")
    print("Import해서 사용하세요: from image_planning_node import ImagePlanningNode")