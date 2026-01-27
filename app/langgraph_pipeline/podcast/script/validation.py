# app/langgraph_pipeline/podcast/script/validation.py
import re
from typing import Tuple
from ..utils import estimate_korean_chars_for_budget

def measure(text: str) -> int:
    return estimate_korean_chars_for_budget(text)

def is_script_truncated(script_text: str) -> Tuple[bool, str]:
    """스크립트가 중간에 끊긴 것처럼 보이는지 감지"""
    if not script_text or len(script_text.strip()) < 80:
        return True, "too_short_or_empty"

    lines = [ln.strip() for ln in script_text.splitlines() if ln.strip()]
    if not lines:
        return True, "no_lines"

    last = lines[-1]
    last_wo_speaker = re.sub(r"^「(선생님|학생|선생님2)」\s*:?\s*", "", last).strip()

    if len(last_wo_speaker) < 10:
        return True, "last_line_too_short"

    if not re.search(r"[.!?…。!?]$", last_wo_speaker):
        return True, "no_terminal_punctuation"

    if last_wo_speaker.count("(") != last_wo_speaker.count(")"):
        return True, "unbalanced_parentheses"

    return False, "ok"