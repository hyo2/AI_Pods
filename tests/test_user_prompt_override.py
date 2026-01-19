from app.langgraph_pipeline.podcast.script.options_parser import parse_user_prompt_overrides, apply_overrides

def test_duration_override():
    ov = parse_user_prompt_overrides("15분으로 해줘")
    assert ov["duration"] == 15

def test_style_override():
    ov = parse_user_prompt_overrides("강의형으로")
    assert ov["style"] == "lecture"

def test_apply_overrides_priority():
    ov = parse_user_prompt_overrides("15분 대화형 중급으로")
    d, s, diff = apply_overrides(10, "lecture", "basic", ov)
    assert d == 15
    assert s == "explain"
    assert diff == "intermediate"
