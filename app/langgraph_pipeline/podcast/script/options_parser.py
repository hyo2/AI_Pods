import re
from typing import Optional, Dict, Any, List, Set

STYLE_ALIASES = {
    "lecture": [r"강의형", r"단독", r"선생님만", r"lecture"],
    "explain": [r"대화형", r"대화", r"설명형", r"문답", r"explain", r"dialogue"],
}

DLG_MODE_ALIASES = {
    "teacher_teacher": [
        r"선생님\s*끼리", r"교사\s*끼리",
        r"선생님\s*들", r"교사\s*들",
        r"선생님\s*들\s*끼리", r"교사\s*들\s*끼리",
        r"선생님\s*두\s*명", r"교사\s*두\s*명",
        r"두\s*선생님", r"두\s*교사",
        r"teacher\s*[- ]?\s*teacher",
        r"선생님\s*2", r"선생님2",
    ],
}


DIFF_ALIASES = {
    "basic": [r"초급", r"입문", r"쉽게", r"easy", r"beginner"],
    "intermediate": [r"중급", r"보통", r"intermediate"],
    "advanced": [r"고급", r"심화", r"전문가", r"advanced", r"expert"],
}

def _parse_duration_minutes(text: str) -> Optional[float]:
    t = text.strip()

    m = re.search(r"\b(\d{1,2})\s*:\s*(\d{1,2})\b", t)
    if m:
        mm = int(m.group(1))
        ss = int(m.group(2))
        return mm + ss / 60.0

    m = re.search(r"(\d+(?:\.\d+)?)\s*분(?:\s*(\d+(?:\.\d+)?)\s*초)?", t)
    if m:
        minutes = float(m.group(1))
        seconds = float(m.group(2)) if m.group(2) else 0.0
        return minutes + seconds / 60.0

    m = re.search(r"(\d+(?:\.\d+)?)\s*초", t)
    if m:
        seconds = float(m.group(1))
        return seconds / 60.0

    return None


def _parse_page_numbers(text: str, max_pages: int = 10000) -> List[int]:
    """
    사용자 프롬프트에서 페이지 번호/범위를 파싱.
    지원 예:
      - '12페이지', '페이지 12', 'p.12', '12p'
      - '12~15페이지', '12-15p', 'p12~p15'
    """
    t = text.lower()
    pages: Set[int] = set()

    # 범위: 12~15, 12-15
    for m in re.finditer(r"(?:p\.?\s*)?(\d{1,4})\s*(?:~|-)\s*(?:p\.?\s*)?(\d{1,4})\s*(?:페이지|p)?", t):
        a = int(m.group(1))
        b = int(m.group(2))
        if 1 <= a <= max_pages and 1 <= b <= max_pages:
            lo, hi = (a, b) if a <= b else (b, a)
            for x in range(lo, hi + 1):
                pages.add(x)

    # 단일: 12페이지 / 페이지 12 / p.12 / 12p
    for m in re.finditer(r"(?:페이지\s*)?(\d{1,4})\s*(?:페이지|p)\b", t):
        x = int(m.group(1))
        if 1 <= x <= max_pages:
            pages.add(x)

    for m in re.finditer(r"\bp\.?\s*(\d{1,4})\b", t):
        x = int(m.group(1))
        if 1 <= x <= max_pages:
            pages.add(x)

    return sorted(pages)


def parse_user_prompt_overrides(user_prompt: str) -> Dict[str, Any]:
    if not user_prompt or not user_prompt.strip():
        return {"duration_min": None, "style": None, "difficulty": None, "ocr_force_pages": [], "dialogue_mode": None}

    text = user_prompt.strip()

    duration_min = _parse_duration_minutes(text)

    style = None
    for key, patterns in STYLE_ALIASES.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            style = key
            break

    difficulty = None
    for key, patterns in DIFF_ALIASES.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            difficulty = key
            break

    # ✅ 추가: OCR 강제 페이지 파싱
    ocr_force_pages = _parse_page_numbers(text)

    dialogue_mode = None
    for key, patterns in DLG_MODE_ALIASES.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            dialogue_mode = key
            break


    return {
        "duration_min": duration_min,
        "style": style,
        "difficulty": difficulty,
        "ocr_force_pages": ocr_force_pages,
        "dialogue_mode": dialogue_mode,
    }


def apply_overrides(duration_min: float, style: str, difficulty: str, overrides: Dict[str, Any]):
    new_duration_min = float(overrides["duration_min"]) if overrides.get("duration_min") else duration_min
    new_style = str(overrides["style"]) if overrides.get("style") else style
    new_difficulty = str(overrides["difficulty"]) if overrides.get("difficulty") else difficulty
    # ocr_force_pages는 graph/state로 넘기는 값이라 여기서는 그대로 둠
    return new_duration_min, new_style, new_difficulty
