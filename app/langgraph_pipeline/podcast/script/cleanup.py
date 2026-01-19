# app/langgraph_pipeline/podcast/script/cleanup.py
import re

def clean_script(script_text: str) -> str:
    """스크립트 텍스트 정리"""
    if not script_text:
        return ""

    script_text = re.sub(
        r"```python|```json|```text|```markdown|```",
        "",
        script_text,
        flags=re.IGNORECASE
    )
    script_text = re.sub(r"[\U00010000-\U0010ffff]", "", script_text)

    # \n 이스케이프 복구
    script_text = script_text.replace("\\r\\n", "\n").replace("\\n", "\n")
    script_text = script_text.replace("\\t", " ")

    # '?n', '!n' 찌꺼기 제거
    script_text = re.sub(r"([.!?])n(\s|$)", r"\1\2", script_text)

    script_text = re.sub(r"\n{3,}", "\n\n", script_text)
    script_text = re.sub(r"\n+$", "", script_text)

    return script_text.strip()
