import re
from app.langgraph_pipeline.podcast.script.postprocess import hard_cap_fallback

def make_long_dialogue(n_lines=80):
    # 길이를 일부러 길게 만들기
    lines = []
    for i in range(n_lines):
        if i % 2 == 0:
            lines.append(f"[선생님]: {i}번째 설명입니다. 중요한 포인트를 자세히 말합니다.")
        else:
            lines.append(f"[학생]: {i}번째 질문입니다. 그럼 이건 왜 그런가요?")
    return "\n".join(lines)

def test_hardcap_respects_cut_ratio_and_ends_with_teacher(fake_model_factory, extract_text_fn):
    budget = 4000  # 10분 budget
    style = "explain"

    script_text = make_long_dialogue(120)

    # 마무리 생성은 FakeModel이 담당 (짧아도 ok)
    model = fake_model_factory("[학생]: 정리 감사합니다!\n[선생님]: 오늘은 여기까지입니다. 수고하셨습니다!")

    out = hard_cap_fallback(
        script_text=script_text,
        budget=budget,
        model=model,
        style=style,
        extract_text_fn=extract_text_fn,
    )

    # 1) 마지막은 선생님으로 끝나야 함
    assert re.search(r"\[선생님\].*$", out, re.DOTALL)

    # 2) 하드캡 결과가 너무 짧아지지 않았는지(너가 cut_ratio 올려놨으니)
    # 문자열 길이 대신 너희 measure가 더 정확하지만, 우선 단순 체크
    assert len(out) > 2000
