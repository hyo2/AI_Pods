"""이미지 생성 서비스"""
import logging
from typing import List, Optional
import base64
from io import BytesIO
from PIL import Image
from google.cloud import aiplatform

logger = logging.getLogger(__name__)


class ImageGenerationService:
    """Google Vertex AI Imagen을 사용한 이미지 생성"""

    def __init__(self, project_id: str, region: str = "us-central1"):
        """
        이미지 생성 서비스 초기화
        
        Args:
            project_id: Google Cloud 프로젝트 ID
            region: Vertex AI 지역
        """
        self.project_id = project_id
        self.region = region
        aiplatform.init(project=project_id, location=region)

    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1
    ) -> List[str]:
        """
        이미지 생성
        
        Args:
            prompt: 이미지 생성 프롬프트
            width: 이미지 너비
            height: 이미지 높이
            num_images: 생성할 이미지 수
        
        Returns:
            생성된 이미지 Base64 문자열 리스트
        """
        try:
            from vertexai.preview.vision_models import ImageGenerationModel
            
            model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
            
            images = model.generate_images(
                prompt=prompt,
                number_of_images=num_images,
                width=width,
                height=height,
                safety_filter_level="block_few",
                person_generation="allow_adult"
            )
            
            image_urls = []
            for image in images:
                image_urls.append(image._image_bytes)
            
            logger.info(f"Generated {len(image_urls)} images")
            return image_urls
            
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return []

    async def generate_batch(
        self,
        prompts: List[str],
        width: int = 1024,
        height: int = 1024
    ) -> List[List[str]]:
        """
        여러 프롬프트로부터 배치로 이미지 생성
        
        Args:
            prompts: 이미지 생성 프롬프트 리스트
            width: 이미지 너비
            height: 이미지 높이
        
        Returns:
            생성된 이미지 리스트의 리스트
        """
        all_images = []
        
        for prompt in prompts:
            images = await self.generate_image(
                prompt=prompt,
                width=width,
                height=height,
                num_images=1
            )
            all_images.append(images)
        
        return all_images
