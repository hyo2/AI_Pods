from app.langgraph_pipeline.podcast.script.validation import is_script_truncated

def test_truncated_when_no_punct():
    text = "[선생님]: 안녕하세요\n[학생]: 네\n[선생님]: 그래서 결론은"
    bad, reason = is_script_truncated(text)
    assert bad is True

def test_ok_when_ends_properly():
    text = "[선생님]: 안녕하세요.\n[학생]: 네!\n[선생님]: 오늘은 여기까지입니다. 감사합니다!"
    bad, reason = is_script_truncated(text)
    assert bad is False
