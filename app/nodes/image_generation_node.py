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
    """
    
    def __init__(
        self,
        project_id: str = None,
        location: str = "us-central1",
        output_dir: str = "outputs/images"
    ):
        """
        이미지 생성 노드 초기화
        
        Args:
            project_id: Google Cloud 프로젝트 ID (자동 탐지)
            location: Vertex AI 리전
            output_dir: 이미지 저장 디렉토리
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
                        with open(credentials_path, 'r') as f:
                            creds = json.load(f)
                            project_id = creds.get('project_id')
                    except Exception:
                        pass
            
            if not project_id:
                print("⚠️  프로젝트 ID를 찾을 수 없습니다.")
        
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
                print(f"⚠️  초기화 실패: {str(e)}")
                self.model = None
        else:
            self.model = None
            if not project_id:
                print("⚠️  이미지 생성 불가 (프로젝트 ID 없음)")
    
    def generate_image(
        self,
        prompt: str,
        image_id: str,
        max_retries: int = 3,
        retry_delay: int = 5
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
        
        for attempt in range(max_retries):
            try:
                print(f"\n🎨 {image_id} 생성 중... (시도 {attempt + 1}/{max_retries})")
                
                # 이미지 생성
                response = self.model.generate_content(
                    prompt,
                    generation_config={
                        "response_modalities": ["IMAGE"],
                        "image_config": {
                            "aspect_ratio": "16:9"
                        }
                    }
                )
                
                # 이미지 추출
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        # 이미지 데이터를 PIL Image로 변환
                        image_data = part.inline_data.data
                        image = Image.open(BytesIO(image_data))
                        
                        # 저장
                        image_path = os.path.join(self.output_dir, f"{image_id}.png")
                        image.save(image_path, "PNG")
                        
                        print(f"✅ {image_id}: 저장 완료 ({image_path})")
                        return image_path
                
                print(f"⚠️  {image_id}: 응답에 이미지 없음")
                return None
            
            except Exception as e:
                error_msg = str(e)
                
                # 429 에러 (할당량 초과)
                if "429" in error_msg or "quota" in error_msg.lower() or "resource" in error_msg.lower():
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)
                        print(f"⚠️  {image_id}: 할당량 초과, {wait_time}초 대기 후 재시도...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ {image_id}: 할당량 초과, 재시도 실패")
                        return None
                
                # 기타 에러
                print(f"❌ {image_id}: 생성 실패 - {error_msg}")
                return None
        
        return None
    
    def generate_images_from_prompts(
        self,
        prompts: List[Dict[str, Any]],
        show_progress: bool = True
    ) -> Dict[str, str]:
        """
        여러 프롬프트로부터 이미지 생성
        
        Args:
            prompts: 프롬프트 리스트
            show_progress: 진행 상황 표시
        
        Returns:
            {image_id: 이미지 경로} 매핑
        """
        print("\n" + "="*80)
        print("🖼️  이미지 생성 시작")
        print("="*80)
        
        image_paths = {}
        
        for i, prompt_data in enumerate(prompts):
            if show_progress:
                print(f"\n[{i+1}/{len(prompts)}] {prompt_data.get('image_id', 'unknown')}")
            
            image_id = prompt_data.get('image_id')
            prompt = prompt_data.get('image_prompt')
            
            if not image_id or not prompt:
                print(f"⚠️  프롬프트 데이터 불완전, 스킵")
                continue
            
            # 이미지 생성
            image_path = self.generate_image(prompt, image_id)
            
            if image_path:
                image_paths[image_id] = image_path
        
        print(f"\n" + "="*80)
        print(f"✅ {len(image_paths)}/{len(prompts)}개 이미지 생성 완료")
        print("="*80)
        
        return image_paths
    
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
        
        image_paths = self.generate_images_from_prompts(prompts)
        
        return {
            **state,
            "image_paths": image_paths
        }


# ============================================================================
# 헬퍼 함수들
# ============================================================================

def load_prompts(prompts_path: str) -> List[Dict[str, Any]]:
    """프롬프트 JSON 로드"""
    with open(prompts_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_image_manifest(
    image_paths: Dict[str, str],
    output_path: str
):
    """이미지 매니페스트 저장"""
    manifest = {
        'total_images': len(image_paths),
        'images': [
            {
                'image_id': image_id,
                'path': path,
                'filename': os.path.basename(path)
            }
            for image_id, path in image_paths.items()
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 이미지 매니페스트 저장: {output_path}")


def print_generation_summary(image_paths: Dict[str, str]):
    """생성 결과 요약"""
    print("\n" + "="*80)
    print("📊 생성 결과 요약")
    print("="*80)
    
    print(f"\n총 {len(image_paths)}개 이미지:")
    
    for image_id, path in sorted(image_paths.items()):
        file_size = os.path.getsize(path) / 1024  # KB
        print(f"  - {image_id}: {os.path.basename(path)} ({file_size:.1f} KB)")


if __name__ == "__main__":
    print("Image Generation Node - 이미지 생성 노드 (나노바나나 🍌)")
    print("Import해서 사용하세요: from image_generation_node import ImageGenerationNode")