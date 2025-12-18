from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parent.parent
# parent       -> app/
# parent.parent -> backend/

text_path = BASE_DIR / "outputs" / "팟캐스트 소개 및 주제 제시_script.txt"

text = text_path.read_text(encoding="utf-8")

# [00:00:00] 형태 제거
text = re.sub(r"\[\d{2}:\d{2}:\d{2}\]", "", text)

# [진행자], [박사] 같은 화자 태그 제거
text = re.sub(r"\[[^\]]+\]", "", text)

# 앞뒤 공백 정리
text = text.strip()

print(len(text))
