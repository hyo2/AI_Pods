# app/langgraph_pipeline/podcast/script/compression.py
import logging
from ..utils import estimate_korean_chars_for_budget

logger = logging.getLogger(__name__)

# ✅ 개선된 압축 프롬프트 (대화 구조 유지 강조!)
COMPRESS_PROMPT_TEMPLATE = """\
You are a professional podcast script editor.

**Task:**
Shorten the dialogue script from {original_len} to approximately {budget} Korean characters ({tolerance}).

**CRITICAL - How to compress:**
1. Keep ALL dialogue turns (do NOT reduce turn count)
2. Keep opening greeting and closing farewell
3. Make EACH turn shorter by:
   - Removing redundant explanations
   - Using simpler vocabulary
   - Cutting filler phrases (그러니까, 뭐, 사실, 등등)
4. Preserve natural conversation flow

**Style-specific rules:**
{style_rules}

**Target length:**
- Approximately {budget} Korean characters ({tolerance})
- {priority_note}

**Output requirements:**
- MUST be primarily in Korean
- English is ONLY allowed when it's the subject of learning
- Keep the SAME number of dialogue turns
- Each turn should just be shorter

**Example of what to do:**
BEFORE (long):
「선생님」: 그러니까 말이죠, 수용성 성분이라는 것은 사실 물에 잘 녹는 성질을 가진 성분들을 말하는 거예요. 예를 들면 비타민 C 같은 것들이 여기에 속하죠.

AFTER (short):
「선생님」: 수용성 성분은 물에 녹는 비타민 C 같은 성분이에요.

**What NOT to do:**
❌ DO NOT convert dialogue to summary
❌ DO NOT reduce number of turns
❌ DO NOT remove speaker tags

[ORIGINAL SCRIPT - {original_len} characters]
{script_text}

[YOUR SHORTENED SCRIPT - Target: {budget} Korean characters]
"""

def compress_script_once(
    model,
    extract_text_fn,
    script_text: str,
    budget: int,
    is_dialogue: bool,
    round_idx: int = 0,
    speaker_a_label: str = "선생님",
    speaker_b_label: str = "학생",
) -> str:
    original_len = estimate_korean_chars_for_budget(script_text)

    # ✅ 압축 비율이 너무 크면 포기 (80% 이상 압축 요구 시)
    compression_ratio = budget / original_len
    if compression_ratio < 0.2:
        logger.warning(f"[압축 스킵] 압축 비율 너무 극단적: {compression_ratio:.1%} (20% 미만)")
        return script_text

    if not is_dialogue:
        style_rules = (
            "- Speaker tag: Use ONLY '「선생님」' at the start of EVERY line\n"
            "- Do NOT use any other labels\n"
            "- Keep structure: engaging opening → key points → clear summary\n"
        )
        tolerance = "±8%"
        priority_note = "Both length compliance and content completeness are important"
    else:
        style_rules = (
            "- MUST maintain dialogue format (DO NOT convert to summary/prose)\n"
            f"- Speaker tags: Use ONLY '「{speaker_a_label}」' and '「{speaker_b_label}」'\n"
        )
        if speaker_b_label == "학생":
            style_rules += "- Maintain approximately 7:3 (Teacher:Student) ratio\n"
        else:
            style_rules += "- Two teachers conversation (NO student role)\n"
        style_rules += (
            "- Last 2 turns MUST be summary + closing\n"
            "- Keep SAME number of turns, make EACH turn shorter\n"
        )
        if round_idx >= 1:
            style_rules += (
                "\nEXTRA CRITICAL:\n"
                "- You MUST keep the SAME number of dialogue turns\n"
                "- Just make EACH turn use fewer words\n"
            )
        tolerance = "±10%"
        priority_note = "Dialogue structure preservation is MORE important than exact length"

    prompt = COMPRESS_PROMPT_TEMPLATE.format(
        style_rules=style_rules,
        budget=budget,
        tolerance=tolerance,
        priority_note=priority_note,
        script_text=script_text,
        original_len=original_len,
    )

    # ✅ Temperature 상향 (0.3~0.4로 창의성 확보)
    generation_config = {
        "max_output_tokens": 6144,
        "temperature": 0.3 if round_idx >= 2 else 0.4,
    }

    # ✅ 디버깅: 원본 정보 출력
    original_lines = [l.strip() for l in script_text.strip().split('\n') if l.strip()]
    original_turns = len([l for l in original_lines if '「' in l and '」' in l])
    
    logger.info("=" * 80)
    logger.info(f"[압축 시작] Round {round_idx + 1}")
    logger.info(f"  원본: {original_len}자, {original_turns}턴")
    logger.info(f"  목표: {budget}자 (압축률: {budget/original_len:.1%})")
    logger.info(f"  Temperature: {generation_config['temperature']}")
    logger.info("  원본 앞부분:")
    for i, line in enumerate(original_lines[:5]):
        logger.info(f"    {i+1}. {line[:80]}...")
    logger.info("=" * 80)

    try:
        resp = model.generate_content(prompt, generation_config=generation_config)
        compressed = extract_text_fn(resp).strip()
        
        # ✅ 디버깅: 압축 결과 출력
        if compressed:
            compressed_lines = [l.strip() for l in compressed.strip().split('\n') if l.strip()]
            compressed_turns = len([l for l in compressed_lines if '「' in l and '」' in l])
            
            logger.info("=" * 80)
            logger.info(f"[압축 결과]")
            logger.info(f"  결과: {len(compressed)}자, {compressed_turns}턴")
            logger.info(f"  턴 수 변화: {original_turns} → {compressed_turns}")
            logger.info("  결과 앞부분:")
            for i, line in enumerate(compressed_lines[:5]):
                logger.info(f"    {i+1}. {line[:80]}...")
            logger.info("=" * 80)

        if not compressed:
            logger.warning("[압축] 빈 결과 반환")
            return script_text

        compressed_len = estimate_korean_chars_for_budget(compressed)

        # ✅ 압축 실패 조건 완화 (원본의 85% 이하면 실패)
        if compressed_len > original_len * 0.85:
            logger.warning(f"[압축 실패] 충분히 줄지 않음: {original_len} → {compressed_len}")
            return script_text

        # ✅ 과도 압축 기준 완화 (50% → 40%)
        if compressed_len < int(budget * 0.40):
            logger.warning("=" * 80)
            logger.warning(f"[압축 실패] 과도하게 짧음: {compressed_len}자 (목표: {budget}자)")
            logger.warning(f"  압축률: {compressed_len/original_len:.1%} (원본 대비)")
            logger.warning(f"  목표 대비: {compressed_len/budget:.1%}")
            logger.warning(f"  턴 수: {original_turns} → {compressed_turns}")
            logger.warning("=" * 80)
            
        # ✅ 극단적으로 짧으면 (300자 미만) 즉시 포기
            if compressed_len < 300:
                logger.error("=" * 80)
                logger.error(f"[압축 포기] 결과가 너무 짧음 ({compressed_len}자) - 요약으로 변질됨")
                logger.error(f"  원본 턴수: {original_turns}, 결과 턴수: {compressed_turns}")
                logger.error("  실제 생성된 내용 (전체):")
                for i, line in enumerate(compressed_lines[:15]):  # 최대 15줄
                    logger.error(f"    {i+1}. {line}")
                logger.error("  프롬프트 핵심 부분:")
                prompt_lines = prompt.split('\n')
                for line in prompt_lines:
                    if 'Keep ALL' in line or 'SAME number' in line or 'Example' in line:
                        logger.error(f"    > {line}")
                logger.error("=" * 80)
                return script_text
            
            # 300~40% 사이면 재시도 가능성 있음
            return script_text

        # ✅ 성공 범위 확대 (40%~150%)
        success_min = int(budget * 0.40)
        success_max = int(budget * 1.50)
        
        if success_min <= compressed_len <= success_max:
            logger.info(f"[압축 성공] {original_len} → {compressed_len}자 (목표: {budget}자)")
            return compressed
        else:
            logger.warning(f"[압축 실패] 범위 벗어남: {compressed_len}자 (허용: {success_min}~{success_max}자)")
            return script_text

    except Exception as e:
        logger.warning(f"[압축 실패] {e}")
        return script_text