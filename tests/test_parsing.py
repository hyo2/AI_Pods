from app.langgraph_pipeline.podcast.script.parsing import extract_json_from_llm

def test_extract_json_from_fenced_block():
    raw = """```json
{"title":"t","script":"[선생님]: a\\n[학생]: b"}
```"""
    data = extract_json_from_llm(raw)
    assert data["title"] == "t"
    assert "script" in data

def test_extract_json_from_loose_text():
    raw = 'blah blah {"title":"t2","script":"x"} trailing'
    data = extract_json_from_llm(raw)
    assert data["title"] == "t2"
