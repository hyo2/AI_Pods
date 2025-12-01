"""
이미지 생성 노드 (LangGraph)
토픽 리스트를 받아 각 토픽마다 이미지 생성
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import os


@dataclass
class GeneratedImage:
    """생성된 이미지 정보"""
    topic_id: str
    topic_title: str
    image_path: str
    generation_method: str  # "imagen-4", "gemini" 등
    style: str
    prompt_used: str
    keywords: List[str]
    importance: float
    metadata: Optional[Dict[str, Any]] = None


class ImageGenerationNode:
    """토픽별 이미지 생성 노드"""
    
    def __init__(
        self,
        imagen_service=None,
        output_dir: str = "./generated_images",
        default_method: str = "gemini",  # or "imagen-4", "imagen-4-fast"
        auto_delay: int = 3
    ):
        """
        Args:
            imagen_service: ImagenService 인스턴스 (None이면 생성)
            output_dir: 이미지 저장 디렉토리
            default_method: 기본 생성 방법
            auto_delay: 각 생성 간 대기 시간 (초)
        """
        self.output_dir = output_dir
        self.default_method = default_method
        self.auto_delay = auto_delay
        
        # ImagenService 초기화
        if imagen_service is None:
            try:
                from app.services.imagen_service import ImagenService
                # 기존 ImagenService는 default_model 파라미터가 없을 수 있음
                self.imagen = ImagenService(
                    project_id="alan-document-lab",
                    credentials_path="./vertex-ai-service-account.json"
                )
            except Exception as e:
                print(f"⚠️  ImagenService 초기화 실패: {e}")
                self.imagen = None
        else:
            self.imagen = imagen_service
        
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_images_from_topics(
        self,
        topics: List,  # List[ImageTopic]
        strategy: str = "auto",  # "fast", "quality", "hybrid", "auto"
        use_optimized_prompt: bool = True
    ) -> List[GeneratedImage]:
        """
        토픽 리스트에서 이미지 생성
        
        Args:
            topics: ImageTopic 리스트
            strategy: 생성 전략
                - "fast": Gemini만 사용 (빠름)
                - "quality": Imagen 4만 사용 (고품질)
                - "hybrid": 중요도에 따라 혼합
                - "auto": 스타일에 따라 자동 선택
            use_optimized_prompt: Gemini 프롬프트 최적화 사용
        
        Returns:
            GeneratedImage 리스트
        """
        print(f"\n🎨 이미지 생성 시작: {len(topics)}개 토픽")
        print(f"전략: {strategy}")
        print(f"출력 디렉토리: {self.output_dir}")
        
        results = []
        
        for i, topic in enumerate(topics, 1):
            print(f"\n[{i}/{len(topics)}] 생성 중: {topic.title}")
            print(f"  스타일: {topic.style}")
            print(f"  중요도: {topic.importance:.2f}")
            
            try:
                # 생성 방법 결정
                method = self._decide_generation_method(topic, strategy)
                print(f"  방법: {method}")
                
                # 이미지 생성
                if self.imagen and hasattr(self.imagen, 'generate_topic_image'):
                    # 기존 ImagenService 메서드 사용
                    result = self.imagen.generate_topic_image(
                        topic=topic.topic_id,
                        description=topic.description,
                        keywords=topic.keywords,
                        style=topic.style,
                        method=method,
                        output_dir=self.output_dir,
                        auto_delay=self.auto_delay if i < len(topics) else 0,
                        use_optimized_prompt=use_optimized_prompt
                    )
                else:
                    # 직접 Vertex AI 호출
                    result = self._generate_image_direct(
                        topic=topic,
                        method=method,
                        use_optimized_prompt=use_optimized_prompt
                    )
                    
                    # 딜레이
                    if i < len(topics):
                        import time
                        time.sleep(self.auto_delay)
                
                # GeneratedImage 생성
                generated = GeneratedImage(
                    topic_id=topic.topic_id,
                    topic_title=topic.title,
                    image_path=result['image_path'],
                    generation_method=method,
                    style=topic.style,
                    prompt_used=result.get('annotation', {}).get('imagen_prompt', topic.description),
                    keywords=topic.keywords,
                    importance=topic.importance,
                    metadata={
                        'description': topic.description,
                        'context': topic.context,
                        'annotation': result.get('annotation', {})
                    }
                )
                
                results.append(generated)
                print(f"  ✅ 성공: {result['image_path']}")
                
            except Exception as e:
                print(f"  ❌ 실패: {str(e)}")
                # 실패해도 계속 진행
                continue
        
        success_count = len(results)
        print(f"\n✨ 이미지 생성 완료: {success_count}/{len(topics)}")
        
        return results
    
    def _generate_image_direct(
        self,
        topic,
        method: str,
        use_optimized_prompt: bool
    ) -> Dict[str, Any]:
        """
        Vertex AI를 직접 호출하여 이미지 생성
        (ImagenService가 없거나 메서드가 없을 때)
        """
        from vertexai.preview.vision_models import ImageGenerationModel
        from vertexai.generative_models import GenerativeModel
        import hashlib
        import time
        
        # 프롬프트 준비
        if use_optimized_prompt and method == "gemini":
            # Gemini로 프롬프트 최적화
            prompt = self._optimize_prompt_for_gemini(topic, method)
        else:
            prompt = topic.description
        
        # 이미지 생성
        if method == "gemini":
            # Gemini 2.5 Flash로 이미지 생성
            model = GenerativeModel("gemini-2.0-flash-exp")
            
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.4,
                    "response_modalities": ["IMAGE"]
                }
            )
            
            # 이미지 저장
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data'):
                            # Base64 이미지 저장
                            import base64
                            image_data = base64.b64decode(part.inline_data.data)
                            
                            filename = f"{topic.topic_id}.png"
                            image_path = os.path.join(self.output_dir, filename)
                            
                            with open(image_path, 'wb') as f:
                                f.write(image_data)
                            
                            return {
                                'image_path': image_path,
                                'annotation': {
                                    'imagen_prompt': prompt,
                                    'method': 'gemini'
                                }
                            }
        
        elif method in ["imagen-4", "imagen-4-fast", "imagen-4-ultra"]:
            # Imagen 4로 이미지 생성
            model_map = {
                "imagen-4": "imagen-4.0-generate-001",
                "imagen-4-fast": "imagen-4.0-fast-generate-001",
                "imagen-4-ultra": "imagen-4.0-ultra-generate-001"
            }
            
            model = ImageGenerationModel.from_pretrained(model_map[method])
            
            images = model.generate_images(
                prompt=prompt,
                number_of_images=1,
                aspect_ratio="16:9",
                safety_filter_level="block_some",
                person_generation="allow_adult"
            )
            
            if images:
                filename = f"{topic.topic_id}.png"
                image_path = os.path.join(self.output_dir, filename)
                images[0].save(image_path)
                
                return {
                    'image_path': image_path,
                    'annotation': {
                        'imagen_prompt': prompt,
                        'method': method
                    }
                }
        
        raise Exception(f"이미지 생성 실패: {method}")
    
    def _optimize_prompt_for_gemini(self, topic, target_method: str) -> str:
        """Gemini로 프롬프트 최적화"""
        from vertexai.generative_models import GenerativeModel
        
        optimization_prompt = f"""You are an expert at creating image generation prompts.

Given this topic information:
- Title: {topic.title}
- Description: {topic.description}
- Style: {topic.style}
- Keywords: {', '.join(topic.keywords)}

Create an optimized prompt for {target_method} image generation.

Rules:
- Natural conversational style (not keyword lists)
- Keep it under 80 words
- Focus on visual elements
- Include style guidance

Output ONLY the optimized prompt, nothing else."""

        model = GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(
            optimization_prompt,
            generation_config={"temperature": 0.4}
        )
        
        return response.text.strip()
    
    def _decide_generation_method(self, topic, strategy: str) -> str:
        """토픽과 전략에 따라 생성 방법 결정"""
        
        if strategy == "fast":
            return "gemini"
        
        elif strategy == "quality":
            return "imagen-4"
        
        elif strategy == "hybrid":
            # 중요도에 따라 결정
            if topic.importance >= 0.8:
                return "imagen-4"  # 고품질
            else:
                return "gemini"  # 빠른 생성
        
        elif strategy == "auto":
            # 스타일에 따라 자동 선택
            style_method_map = {
                "abstract": "gemini",      # 빠르고 충분
                "technical": "imagen-4",   # 정확성 중요
                "illustration": "gemini",  # 빠르고 충분
                "photo": "imagen-4",       # 고품질 필요
                "scene": "imagen-4"        # 복잡성, 고품질
            }
            return style_method_map.get(topic.style, "gemini")
        
        else:
            return self.default_method
    
    def __call__(self, state: dict) -> dict:
        """
        LangGraph 노드 실행
        
        Expected state:
            - image_topics: List[ImageTopic]
        
        Returns:
            - generated_images: List[GeneratedImage]
        """
        topics = state.get("image_topics", [])
        
        if not topics:
            raise ValueError("No image_topics in state")
        
        strategy = state.get("generation_strategy", "auto")
        
        results = self.generate_images_from_topics(
            topics,
            strategy=strategy
        )
        
        return {
            **state,
            "generated_images": results
        }


# ============================================================================
# 헬퍼 함수
# ============================================================================

def print_generation_summary(images: List[GeneratedImage]):
    """생성 결과 요약 출력"""
    print("\n" + "="*80)
    print("🖼️  생성된 이미지")
    print("="*80)
    
    print(f"\n총 {len(images)}개 이미지")
    
    # 방법별 분포
    method_counts = {}
    for img in images:
        method_counts[img.generation_method] = method_counts.get(img.generation_method, 0) + 1
    
    print("\n생성 방법 분포:")
    for method, count in sorted(method_counts.items()):
        print(f"  {method}: {count}개")
    
    # 스타일별 분포
    style_counts = {}
    for img in images:
        style_counts[img.style] = style_counts.get(img.style, 0) + 1
    
    print("\n스타일 분포:")
    for style, count in sorted(style_counts.items()):
        print(f"  {style}: {count}개")
    
    # 이미지 목록
    print("\n" + "-"*80)
    print("이미지 상세")
    print("-"*80)
    
    for i, img in enumerate(images, 1):
        print(f"\n[{i}] {img.topic_id}")
        print(f"  제목: {img.topic_title}")
        print(f"  경로: {img.image_path}")
        print(f"  방법: {img.generation_method}")
        print(f"  스타일: {img.style}")
        print(f"  중요도: {img.importance:.2f}")


def save_generation_results(images: List[GeneratedImage], output_path: str):
    """생성 결과를 JSON으로 저장"""
    import json
    
    results_dict = [asdict(img) for img in images]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results_dict, f, ensure_ascii=False, indent=2)
    
    print(f"💾 생성 결과 저장: {output_path}")


def create_image_gallery_html(images: List[GeneratedImage], output_path: str):
    """이미지 갤러리 HTML 생성"""
    html_template = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>생성된 이미지 갤러리</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            text-align: center;
            color: #333;
            margin-bottom: 10px;
        }}
        .stats {{
            text-align: center;
            color: #666;
            margin-bottom: 30px;
        }}
        .gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }}
        .image-card {{
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        .image-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        .image-card img {{
            width: 100%;
            height: 300px;
            object-fit: cover;
        }}
        .image-info {{
            padding: 15px;
        }}
        .image-title {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 8px;
            color: #333;
        }}
        .image-meta {{
            font-size: 14px;
            color: #666;
            margin-bottom: 5px;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 12px;
            margin-right: 5px;
            margin-top: 5px;
        }}
        .badge-method {{
            background: #e3f2fd;
            color: #1976d2;
        }}
        .badge-style {{
            background: #f3e5f5;
            color: #7b1fa2;
        }}
        .badge-importance {{
            background: #fff3e0;
            color: #f57c00;
        }}
    </style>
</head>
<body>
    <h1>🎨 생성된 이미지 갤러리</h1>
    <div class="stats">총 {total_count}개 이미지</div>
    
    <div class="gallery">
        {image_cards}
    </div>
</body>
</html>
"""
    
    card_template = """
        <div class="image-card">
            <img src="{image_path}" alt="{title}">
            <div class="image-info">
                <div class="image-title">{title}</div>
                <div class="image-meta">{topic_id}</div>
                <div>
                    <span class="badge badge-method">{method}</span>
                    <span class="badge badge-style">{style}</span>
                    <span class="badge badge-importance">중요도: {importance:.2f}</span>
                </div>
            </div>
        </div>
"""
    
    # 이미지 카드 생성
    cards = []
    for img in images:
        card = card_template.format(
            image_path=os.path.basename(img.image_path),
            title=img.topic_title,
            topic_id=img.topic_id,
            method=img.generation_method,
            style=img.style,
            importance=img.importance
        )
        cards.append(card)
    
    # HTML 생성
    html = html_template.format(
        total_count=len(images),
        image_cards="\n".join(cards)
    )
    
    # 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"🌐 갤러리 HTML 생성: {output_path}")
    print(f"   브라우저에서 열어보세요!")
