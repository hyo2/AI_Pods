import os
import base64
from typing import List, Optional
from PIL import Image
import io
from google.cloud import aiplatform
from vertexai.preview.vision_models import ImageGenerationModel
import vertexai

class ImagenService:
    """Google Vertex AI 이미지 생성 서비스 (Imagen + Gemini)"""
    
    def __init__(
        self, 
        project_id: str,
        location: str = "us-central1",
        credentials_path: Optional[str] = None,
        default_method: str = "imagen"  # ⭐ "imagen" 또는 "gemini"
    ):
        self.project_id = project_id
        self.location = location
        self.default_method = default_method
        
        # Credentials 설정
        if credentials_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        
        # Vertex AI 초기화
        vertexai.init(project=project_id, location=location)
        
        # Imagen 모델 로드
        self.imagen_model = ImageGenerationModel.from_pretrained("imagen-4.0-generate-001")
        
        # Gemini 클라이언트 초기화 (이미지 생성용)
        from google import genai
        from google.genai.types import HttpOptions
        self.gemini_client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
            http_options=HttpOptions(api_version="v1")
        )
    
    def generate_imagen_prompt(self, topic: str, description: str, style: str) -> str:
        """Gemini를 사용해서 Imagen 프롬프트 생성"""
        from vertexai.generative_models import GenerativeModel
        
        gemini = GenerativeModel("gemini-2.5-flash")
        
        style_guides = {
            "abstract": "Create an abstract, modern, minimalist illustration",
            "technical": "Create a clean technical diagram or infographic",
            "illustration": "Create a creative illustration or artistic rendering",
            "photo": "Create a photorealistic image",
            "scene": "Create a detailed scene illustration with characters and actions"
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
"""

        if style == "scene":
            prompt += """
- Show specific characters, actions, and emotions
- Tell a visual story with clear narrative
- Include environmental details and context
- Make it engaging and illustrative
"""
        else:
            prompt += """
- NO text, NO people faces, NO watermarks
- Clear, clean, suitable for background or visual accent
"""

        prompt += """

Write a detailed Imagen prompt (2-3 sentences maximum).
Focus on: subject, context/background, visual style, color scheme.

Output only the prompt text, nothing else.
"""

        response = gemini.generate_content(prompt)
        return response.text.strip()
    
    def _generate_with_imagen(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        output_path: Optional[str] = None
    ) -> dict:
        """Imagen으로 이미지 생성"""
        images = self.imagen_model.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio=aspect_ratio,
            add_watermark=False,
        )
        
        image = images[0]
        
        if output_path is None:
            output_path = f"/tmp/imagen_{hash(prompt)}.png"
        
        image.save(output_path)
        image_bytes = image._image_bytes
        
        return {
            "image_path": output_path,
            "image_bytes": image_bytes,
            "enhanced_prompt": prompt
        }
    
    def _generate_with_gemini(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        output_path: Optional[str] = None
    ) -> dict:
        """Gemini 2.5 Flash Image (나노바나나)로 이미지 생성"""
        from google.genai.types import GenerateContentConfig, ImageConfig
        
        response = self.gemini_client.models.generate_content(
            model='gemini-2.5-flash-image',
            contents=prompt,
            config=GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=ImageConfig(
                    aspect_ratio=aspect_ratio,
                ),
            ),
        )
        
        # 이미지 추출
        generated_image = None
        image_bytes = None
        
        for part in response.parts:
            if part.inline_data:
                # PIL Image로 변환
                generated_image = part.as_image()
                # 바이트 데이터도 저장
                image_bytes = part.inline_data.data  # ⭐ 수정
                break
        
        if generated_image is None:
            raise Exception("Gemini가 이미지를 생성하지 못했습니다")
        
        # 저장
        if output_path is None:
            output_path = f"/tmp/gemini_{hash(prompt)}.png"
        
        generated_image.save(output_path)  # ⭐ format 제거
        
        return {
            "image_path": output_path,
            "image_bytes": image_bytes,
            "enhanced_prompt": prompt
        }
    
    def generate_image(
        self,
        prompt: str,
        method: Optional[str] = None,  # ⭐ "imagen" 또는 "gemini"
        aspect_ratio: str = "16:9",
        negative_prompt: Optional[str] = None,
        enhance_prompt: bool = True,
        output_path: Optional[str] = None,
        max_retries: int = 5,
        base_delay: int = 8
    ) -> dict:
        """이미지 생성 (Exponential Backoff 재시도)"""
        import time
        import random
        
        # method 기본값
        if method is None:
            method = self.default_method
        
        for attempt in range(max_retries):
            try:
                # 생성 방법 선택
                if method == "imagen":
                    return self._generate_with_imagen(prompt, aspect_ratio, output_path)
                elif method == "gemini":
                    return self._generate_with_gemini(prompt, aspect_ratio, output_path)
                else:
                    raise ValueError(f"Unknown method: {method}. Use 'imagen' or 'gemini'")
                    
            except Exception as e:
                error_message = str(e)
                
                # 429 Quota exceeded 에러 확인
                if "429" in error_message or "Quota exceeded" in error_message:
                    if attempt < max_retries - 1:
                        wait_time = base_delay * (2 ** attempt) + random.uniform(0, 2)
                        print(f"⚠️  할당량 초과 (시도 {attempt + 1}/{max_retries})")
                        print(f"⏳ {wait_time:.1f}초 대기 후 재시도...")
                        time.sleep(wait_time)
                    else:
                        print(f"❌ 최대 재시도 횟수({max_retries}) 초과")
                        raise
                else:
                    print(f"❌ 에러 발생: {error_message}")
                    raise
        
        raise Exception("이미지 생성 실패: 최대 재시도 횟수 초과")
    
    def generate_topic_image(
        self,
        topic: str,
        description: str,
        keywords: List[str],
        style: str = "abstract",
        method: Optional[str] = None,  # ⭐ 추가
        output_dir: str = "/tmp",
        auto_delay: int = 5
    ) -> dict:
        """토픽 기반 이미지 생성 (전체 파이프라인)"""
        import time
        
        # 1. Gemini로 Imagen 프롬프트 생성
        imagen_prompt = self.generate_imagen_prompt(topic, description, style)
        
        print(f"📝 Generated prompt: {imagen_prompt}")
        print(f"🎨 생성 방식: {method or self.default_method}")
        
        # 2. 파일명 생성 (중복 시 넘버링)
        base_filename = topic.replace(' ', '_').replace('/', '_')
        output_path = os.path.join(output_dir, f"{base_filename}.png")
        
        counter = 1
        while os.path.exists(output_path):
            output_path = os.path.join(output_dir, f"{base_filename}_{counter}.png")
            counter += 1
        
        # 3. 이미지 생성 (Imagen 또는 Gemini)
        result = self.generate_image(
            prompt=imagen_prompt,
            method=method,
            output_path=output_path
        )
        
        # 4. 자동 delay
        if auto_delay > 0:
            print(f"⏳ 다음 요청 방지를 위해 {auto_delay}초 대기...")
            time.sleep(auto_delay)
        
        # 5. 주석 추가
        return {
            "image_path": result["image_path"],
            "annotation": {
                "topic": topic,
                "keywords": keywords,
                "description": description,
                "imagen_prompt": imagen_prompt,
                "generation_method": method or self.default_method  # ⭐ 추가
            }
        }