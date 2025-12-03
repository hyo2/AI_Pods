# app/services/podcast/prompt_service.py
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PromptTemplateService:
    """프롬프트 템플릿 관리 서비스 (하드코딩 버전)"""
    
    @staticmethod
    def get_template(style_id: str) -> Optional[Dict]:
        """스타일 ID로 템플릿 조회"""
        templates = {
            "explain": {
                "style_id": "explain",
                "style_name": "설명형",
                "system_prompt": "당신은 복잡한 개념을 쉽게 설명하는 교육 팟캐스트 전문가입니다.",
                "user_prompt_template": """아래 텍스트를 분석하여 두 명의 화자(진행자, 게스트)가 대화하는 형식의 팟캐스트 스크립트를 한국어로 작성해 주세요.

**[중요: 화자 태그 규칙]**
- 화자를 구분할 때는 반드시 "[진행자]"와 "[게스트]" 태그만 사용하세요.
- 대화 내용 안에서 이름을 언급할 때만 "{host_name}", "{guest_name}"을 사용하세요.

**[설명형 스타일 특징]**
1. **진행자:** 청취자를 대표하여 "이게 무슨 뜻이죠?" 같은 질문을 합니다.
2. **게스트:** 복잡한 개념을 일상적인 비유와 예시로 쉽게 풀어서 설명합니다.
3. **톤:** 친절하고 교육적입니다.

원본 텍스트:
---
{combined_text}
---"""
            },
            "debate": {
                "style_id": "debate",
                "style_name": "토론형",
                "system_prompt": "당신은 균형 잡힌 시각으로 다양한 관점을 제시하는 토론 팟캐스트 전문가입니다.",
                "user_prompt_template": """아래 텍스트를 분석하여 두 명의 화자가 토론하는 형식의 팟캐스트 스크립트를 한국어로 작성해 주세요.

**[중요: 화자 태그 규칙]**
- 화자를 구분할 때는 반드시 "[진행자]"와 "[게스트]" 태그만 사용하세요.

**[토론형 스타일 특징]**
1. **진행자:** 논쟁적인 질문을 던지고, 반대 의견을 제시합니다.
2. **게스트:** 자신의 관점을 논리적으로 방어하고, 근거를 들어 반박합니다.
3. **톤:** 활기차고 논쟁적입니다.

원본 텍스트:
---
{combined_text}
---"""
            },
            "interview": {
                "style_id": "interview",
                "style_name": "인터뷰",
                "system_prompt": "당신은 깊이 있는 질문으로 게스트의 이야기를 이끌어내는 인터뷰 팟캐스트 전문가입니다.",
                "user_prompt_template": """아래 텍스트를 분석하여 인터뷰 형식의 팟캐스트 스크립트를 한국어로 작성해 주세요.

**[중요: 화자 태그 규칙]**
- 화자를 구분할 때는 반드시 "[진행자]"와 "[게스트]" 태그만 사용하세요.

**[인터뷰 스타일 특징]**
1. **진행자:** 게스트의 경험과 생각을 깊이 있게 파고드는 질문을 합니다.
2. **게스트:** 자신의 경험, 실패담, 성공 스토리를 구체적으로 이야기합니다. (게스트 발언 비중 70% 이상)
3. **톤:** 진지하고 깊이 있습니다.

원본 텍스트:
---
{combined_text}
---"""
            },
            "summary": {
                "style_id": "summary",
                "style_name": "요약 중심",
                "system_prompt": "당신은 핵심만 간결하게 전달하는 뉴스 브리핑 스타일의 팟캐스트 전문가입니다.",
                "user_prompt_template": """아래 텍스트를 분석하여 요약 중심의 팟캐스트 스크립트를 한국어로 작성해 주세요.

**[중요: 화자 태그 규칙]**
- 화자를 구분할 때는 반드시 "[진행자]"와 "[게스트]" 태그만 사용하세요.

**[요약 중심 스타일 특징]**
1. **진행자:** "핵심만 요약하면?" 같은 직접적인 질문을 합니다.
2. **게스트:** 불릿 포인트 형식으로 간결하게 답변합니다. "첫째, 둘째, 셋째"
3. **톤:** 간결하고 명확합니다.
4. **길이:** 전체 대화를 짧게 유지합니다.

원본 텍스트:
---
{combined_text}
---"""
            }
        }
        
        template = templates.get(style_id)
        if template:
            logger.info(f"템플릿 로드: {style_id}")
            return template
        else:
            logger.warning(f"템플릿을 찾을 수 없음: {style_id}, 기본값 사용")
            return None
    
    @staticmethod
    def list_templates() -> list:
        """활성화된 모든 템플릿 목록 조회"""
        return [
            {"style_id": "explain", "style_name": "설명형", "description": "복잡한 개념을 쉽게 설명"},
            {"style_id": "debate", "style_name": "토론형", "description": "찬반 의견 토론"},
            {"style_id": "interview", "style_name": "인터뷰", "description": "깊이 있는 인터뷰"},
            {"style_id": "summary", "style_name": "요약 중심", "description": "핵심만 간결하게"}
        ]
    
    @staticmethod
    def get_default_template() -> Dict:
        """기본 템플릿 반환 (설명형)"""
        template = PromptTemplateService.get_template("explain")
        if not template:
            # 폴백
            return {
                "style_id": "explain",
                "style_name": "설명형",
                "system_prompt": "당신은 팟캐스트 전문가입니다.",
                "user_prompt_template": "아래 텍스트로 팟캐스트를 만드세요:\n{combined_text}"
            }
        return template