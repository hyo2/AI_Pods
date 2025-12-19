# app/langgraph_pipeline/podcast/prompt_service.py
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

class PromptTemplateService:
    """Supabase 기반 프롬프트 템플릿 서비스"""

    @staticmethod
    def get_template(supabase_client, style_id: str) -> Optional[Dict]:
        """
        Supabase에서 style_id로 템플릿 조회
        :param supabase_client: Supabase 클라이언트 객체
        """
        try:
            # Supabase 방식의 쿼리 (SQL 대신 사용)
            response = supabase_client.table("prompt_templates")\
                .select("*")\
                .eq("style_id", style_id)\
                .eq("is_active", True)\
                .execute()

            # 데이터가 있으면 첫 번째 항목 반환
            if response.data and len(response.data) > 0:
                result = response.data[0]
                logger.info(f"Supabase 템플릿 로드 성공: {style_id}")
                return {
                    "style_id": result["style_id"],
                    "style_name": result["style_name"],
                    "system_prompt": result["system_prompt"],
                    "user_prompt_template": result["user_prompt_template"]
                }
            else:
                logger.warning(f"Supabase에서 템플릿을 찾을 수 없음: {style_id}")
                return None
                
        except Exception as e:
            logger.error(f"템플릿 조회 중 Supabase 오류 발생: {e}")
            return None

    @staticmethod
    def get_default_template(supabase_client) -> Dict:
        """기본 템플릿 반환 (explain)"""
        template = PromptTemplateService.get_template(supabase_client, "explain")
        if not template:
            # DB 연결 실패 시 하드코딩 폴백
            return {
                "style_id": "explain",
                "style_name": "Basic Explanation (Fallback)",
                "system_prompt": "You are a teacher. Respond in Korean.",
                "user_prompt_template": "Create a dialogue in Korean:\n{combined_text}"
            }
        return template