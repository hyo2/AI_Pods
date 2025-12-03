from typing import TypedDict, List
from app.services.imagen_service import ImagenService

class GeneratedImage(TypedDict):
    """생성된 이미지 정보"""
    image_index: int
    image_path: str
    annotation: dict

def generate_images(state: dict) -> dict:
    """
    LangGraph 노드: 이미지 생성
    
    Input (state):
        - summary: str (요약문)
        
    Output (state):
        - images_with_annotations: List[GeneratedImage]
    """
    summary = state.get("summary", "")
    
    if not summary:
        print("⚠️  요약문이 없습니다. 이미지 생성 스킵.")
        return {"images_with_annotations": []}
    
    # Imagen 서비스 초기화
    imagen = ImagenService(
        project_id="alan-document-lab",
        credentials_path="./vertex-ai-service-account.json"  # 경로 수정 필요
    )
    
    # 1. Gemini로 토픽 추출
    from vertexai.generative_models import GenerativeModel
    gemini = GenerativeModel("")
    
    topics_prompt = f"""
다음 요약문에서 시각화가 필요한 주요 토픽을 3-5개 추출하세요.

요약문:
{summary}

각 토픽에 대해 다음 JSON 형식으로 응답:
{{
  "topics": [
    {{
      "topic": "토픽명",
      "description": "간단한 설명 (1-2문장)",
      "keywords": ["키워드1", "키워드2"],
      "style": "abstract"
    }}
  ]
}}

style은 다음 중 선택: abstract, technical, illustration, photo
"""
    
    response = gemini.generate_content(topics_prompt)
    
    # JSON 파싱 (간단하게)
    import json
    topics_text = response.text.strip()
    # ```json 제거
    if "```json" in topics_text:
        topics_text = topics_text.split("```json")[1].split("```")[0]
    
    topics_data = json.loads(topics_text)
    topics = topics_data["topics"]
    
    print(f"📌 추출된 토픽: {len(topics)}개")
    
    # 2. 각 토픽마다 이미지 생성
    images_with_annotations = []
    
    for i, topic_info in enumerate(topics):
        print(f"\n🎨 [{i+1}/{len(topics)}] {topic_info['topic']} 이미지 생성 중...")
        
        result = imagen.generate_topic_image(
            topic=topic_info["topic"],
            description=topic_info["description"],
            keywords=topic_info["keywords"],
            style=topic_info.get("style", "abstract"),
            output_dir="/tmp/generated_images"
        )
        
        images_with_annotations.append({
            "image_index": i,
            "image_path": result["image_path"],
            "annotation": result["annotation"]
        })
        
        print(f"✅ 저장: {result['image_path']}")
    
    print(f"\n✨ 총 {len(images_with_annotations)}개 이미지 생성 완료!")
    
    return {"images_with_annotations": images_with_annotations}