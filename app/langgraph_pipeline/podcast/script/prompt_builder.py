# app/langgraph_pipeline/podcast/script/prompt_builder.py
import logging
logger = logging.getLogger(__name__)

def create_prompt(
    combined_text: str,
    host_name: str,
    guest_name: str,
    duration: float,
    difficulty: str,
    user_prompt: str,
    budget: int,
    style: str,
    user_prompt_template: str,
) -> str:
    """budget은 외부에서 받고, style/template도 인자로 받아 순수 함수로 생성"""

    max_text_length = 60000
    if len(combined_text) > max_text_length:
        logger.warning(f"텍스트 제한: {len(combined_text)} → {max_text_length}자")
        combined_text = combined_text[:max_text_length] + "\n\n[... truncated ...]"

    difficulty_map = {
        "basic": (
            "**[난이도: 초급 / 입문자용]**\n"
            "- 중학생에게 설명하듯 쉽게 설명\n"
            "- 단순한 비유 사용, 어려운 전문용어 지양\n"
            "- '무엇'과 '왜'에 집중"
        ),
        "intermediate": (
            "**[난이도: 중급 / 대학생 수준]**\n"
            "- 명확한 설명과 기술적 정확성의 균형\n"
            "- 전문용어 사용 가능하되 간단히 설명\n"
            "- 개념 적용에 집중"
        ),
        "advanced": (
            "**[난이도: 고급 / 전문가용]**\n"
            "- 전문가처럼 대화\n"
            "- 뉘앙스와 기술적 세부사항 깊이 있게\n"
            "- 기본 개념은 알고 있다고 가정"
        )
    }
    diff_instruction = difficulty_map.get(difficulty.lower(), difficulty_map["intermediate"])

    length_guide = f"목표 길이: 약 **{budget}자 (±10%)**"

    duration_int = max(1, int(round(duration)))

    if style != "lecture":
        turn_guide = {5: "10~14턴", 10: "18~24턴", 15: "28~32턴"}
        recommended_turns = turn_guide.get(duration_int, f"{duration_int*2}~{duration_int*3}턴")

        length_guide += f"\n- 권장 대화 턴 수: **{recommended_turns}**"
        length_guide += "\n- 선생님:학생 비율 약 7:3 유지"
        length_guide += "\n\n**CRITICAL (ENGLISH FOR PRECISION):**"
        length_guide += "\n- This MUST be a dialogue, NOT a summary"
        length_guide += "\n- Keep turn-by-turn conversation structure"

    instruction_block = (
        "먼저 이 팟캐스트를 위한 간결하고 매력적인 **제목**을 생성하세요.\n"
        f"그 다음 **약 {duration_int}분**짜리 세션에 적합한 스크립트를 작성하세요.\n\n"
        f"{diff_instruction}\n\n"
        "**출력 형식 (매우 중요):**\n"
        "반드시 다음과 같은 유효한 JSON 형식으로 응답하세요:\n"
        "{\n"
        '  "title": "팟캐스트 제목",\n'
        '  "script": "전체 팟캐스트 스크립트를 여기에 직접 작성"\n'
        "}\n\n"
        "**중요 규칙:**\n"
        "- script 필드에는 순수 텍스트만 넣으세요 (JSON 구조 넣지 마세요)\n"
        "- **반드시 유효한 JSON**을 지키세요\n"
        "- script 문자열 안에 실제 줄바꿈(개행)을 넣지 말고, 줄바꿈이 필요하면 **\\\\n** 이스케이프를 사용하세요\n"
        "- 대화형이면 각 턴을 **\\\\n** 으로 구분하세요 (예: [선생님]: ...\\\\n[학생]: ...)\n"
        "- **화자 태그는 반드시 줄 시작에만 사용**: [선생님]: ... / [학생]: ...\n"
        "  (문장 중간에 [학생]님 같은 표기 금지 — 화자 분리 로직이 깨집니다)\n\n"
        f"{length_guide}\n"
        f"- 출력 스크립트는 **최소 {int(budget * 0.90)}자 이상** 작성하세요. (매우 중요)\n"
    )

    if user_prompt and user_prompt.strip():
        instruction_block += f"\n - **사용자 특별 요청:** {user_prompt}\n"

    return user_prompt_template.format(
        combined_text=combined_text,
        host_name=host_name,
        guest_name=guest_name,
        length_instruction=instruction_block,
    )
