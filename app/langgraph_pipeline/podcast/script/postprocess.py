# app/langgraph_pipeline/podcast/script/postprocess.py
import re
import logging
from typing import Dict
from difflib import SequenceMatcher
from ..utils import estimate_korean_chars_for_budget
from .cleanup import clean_script

logger = logging.getLogger(__name__)

# =========================
# ✅ 스크립트 끊김 감지 함수
# =========================

def is_script_truncated(script: str) -> tuple[bool, str]:
    """
    스크립트가 끊겼는지 확인 (완전성 체크 강화)
    
    Returns:
        (is_truncated, reason)
    """
    script = script.strip()
    
    # 기본 체크
    if not script:
        return True, "빈 스크립트"
    
    # 마지막 줄 확인
    lines = [l for l in script.split('\n') if l.strip()]
    if not lines:
        return True, "유효한 줄 없음"
    
    last_line = lines[-1].strip()
    
    # 1. 화자 태그로 시작하는데 내용 없음
    if last_line.startswith(('「', '[')):
        # 「선생님」: 또는 [선생님]:
        if ':' in last_line:
            content_after_colon = last_line.split(':', 1)[-1].strip()
            if len(content_after_colon) < 10:
                return True, "마지막 발화 내용 없음"
    
    # 2. 문장 부호로 끝나지 않음
    if last_line and not last_line[-1] in '.!?。！？…':
        return True, f"문장 부호 없음: '{last_line[-20:]}'"
    
    # 3. 마지막 발화가 너무 짧음 (화자 태그 제외)
    # 화자 태그 제거 후 길이 체크
    content_only = re.sub(r'^(\[|「)[^\]」]+(\]|」)\s*:\s*', '', last_line)
    if len(content_only) < 50:
        return True, f"마지막 발화 너무 짧음: {len(content_only)}자"
    
    return False, ""


# =========================
# ✅ 비완결성(하드캡/압축/이어쓰기) 꼬리 제거 유틸
# - 예시 꼬리(“이렇게/계속/다음에…”) 나열 방식 X
# - 구조적으로 “마지막 완결 문장까지만” 남김
# =========================

def _split_tag(line: str) -> tuple[str, str]:
    """
    '「선생님」:' 또는 '「학생」:' 태그 분리
    """
    m = re.match(r"^(\[(?:선생님|학생|선생님2)\]:)\s*(.*)$", line.strip())
    if not m:
        return "", line.strip()
    return m.group(1), (m.group(2) or "").strip()


# 선생님 리액션-only(답변 없이 리액션만) 감지: 이건 “예시 꼬리”가 아니라
# ‘답변이 없는 리액션’이라는 구조를 잡는 용도라 안전함.
_TEACHER_REACTION_ONLY_RE = re.compile(
    r"^(오|와|음|아|좋은 질문|좋은 질문이에요|아주 좋은 질문|맞아요|그렇죠|좋아요|"
    r"좋습니다|좋은 포인트|중요한 질문|잘 물어봤어요)[^.!?]*[.!?]?$"
)

def _is_teacher_reaction_only(line: str) -> bool:
    """
    '오 좋은 질문이에요.' 처럼 답이 없는 리액션-only 선생님 라인 감지
    """
    tag, body = _split_tag(line)
    if tag != "「선생님」:":
        return False
    if not body:
        return True
    # 너무 길면 리액션-only 가능성이 낮으므로 짧은 문장에만 적용
    return len(body) <= 60 and bool(_TEACHER_REACTION_ONLY_RE.match(body.strip()))


# 문장 종결로 “자연스럽게 끝난” 것으로 볼 수 있는 기본 패턴(너무 과도하게 확장하지 않음)
# - 마침표/물음표/느낌표 우선
# - 문장부호가 없을 때는 한국어 종결 어미 기반으로 보수적으로 판단
_KO_SENTENCE_END_RE = re.compile(r"(다|요|죠|니다|습니다)\s*$")

def _trim_to_last_terminal(text: str) -> str:
    """
    텍스트에서 '마지막 완결 문장'까지만 남긴다.
    1) 문장부호(.!? )가 있으면: 마지막 .!? 위치까지
    2) 문장부호가 없으면: 종결 어미(다/요/죠/니다/습니다)로 끝날 때만 그대로 유지
       그렇지 않으면 빈 문자열(=완결 문장 없음) 반환
    """
    s = (text or "").strip()
    if not s:
        return ""

    last_p = max(s.rfind("."), s.rfind("!"), s.rfind("?"))
    if last_p != -1:
        return s[: last_p + 1].strip()

    # 문장부호가 없으면 “진짜로 끝난 문장”로 보이는 경우만 유지
    if _KO_SENTENCE_END_RE.search(s):
        return s

    return ""

def _sanitize_trailing_lines(lines: list[str], is_dialogue: bool) -> list[str]:
    """
    끝부분 비완결성 보정(구조 기반):
    - 마지막 줄/마지막 발화에서 “마지막 완결 문장”까지만 남기고,
      완결 문장이 전혀 없으면 그 줄은 제거한다.
    - 대화형:
        * 마지막이 선생님이고 리액션-only면 제거 → 클로징에서 질문 답변+마무리
        * 마지막 선생님 발화는 '완결 문장까지만 trim'
    - 강의형:
        * 마지막 줄은 '완결 문장까지만 trim'
    """
    if not lines:
        return lines

    out = [ln.strip() for ln in lines if ln.strip()]
    if not out:
        return out

    last = out[-1]

    if is_dialogue:
        # 태그 정규화(혹시 「선생님」 형태로 들어오면 「선생님」: 로 맞춤)
        if last.startswith("「선생님」") and "「선생님」:" not in last:
            last = last.replace("「선생님」", "「선생님」:", 1)
        if last.startswith("「학생」") and "「학생」:" not in last:
            last = last.replace("「학생」", "「학생」:", 1)
        if last.startswith("「선생님2」") and "「선생님2」:" not in last:
            last = last.replace("「선생님2」", "「선생님2」:", 1)

        # 마지막이 선생님 발화인 경우에만 처리(문제의 대부분이 여기서 발생)
        if last.startswith("「선생님」:"):
            # 1) 리액션-only면 통째로 제거(답은 클로징이 하게)
            if _is_teacher_reaction_only(last):
                out.pop()
                return out

            # 2) 라인 내부에서 완결 문장까지만 남김
            _, body = _split_tag(last)
            trimmed = _trim_to_last_terminal(body)

            if trimmed:
                out[-1] = f"「선생님」: {trimmed}"
            else:
                # 완결 문장이 전혀 없으면 제거 → 클로징이 답변/정리 담당
                out.pop()

        else:
            # 마지막이 학생 발화면(질문/감상) 그대로 두는 게 보통 더 자연스럽다.
            # (클로징 프롬프트가 질문 답변/마무리를 담당)
            pass

    else:
        # 강의형: 마지막 줄을 완결 문장까지만 남김
        trimmed = _trim_to_last_terminal(last)
        if trimmed:
            out[-1] = trimmed
        else:
            out.pop()

    return out


def get_default_closing(is_dialogue: bool, last_speaker: str = None, speaker_b_label: str = "학생") -> str:
    if is_dialogue:
        if last_speaker == "student" and speaker_b_label == "학생":
            return (
                "「선생님」: 네, 오늘 배운 핵심 내용들을 잘 복습하시면 큰 도움이 될 거예요. "
                "궁금한 점이 있으면 언제든 질문해 주시고, 다음 시간에 또 뵙겠습니다. 수고하셨습니다!"
            )
        return (
            f"「{speaker_b_label}」: 오늘 정말 많은 것을 배웠습니다. 감사합니다!\n"
            "「선생님」: 네, 잘 이해하셨네요. 오늘 배운 내용을 실습해보시면서 더 깊이 있게 공부해 보시기 바랍니다. "
            "다음 시간에 또 뵙겠습니다. 수고하셨습니다!"
        )
    return (
        "「선생님」: 오늘 학습한 내용이 여러분의 이해에 도움이 되었기를 바랍니다. "
        "핵심 개념들을 잘 정리하시고, 실제로 적용해 보면서 학습을 이어가시기 바랍니다. "
        "다음 시간에 뵙겠습니다. 감사합니다!"
    )

def hard_cap_fallback(
    script_text: str,
    budget: int,
    model,
    style: str,
    extract_text_fn,
    speaker_b_label: str = "학생",
) -> str:
    is_dialogue = (style != "lecture")
    # 10분/15분에서 0.75는 너무 공격적이라 컷 비율을 상향
    if budget <= 2200:      # 5분(2000자) 근처
        cut_ratio = 0.90
    elif budget <= 4500:    # 10분(4000자) 근처
        cut_ratio = 0.88
    else:                   # 15분(6000자) 이상
        cut_ratio = 0.85

    # ✅ 엔딩 예산을 강제로 확보해서 클로징이 항상 생성되게 함(복불복 감소)
    closing_reserve = max(220, int(budget * 0.08))
    target_cut = min(int(budget * cut_ratio), max(0, budget - closing_reserve))
    logger.info(f"[하드캡 컷 비율] budget={budget}, cut_ratio={cut_ratio}, target_cut={target_cut}")

    lines = [ln.strip() for ln in script_text.splitlines() if ln.strip()]
    accumulated = ""
    cut_lines = []
    teacher_count = 0
    student_count = 0

    for line in lines:
        test_text = (accumulated + "\n" + line).strip()
        current_len = estimate_korean_chars_for_budget(test_text)

        if re.match(r"^「선생님」", line) or re.match(r"^「선생님2」", line):
            teacher_count += 1
        elif re.match(r"^「학생」", line):
            student_count += 1

        if current_len > target_cut:
            if re.match(r"^「(선생님|선생님2|학생)」", line):
                break
            remaining_budget = target_cut - estimate_korean_chars_for_budget(accumulated)
            if remaining_budget > 50:
                sentences = re.split(r"([.!?]\s+)", line)
                partial = ""
                for sent in sentences:
                    if estimate_korean_chars_for_budget(accumulated + "\n" + partial + sent) <= target_cut:
                        partial += sent
                    else:
                        break
                if partial.strip():
                    cut_lines.append(partial.strip())
            break

        cut_lines.append(line)
        accumulated = test_text

    # ✅ 꼬리 비완결성 보정(특히 '오 좋은 질문이에요'만 남는 케이스 제거)
    
    # ✅ 추가 검증: 마지막 발화가 불완전하면 제거
    if cut_lines:
        last_line = cut_lines[-1].strip()
        
        # 화자 태그 제거
        content_only = re.sub(r'^(\[|「)[^\]」]+(\]|」)\s*:\s*', '', last_line)
        
        # 불완전한 발화 제거 조건
        is_incomplete = False
        
        # 1. 내용이 50자 미만
        if len(content_only) < 50:
            is_incomplete = True
            logger.info(f"[하드캡] 마지막 발화 너무 짧음: {len(content_only)}자 → 제거")
        
        # 2. 문장 부호로 끝나지 않음
        elif content_only and not content_only[-1] in '.!?。！？…':
            is_incomplete = True
            logger.info(f"[하드캡] 마지막 발화 불완전: '{content_only[-20:]}' → 제거")
        
        if is_incomplete:
            cut_lines = cut_lines[:-1]
    
    cut_lines = _sanitize_trailing_lines(cut_lines, is_dialogue=is_dialogue)
    truncated = "\n".join(cut_lines).strip()
    truncated_len = estimate_korean_chars_for_budget(truncated)

    last_speaker = None
    if is_dialogue:
        for line in reversed(cut_lines):
            if re.match(r"^「선생님」", line) or re.match(r"^「선생님2」", line):
                last_speaker = "teacher"
                break
            if re.match(r"^「학생」", line):
                last_speaker = "student"
                break
        logger.info(f"[하드캡] {truncated_len}자 / 선생님:{teacher_count} / 학생:{student_count} / 마지막:{last_speaker}")

    # ✅ 마지막 발화(질문 가능성) 추출: 물음표 없어도 잡아서 클로징에서 답변 유도
    last_b_q = None
    if is_dialogue:
        for line in reversed(cut_lines):
            if line.startswith(f"「{speaker_b_label}」"):
                # 너무 짧은 맞장구는 제외
                normalized = line
                if f"「{speaker_b_label}」:" not in normalized and normalized.startswith(f"「{speaker_b_label}」"):
                    normalized = normalized.replace(f"「{speaker_b_label}」", f"「{speaker_b_label}」:", 1)
                _, body = _split_tag(normalized)
                if len(body) >= 8:
                    last_b_q = line.strip()
                    break

    remaining_budget = max(0, budget - truncated_len)

    # ✅ 전체 내용 요약 생성 (클로징 품질 향상)
    summary = ""
    if is_dialogue and truncated_len > 1000:
        summary_prompt = f"""
다음 팟캐스트 대화의 핵심 내용을 2-3문장으로 간단히 요약하세요.
주요 개념과 결론만 포함하세요.

[대화 전체]
{truncated}

[핵심 요약 (2-3문장)]
""".strip()
        try:
            summary_resp = model.generate_content(
                summary_prompt,
                generation_config={"max_output_tokens": 512, "temperature": 0.2}
            )
            summary = extract_text_fn(summary_resp).strip()
            logger.info(f"[하드캡] 전체 요약 생성 ({len(summary)}자)")
        except Exception as e:
            logger.warning(f"[하드캡] 요약 생성 실패: {e}")
            summary = ""


    if is_dialogue:
        closing_prompt = f"""
    다음은 대화형 팟캐스트의 일부입니다. 이 대화를 자연스럽고 완결되게 마무리하세요.

    **CRITICAL - 화자 태그 규칙 (매우 중요):**
    - 반드시 각 줄 시작에 「선생님」: 또는 「{speaker_b_label}」: 태그 사용
    - "진행자", "청취자", "호스트", "게스트" 같은 표현 절대 금지
    - 태그 형식: 「선생님」: ... 또는 「{speaker_b_label}」: ...
    - 다른 형식 사용 시 오류 발생

    **내용 규칙:**
    - 남은 예산: {remaining_budget}자 (±20%)
    - 대화 형식 유지
    - 첫 줄은 반드시 「선생님」: 으로 시작
    - (아래에 학생 질문이 있으면) 반드시 그 질문에 대한 답변으로 시작
    - 마지막 학생 질문이 존재하면, 반드시 「선생님」: 으로 그 질문에 대한 '직접적인 답'을 2~4문장으로 먼저 작성
    - 마지막은 반드시 「선생님」이 격려+인사로 끝내기

    **올바른 예시:**
    「{speaker_b_label}」: 오늘 정말 유익했습니다!
    「선생님」: 네, 잘 이해하셨네요. 다음 시간에 뵙겠습니다!

    **잘못된 예시 (절대 금지):**
    청취자: 감사합니다
    진행자: 다음에 또 만나요
    """.strip()

        
        if last_b_q:
            closing_prompt += f"""

    **마지막 질문(반드시 먼저 답변할 것):**
    {last_b_q}
    """.strip()

        closing_prompt += f"""

    **전체 내용 요약:**
    {summary if summary else "(요약 없음 - 마지막 부분만 참고)"}

    [참고: 마지막 대화]
    {truncated[-800:]}

    **마무리 요구사항:**
    - 전체 요약을 언급하며 핵심 정리
    - 마지막 질문이 있으면 반드시 답변
    - 격려 + 인사로 종료
    - 반드시 「선생님」이 마지막 발화

    [마무리 생성 - 반드시 「선생님」: 또는 「{speaker_b_label}」: 태그 사용]
    """.strip()

    else:
        closing_prompt = f"""
다음은 강의의 일부입니다. 강의를 자연스럽게 완결하세요.

- 남은 예산: {remaining_budget}자 (±20%)
- 반드시 '「선생님」:' 형식 유지

[참고: 마지막 부분]
{truncated[-800:]}

[마무리 생성]
"""

    try:
        resp = model.generate_content(
            closing_prompt,
            generation_config={"max_output_tokens": min(2048, max(256, remaining_budget * 3)), "temperature": 0.2},
        )
        closing = clean_script(extract_text_fn(resp))

        if estimate_korean_chars_for_budget(closing) < 80:
            closing = get_default_closing(is_dialogue, last_speaker if is_dialogue else None, speaker_b_label=speaker_b_label)

        # 대화형이면 선생님으로 끝나는지 보정
        if is_dialogue and not re.search(r"「선생님」[^\[]*$", closing, re.DOTALL):
            closing = closing.rstrip() + "\n「선생님」: 오늘 배운 내용을 잘 복습하시고, 다음 시간에 또 뵙겠습니다. 수고하셨습니다!"

        return (truncated + "\n" + closing).strip()

    except Exception as e:
        logger.error(f"[하드캡] 마무리 생성 오류: {e}")
        return (truncated + "\n" + get_default_closing(is_dialogue, last_speaker if is_dialogue else None, speaker_b_label=speaker_b_label)).strip()

def continue_script_fallback(
    script_text: str,
    budget: int,
    model,
    style: str,
    extract_text_fn,
    speaker_b_label: str = "학생",
) -> str:
    is_dialogue = (style != "lecture")
    current_len = estimate_korean_chars_for_budget(script_text)
    
    # ✅ 개선: 120% 여유 + 최소 200자 보장
    # - budget * 1.2가 존치 최대치 (120%)
    # - 최소 200자는 보장하여 이어쓰기 실패 방지
    remaining_budget = max(200, int(budget * 1.2) - current_len)
    
    logger.info(f"[이어쓰기 예산] 현재: {current_len}자, 목표: {budget}자, 할당: {remaining_budget}자 (120% 여유)")

    if remaining_budget < 200:
        # ✅ 남은 예산이 적을수록 "미완 꼬리 + 클로징"이 되기 쉬움 → 꼬리 정리 후 클로징
        lines = [ln.strip() for ln in script_text.splitlines() if ln.strip()]
        lines = _sanitize_trailing_lines(lines, is_dialogue=is_dialogue)
        base = "\n".join(lines).strip()
        return (base + "\n" + get_default_closing(is_dialogue, speaker_b_label=speaker_b_label)).strip()
    if is_dialogue:
        prompt = f"""
다음은 대화형 팟캐스트 스크립트입니다. 

**중요: 먼저 현재 상태를 확인하세요**
1. 스크립트 마지막을 보고 이미 마무리 인사(감사합니다, 수고하셨습니다 등)가 있는지 확인
2. 있다면 → "ALREADY_COMPLETE" 만 출력하고 아무것도 추가하지 마세요
3. 없다면 → 자연스럽게 내용을 이어가고 마무리하세요

**이어쓰기 규칙 (마무리가 없는 경우에만):**
- 대화 형식 유지
- 화자 태그는 줄 시작에만: 「선생님」: / 「{speaker_b_label}」:
- 문장 중간에 「학생」님 금지
- teacher-student일 때만 선생님:학생 비율 7:3 근사 (teacher-teacher면 적용하지 않음)
- 추가 분량은 약 {remaining_budget}자 이내 (±20%)
- **마무리 인사를 중복하지 마세요**

[현재 마지막 부분]
{script_text[-1200:]}

[출력]
"""
    else:
        prompt = f"""
다음은 강의형 스크립트입니다.

**중요: 먼저 현재 상태를 확인하세요**
1. 스크립트 마지막을 보고 이미 마무리 인사가 있는지 확인
2. 있다면 → "ALREADY_COMPLETE" 만 출력
3. 없다면 → 자연스럽게 이어서 마무리하세요

**이어쓰기 규칙:**
- 반드시 「선생님」: 형식 유지
- 추가 분량은 약 {remaining_budget}자 이내 (±20%)

[현재 마지막 부분]
{script_text[-1200:]}

[출력]
"""

    try:
        resp = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": min(4096, max(512, remaining_budget * 3)), "temperature": 0.2},
        )
        cont = clean_script(extract_text_fn(resp))

        # ✅ LLM이 이미 완결로 판단한 경우
        if "ALREADY_COMPLETE" in cont[:100].upper():
            logger.info("[이어쓰기 스킵] LLM이 스크립트가 이미 완결되었다고 판단")
            # 혹시 꼬리가 미완이면 한 번 정리
            lines = [ln.strip() for ln in script_text.splitlines() if ln.strip()]
            lines = _sanitize_trailing_lines(lines, is_dialogue=is_dialogue)
            return "\n".join(lines).strip()

        if estimate_korean_chars_for_budget(cont) < 120:
            cont = get_default_closing(is_dialogue, speaker_b_label=speaker_b_label)

        
        # ✅ 중복 내용 체크 (스크립트 마지막과 이어쓰기 시작 비교)
        if cont and len(cont) > 50:
            # 스크립트 마지막 150자
            last_150 = script_text.strip()[-150:]
            # 이어쓰기 시작 150자
            cont_150 = cont.strip()[:150]
            
            # 유사도 계산
            similarity = SequenceMatcher(None, last_150, cont_150).ratio()
            
            if similarity > 0.7:
                logger.warning(f"⚠️  이어쓰기 중복 감지 (유사도: {similarity:.1%})")
                logger.warning(f"   스크립트 마지막: {last_150[:50]}...")
                logger.warning(f"   이어쓰기 시작: {cont_150[:50]}...")
                logger.warning(f"   → 중복 부분 제거")
                
                # 중복 부분 찾아서 제거 (첫 100자 스킵)
                cont = cont[100:] if len(cont) > 100 else cont
        
        return (script_text.rstrip() + "\n" + cont.lstrip()).strip()

    except Exception as e:
        logger.error(f"[이어쓰기 폴백] 오류: {e}")
        return (script_text + "\n" + get_default_closing(is_dialogue, speaker_b_label=speaker_b_label)).strip()

def expand_script_fallback(
    *,
    script_text: str,
    budget: int,
    min_chars: int,
    model,
    style: str,
    extract_text_fn,
    max_add_chars: int = 2200,
    speaker_b_label: str = "학생",
) -> str:
    """
    부족한 분량을 '한 번에' 확장하는 보강 루틴.
    - 단순 이어쓰기가 아닌 내용 확장 전략
    - 호출 1회로 큰 폭을 채우는 용도
    """
    from ..utils import estimate_korean_chars_for_budget
    
    current = estimate_korean_chars_for_budget(script_text)
    need = max(0, min_chars - current)
    need = min(need, max_add_chars)

    if need <= 0:
        return script_text

    is_dialogue = (style != "lecture")

    if is_dialogue:
        prompt = f"""\
당신은 팟캐스트 스크립트 편집자입니다.

**임무**: 아래 대화형 스크립트의 본론 부분을 확장하여 **약 {need}자**를 추가하세요.

**중요 전략**:
1. 마무리 인사는 절대 추가하지 마세요 (이미 존재함)
2. **본론 중간**에 내용을 자연스럽게 삽입:
   - 더 자세한 설명
   - 구체적인 예시 추가
   - 학생의 추가 질문과 선생님의 답변
   - 비유나 실생활 적용 사례

**규칙**:
- 대화 형식 유지: 「선생님」/「{speaker_b_label}」
- teacher-student일 때만 선생님:학생 비율 7:3 (teacher-teacher면 적용하지 않음)
- 논리적 흐름 유지
- **기존 마무리는 그대로 유지** (마무리를 다시 작성하지 마세요)

[현재 스크립트]
{script_text}

[확장된 스크립트 전체를 출력 - 본론은 풍부하게, 마무리는 그대로]
"""
    else:
        prompt = f"""\
당신은 팟캐스트 스크립트 편집자입니다.

**임무**: 아래 강의형 스크립트를 확장하여 **약 {need}자**를 추가하세요.

**중요 전략**:
1. 마무리 인사는 절대 추가하지 마세요
2. 본론 중간에 내용을 자연스럽게 삽입:
   - 더 자세한 설명
   - 구체적인 예시
   - 심화 내용

**규칙**:
- 「선생님」: 형식 유지
- 논리적 흐름 유지
- 기존 마무리는 그대로 유지

[현재 스크립트]
{script_text}

[확장된 스크립트 전체를 출력]
"""

    try:
        resp = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": min(6144, max(2048, (current + need) * 3)),
                "temperature": 0.3
            }
        )
        expanded = clean_script(extract_text_fn(resp))

        if not expanded or estimate_korean_chars_for_budget(expanded) < current:
            logger.warning("[확장 실패] 원본보다 짧거나 빈 결과 → 원본 유지")
            return script_text

        # 혹시 마무리 키워드가 중복되었다면 경고
        closing_count = len(re.findall(r'(감사합니다|수고하셨습니다)', expanded))
        if closing_count > 2:
            logger.warning(f"[확장 결과] 마무리 키워드 {closing_count}회 출현 - 중복 가능성")

        return expanded

    except Exception as e:
        logger.error(f"[확장 폴백] 오류: {e}")
        return script_text
    
def expand_middle_content(
    script_text: str,
    budget: int,
    current_len: int,
    structure: Dict,
    model,
    style: str,
    extract_text_fn,
    speaker_b_label: str = "학생",
) -> str:
    """
    마무리는 유지하고 중간 본론 부분만 확장
    
    전략:
    1. 스크립트를 [도입 + 본론 + 마무리]로 분리
    2. 본론 부분에 추가 내용 삽입
    3. 마무리는 그대로 유지
    """
    from ..utils import estimate_korean_chars_for_budget
    from .cleanup import clean_script
    
    is_dialogue = (style != "lecture")
    lines = [l.strip() for l in script_text.strip().split('\n') if l.strip()]
    
    closing_idx = structure['closing_start_idx']
    
    # 마무리가 너무 빨리 시작되면 (전체의 50% 이전) 구조가 이상함
    if closing_idx < len(lines) * 0.5:
        logger.warning(f"[중간 확장 스킵] 마무리가 너무 이른 위치({closing_idx}/{len(lines)})")
        return script_text
    
    # 분리
    intro_and_main = '\n'.join(lines[:closing_idx])
    closing = '\n'.join(lines[closing_idx:])
    
    need = budget - current_len
    
    if is_dialogue:
        prompt = f"""
당신은 팟캐스트 편집자입니다.

**임무**: 아래 본론 부분을 확장하여 **약 {need}자**를 추가하세요.

**중요**:
1. 마무리 인사는 절대 추가하지 마세요 (별도로 제공됨)
2. 본론에 자연스럽게 내용 추가:
   - 더 자세한 설명
   - 추가 예시
   - 학생의 심화 질문과 선생님의 답변

**규칙**:
- 대화 형식 유지: 「선생님」/「{speaker_b_label}」
- 논리적 흐름 유지
- teacher-student일 때만 선생님:학생 비율 7:3 (teacher-teacher면 적용하지 않음)

[확장할 본론 부분]
{intro_and_main}

[확장된 본론만 출력 - 마무리 인사 절대 금지]
"""
    else:
        prompt = f"""
당신은 팟캐스트 편집자입니다.

**임무**: 아래 본론을 확장하여 **약 {need}자**를 추가하세요.

**중요**:
1. 마무리 인사는 절대 추가하지 마세요
2. 본론에 내용 추가: 더 자세한 설명, 예시 등

**규칙**:
- 「선생님」: 형식 유지
- 논리적 흐름 유지

[확장할 본론]
{intro_and_main}

[확장된 본론만 출력]
"""
    
    try:
        resp = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": min(6144, need * 4),
                "temperature": 0.3
            }
        )
        
        expansion = clean_script(extract_text_fn(resp))
        
        # 혹시 마무리 키워드가 포함되었다면 제거
        closing_patterns = r'(감사합니다|수고하셨습니다|다음\s*시간|여기서\s*마치|안녕).*$'
        expansion = re.sub(closing_patterns, '', expansion, flags=re.DOTALL).strip()
        
        # 재조립
        expanded_script = f"{expansion}\n{closing}".strip()
        
        expanded_len = estimate_korean_chars_for_budget(expanded_script)
        logger.info(f"[중간 확장 완료] {current_len}자 → {expanded_len}자")
        
        return expanded_script
        
    except Exception as e:
        logger.error(f"[중간 확장 실패] {e}")
        return script_text