"""
이미지 생성 노드 (LangGraph)
Gemini 2.5 Flash Image (나노바나나) 🍌
"""

import os
import time
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from PIL import Image
from io import BytesIO

# Vertex AI
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    VERTEXAI_AVAILABLE = True
except ImportError:
    VERTEXAI_AVAILABLE = False
    print("⚠️  vertexai 패키지 없음 (pip install google-cloud-aiplatform)")


class ImageGenerationNode:
    """
    이미지 생성 노드

    기능:
    1. 프롬프트로부터 이미지 생성
    2. Gemini 2.5 Flash Image (나노바나나) 사용
    3. 429 에러 재시도

    입력:
      state["image_prompts"]: List[Dict]
        각 항목:
          {
            "image_id": str,
            "image_prompt": str,
            ...
          }

    출력:
      state["image_paths"]: Dict[str, str]
        { image_id: "로컬 파일 경로" }
    """

    def __init__(
        self,
        project_id: str = None,
        location: str = "us-central1",
        output_dir: str = "outputs/images",
    ):
        # 프로젝트 ID 자동 탐지
        if project_id is None:
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")

            # 2. Service Account JSON
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
                print("⚠️  ImageGenerationNode: 프로젝트 ID를 찾을 수 없습니다.")

        self.project_id = project_id
        self.location = location
        self.output_dir = output_dir

        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)

        # Vertex AI 초기화
        if VERTEXAI_AVAILABLE and project_id:
            try:
                vertexai.init(project=project_id, location=location)
                self.model = GenerativeModel("gemini-2.5-flash-image")
                print(f"✅ 이미지 생성 노드 초기화: gemini-2.5-flash-image 🍌")
            except Exception as e:
                print(f"⚠️  ImageGenerationNode 초기화 실패: {str(e)}")
                self.model = None
        else:
            self.model = None
            if not project_id:
                print("⚠️  이미지 생성 불가 (프로젝트 ID 없음)")

    # ------------------------------------------------------------
    # 단일 이미지 생성
    # ------------------------------------------------------------
    def generate_image(
        self,
        prompt: str,
        image_id: str,
        max_retries: int = 3,
        retry_delay: int = 5,
    ) -> Optional[str]:
        """
        단일 이미지 생성
        
        Args:
            prompt: 이미지 프롬프트 (한글 OK)
            image_id: 이미지 ID
            max_retries: 최대 재시도 횟수
            retry_delay: 재시도 대기 시간 (초)
        
        Returns:
            이미지 파일 경로 (실패 시 None)
        """
        if not self.model:
            print(f"⚠️  {image_id}: 모델 없음, 스킵")
            return None

        # ⭐ 프롬프트에 16:9 비율 명시 추가
        enhanced_prompt = f"{prompt}\n\n16:9 aspect ratio, widescreen format."

        for attempt in range(max_retries):
            try:
                print(f"\n🎨 {image_id} 생성 중... (시도 {attempt + 1}/{max_retries})")
                print(f"   프롬프트: {prompt[:100]}...")

                # ⭐ Gemini 2.5 Flash Image - 최소 설정만 사용
                response = self.model.generate_content(
                    enhanced_prompt,
                    generation_config={
                        "response_modalities": ["IMAGE"],
                        # aspect_ratio 제거! 프롬프트에 명시함
                    },
                )

                # 이미지 추출
                if not response.candidates:
                    print(f"⚠️  {image_id}: 응답에 candidates가 없음")
                    return None

                for part in response.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        # 이미지 데이터를 PIL Image로 변환
                        image_bytes = part.inline_data.data
                        image = Image.open(BytesIO(image_bytes))

                        # 저장
                        image_path = os.path.join(self.output_dir, f"{image_id}.png")
                        image.save(image_path, "PNG")

                        print(f"✅ {image_id}: 저장 완료 ({image_path})")
                        return image_path

                print(f"⚠️  {image_id}: 응답에 이미지 없음")
                return None

            except Exception as e:
                error = str(e)

                # 429 에러 (할당량 초과) / quota / resource 관련 재시도
                if (
                    "429" in error
                    or "quota" in error.lower()
                    or "resource" in error.lower()
                ):
                    if attempt < max_retries - 1:
                        wait = retry_delay * (attempt + 1)
                        print(f"⚠️  {image_id}: 할당량 초과, {wait}초 후 재시도...")
                        time.sleep(wait)
                        continue
                    else:
                        print(f"❌ {image_id}: 할당량 초과, 재시도 실패")
                        return None

                # Unknown field 에러
                if "Unknown field" in error:
                    print(f"❌ {image_id}: API 설정 오류 - {error}")
                    print(f"   💡 프롬프트에 비율을 명시했으므로 이 오류는 발생하지 않아야 합니다.")
                    return None

                print(f"❌ {image_id}: 생성 실패 - {error}")
                
                # 재시도 가능한 에러면 계속
                if attempt < max_retries - 1:
                    print(f"   {retry_delay}초 후 재시도...")
                    time.sleep(retry_delay)
                    continue
                
                return None

        return None

    # ------------------------------------------------------------
    # 여러 프롬프트 → 여러 이미지
    # ------------------------------------------------------------
    def generate_images_from_prompts(
        self,
        prompts: List[Dict[str, Any]],
        show_progress: bool = True,
    ) -> Dict[str, str]:
        """
        여러 프롬프트로부터 이미지 생성
        
        Args:
            prompts: 프롬프트 리스트
            show_progress: 진행 상황 표시
        
        Returns:
            {image_id: 이미지 경로} 매핑
        """
        print("\n" + "=" * 80)
        print("🖼️  이미지 생성 시작")
        print("=" * 80)

        image_paths: Dict[str, str] = {}

        for i, prompt_data in enumerate(prompts):
            if show_progress:
                print(f"\n[{i+1}/{len(prompts)}] {prompt_data.get('image_id', 'unknown')}")

            # 필드 추출
            image_id = prompt_data.get("image_id")
            prompt = prompt_data.get("image_prompt")

            if not image_id or not prompt:
                print(f"⚠️  프롬프트 데이터 불완전:")
                print(f"     image_id: {image_id}")
                print(f"     image_prompt: {prompt}")
                continue

            # 이미지 생성
            image_path = self.generate_image(prompt, image_id)

            if image_path:
                image_paths[image_id] = image_path

        print("\n" + "=" * 80)
        print(f"✅ {len(image_paths)}/{len(prompts)}개 이미지 생성 완료")
        print("=" * 80)

        return image_paths

    # ------------------------------------------------------------
    # LangGraph entry
    # ------------------------------------------------------------
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph 노드로 실행
        
        Args:
            state: {
                "image_prompts": List[Dict],
                ...
            }
        
        Returns:
            state with image_paths added
        """
        prompts = state.get("image_prompts", [])
        
        # 디버깅: prompts 구조 확인
        if prompts:
            print(f"\n🔍 첫 번째 프롬프트 데이터 확인:")
            print(f"   키: {list(prompts[0].keys())}")
            print(f"   image_id: {prompts[0].get('image_id')}")
            print(f"   image_prompt 존재: {'image_prompt' in prompts[0]}")
        
        image_paths = self.generate_images_from_prompts(prompts)
        
        # ⭐ state 업데이트 시 기존 image_prompts 정보도 유지
        return {
            **state, 
            "image_paths": image_paths,
            # image_prompts는 그대로 유지 (다른 노드에서 필요할 수 있음)
        }


# ------------------------------------------------------------
# 헬퍼 함수들
# ------------------------------------------------------------
def load_prompts(prompts_path: str) -> List[Dict[str, Any]]:
    """프롬프트 JSON 로드"""
    with open(prompts_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_image_manifest(image_paths: Dict[str, str], output_path: str):
    """이미지 매니페스트 저장"""
    manifest = {
        "total_images": len(image_paths),
        "images": [
            {
                "image_id": image_id,
                "path": path,
                "filename": os.path.basename(path),
            }
            for image_id, path in image_paths.items()
        ]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n💾 이미지 매니페스트 저장: {output_path}")


def print_generation_summary(image_paths: Dict[str, str]):
    """생성 결과 요약"""
    print("\n" + "=" * 80)
    print("📊 생성 결과 요약")
    print("=" * 80)

    print(f"\n총 {len(image_paths)}개 이미지:")

    for image_id, path in sorted(image_paths.items()):
        file_size = os.path.getsize(path) / 1024  # KB
        print(f"  - {image_id}: {os.path.basename(path)} ({file_size:.1f} KB)")


if __name__ == "__main__":
    print("Image Generation Node - 이미지 생성 노드 (나노바나나 🍌)")
    print("Import해서 사용하세요: from image_generation_node import ImageGenerationNode")