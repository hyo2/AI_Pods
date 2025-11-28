import os
import base64
from typing import List, Optional
from google.cloud import aiplatform
from vertexai.preview.vision_models import ImageGenerationModel
import vertexai

class ImagenService:
    """Google Vertex AI Imagen 서비스"""
    
    def __init__(
        self, 
        project_id: str,
        location: str = "us-central1",
        credentials_path: Optional[str] = None
    ):
        self.project_id = project_id
        self.location = location
        
        # Credentials 설정
        if credentials_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        
        # Vertex AI 초기화
        vertexai.init(project=project_id, location=location)
        
        # Imagen 모델 로드
        self.model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")
    
    def generate_imagen_prompt(self, topic: str, description: str, style: str) -> str:
        """
        Gemini를 사용해서 Imagen 프롬프트 생성
        
        Args:
            topic: 토픽 (예: "AI 연구")
            description: 설명
            style: 스타일 (abstract, technical, illustration, photo)
        
        Returns:
            Imagen 프롬프트
        """
        from vertexai.generative_models import GenerativeModel
        
        gemini = GenerativeModel("gemini-2.5-flash")
        
        style_guides = {
            "abstract": "Create an abstract, modern, minimalist illustration",
            "technical": "Create a clean technical diagram or infographic",
            "illustration": "Create a creative illustration or artistic rendering",
            "photo": "Create a photorealistic image"
        }
        
        prompt = f"""
You are an expert at writing prompts for Imagen (Google's image generation AI).

Topic: {topic}
Description: {description}
Style: {style}

{style_guides.get(style, style_guides['abstract'])} for this topic.

Requirements:
- Aspect ratio will be 16:9 (suitable for video)
- Professional quality for presentation/video overlay
- Blue theme preferred (corporate/professional)
- NO text, NO people faces, NO watermarks
- Clear, clean, suitable for background or visual accent

Write a detailed Imagen prompt (2-3 sentences maximum).
Focus on: subject, context/background, visual style, color scheme.

Output only the prompt text, nothing else.
"""
        
        response = gemini.generate_content(prompt)
        return response.text.strip()
    
    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        negative_prompt: Optional[str] = None,
        enhance_prompt: bool = True,
        output_path: Optional[str] = None
    ) -> dict:
        """
        Imagen으로 이미지 생성
        
        Args:
            prompt: Imagen 프롬프트
            aspect_ratio: 비율 (16:9, 1:1, 9:16, 4:3, 3:4)
            negative_prompt: 제외할 요소 (선택)
            enhance_prompt: 자동 프롬프트 개선
            output_path: 저장 경로 (None이면 임시)
        
        Returns:
            {
                "image_path": "...",
                "image_bytes": b"...",
                "enhanced_prompt": "..."
            }
        """
        # 이미지 생성
        images = self.model.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio=aspect_ratio,
            add_watermark=False,
            # negative_prompt는 SDK에서 지원 안 할 수도 있음
        )
        
        # 첫 번째 이미지
        image = images[0]
        
        # 저장 경로 설정
        if output_path is None:
            output_path = f"/tmp/imagen_{hash(prompt)}.png"
        
        # 이미지 저장
        image.save(output_path)
        
        # 이미지 바이트 가져오기
        image_bytes = image._image_bytes
        
        return {
            "image_path": output_path,
            "image_bytes": image_bytes,
            "enhanced_prompt": prompt  # SDK가 enhanced prompt 반환하면 사용
        }
    
    def generate_topic_image(
        self,
        topic: str,
        description: str,
        keywords: List[str],
        style: str = "abstract",
        output_dir: str = "/tmp"
    ) -> dict:
        """
        토픽 기반 이미지 생성 (전체 파이프라인)
        
        Returns:
            {
                "image_path": "...",
                "annotation": {
                    "topic": "...",
                    "keywords": [...],
                    "description": "...",
                    "imagen_prompt": "..."
                }
            }
        """
        # 1. Gemini로 Imagen 프롬프트 생성
        imagen_prompt = self.generate_imagen_prompt(topic, description, style)
        
        print(f"📝 Generated prompt: {imagen_prompt}")
        
        # 2. Imagen으로 이미지 생성
        output_path = os.path.join(output_dir, f"{topic.replace(' ', '_')}.png")
        result = self.generate_image(
            prompt=imagen_prompt,
            output_path=output_path
        )
        
        # 3. 주석 추가
        return {
            "image_path": result["image_path"],
            "annotation": {
                "topic": topic,
                "keywords": keywords,
                "description": description,
                "imagen_prompt": imagen_prompt
            }
        }