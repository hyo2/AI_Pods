# app/langgraph_pipeline/podcast/script/compression.py
import logging
from ..utils import estimate_korean_chars_for_budget

logger = logging.getLogger(__name__)

COMPRESS_PROMPT_TEMPLATE = """\
You are a professional script editor.

**Task:**
Rewrite the script to be approximately {budget} Korean characters (tolerance: {tolerance}).
The original script is {original_len} characters. Your output MUST be SHORTER.

**Style-specific rules:**
{style_rules}

**Target length:**
- Approximately {budget} Korean characters ({tolerance})
- {priority_note}

**Output requirements:**
- MUST be primarily in Korean
- English is ONLY allowed when it's the subject of learning, and must be explained in Korean
- DO NOT switch the entire script to English

**CRITICAL:**
- Make the script SHORTER than the original ({original_len} chars)
- This is a LENGTH REDUCTION rewrite, NOT an expansion
- Keep the same style (dialogue/lecture) as the original

[ORIGINAL SCRIPT - {original_len} characters]
{script_text}

[YOUR REWRITTEN SCRIPT - Target: around {budget} Korean characters]
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

    if not is_dialogue:
        style_rules = (
            "- Speaker tag: Use ONLY '[선생님]' at the start of EVERY line\n"
            "- Do NOT use any other labels\n"
            "- Keep structure: engaging opening → key points → clear summary\n"
        )
        tolerance = "±8%"
        priority_note = "Both length compliance and content completeness are important"
    else:
        style_rules = (
            "- MUST maintain dialogue format (DO NOT convert to summary/prose)\n"
            f"- Speaker tags: Use ONLY '[{speaker_a_label}]' and '[{speaker_b_label}]'\n"
         )
        if speaker_b_label == "학생":
            style_rules += "- Maintain approximately 7:3 (Teacher:Student) ratio\n"
        else:
            style_rules += "- Two teachers conversation (NO student role)\n"
        style_rules += (
            "- Last 2 turns MUST be summary + closing\n"
            "- Keep similar number of turns, make each turn SHORTER\n"
        )
        if round_idx >= 1:
            style_rules += (
                "\nEXTRA CRITICAL:\n"
                "- Maintain dialogue turn count (do NOT collapse into 3-4 turns)\n"
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

    generation_config = {
        "max_output_tokens": 6144,
        "temperature": 0.1 if round_idx >= 2 else 0.2,
    }

    try:
        resp = model.generate_content(prompt, generation_config=generation_config)
        compressed = extract_text_fn(resp).strip()

        if not compressed:
            logger.warning("[압축] 빈 결과 반환")
            return script_text

        compressed_len = estimate_korean_chars_for_budget(compressed)

        if compressed_len > original_len * 0.95:
            logger.warning(f"[압축 실패] 충분히 줄지 않음: {original_len} → {compressed_len}")
            return script_text

        if compressed_len < int(budget * 0.65):
            logger.warning(f"[압축 실패] 과도하게 짧음: {compressed_len}자")
            return script_text

        logger.info(f"[압축 성공] {original_len} → {compressed_len}자")
        return compressed

    except Exception as e:
        logger.warning(f"[압축 실패] {e}")
        return script_text
