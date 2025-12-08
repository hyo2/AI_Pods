"""이미지 생성 계획 및 프롬프트 생성"""
import logging
from typing import List, Dict, Any
from podcast.prompt_service import PromptTemplateService

logger = logging.getLogger(__name__)


class ImagePlanner:
    """이미지 생성을 위한 계획 및 프롬프트 생성"""

    def __init__(self):
        """이미지 플래너 초기화"""
        self.prompt_service = PromptTemplateService()

    def plan_images(
        self,
        script: str,
        topics: List[Dict[str, Any]],
        style: str = "realistic"
    ) -> List[Dict[str, Any]]:
        """
        이미지 생성 계획 수립
        
        Args:
            script: 팟캐스트 스크립트
            topics: 추출된 토픽 리스트
            style: 이미지 스타일
        
        Returns:
            이미지 생성 계획 리스트
        """
        image_plans = []
        
        for topic in topics:
            prompt = self._generate_image_prompt(
                topic["title"],
                style
            )
            
            plan = {
                "id": topic["id"],
                "topic": topic["title"],
                "timestamp": topic["timestamp"],
                "prompt": prompt,
                "style": style,
                "size": "1024x1024"
            }
            
            image_plans.append(plan)
        
        logger.info(f"Created image plans for {len(image_plans)} topics")
        return image_plans

    def _generate_image_prompt(
        self,
        topic: str,
        style: str = "realistic"
    ) -> str:
        """
        토픽으로부터 이미지 생성 프롬프트 생성
        
        Args:
            topic: 토픽 제목
            style: 이미지 스타일
        
        Returns:
            이미지 생성 프롬프트
        """
        style_desc = {
            "realistic": "realistic, high quality, professional photography",
            "cartoon": "cartoon, colorful, illustration style",
            "abstract": "abstract, modern, artistic",
            "anime": "anime style, vibrant colors"
        }.get(style, "high quality, professional")
        
        prompt = f"{topic}\n{style_desc}, 4K resolution, detailed"
        return prompt
