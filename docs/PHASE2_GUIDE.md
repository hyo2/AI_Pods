# 🎨 Phase 2: 텍스트 → 이미지 파이프라인 실행 가이드

텍스트 분석 결과에서 토픽을 추출하고, 각 토픽마다 이미지를 자동 생성합니다.

---

## 🎯 Phase 2 목표

```
텍스트 입력
  ↓
문서 분석 (Phase 1 ✅)
  ↓
토픽 추출 (새로!)
  ↓
이미지 생성 (Imagen/Gemini)
  ↓
결과: 토픽별 이미지 + 갤러리 HTML
```

---

## 📦 준비 사항

### 1. 파일 복사

```bash
# 프로젝트 루트에서 실행

# 노드 파일
cp /mnt/user-data/outputs/topic_extraction_node.py app/nodes/
cp /mnt/user-data/outputs/image_generation_node.py app/nodes/

# 파이프라인
mkdir -p app/pipelines
cp /mnt/user-data/outputs/pipeline_phase2.py app/pipelines/

# 테스트
cp /mnt/user-data/outputs/test_phase2_pipeline.py tests/

# 문서
cp /mnt/user-data/outputs/PHASE2_GUIDE.md docs/
```

### 2. 폴더 구조

```
alan-document-lab/
├── app/
│   ├── nodes/
│   │   ├── document_analysis_node.py    (Phase 1)
│   │   ├── topic_extraction_node.py     ← 새로!
│   │   └── image_generation_node.py     ← 새로!
│   ├── services/
│   │   └── imagen_service.py            (이미 있음)
│   └── pipelines/
│       └── pipeline_phase2.py           ← 새로!
├── tests/
│   └── test_phase2_pipeline.py          ← 새로!
└── vertex-ai-service-account.json
```

---

## 🚀 빠른 시작 (1분)

### 가장 간단한 방법

```bash
python tests/test_phase2_pipeline.py

# 메뉴에서 '1. 빠른 파이프라인' 선택
# → 3-5개 이미지 생성 (약 2분)
```

### Python 코드로

```python
from app.pipelines.pipeline_phase2 import quick_pipeline
import vertexai

# Vertex AI 초기화
vertexai.init(project="alan-document-lab", location="us-central1")

# 파이프라인 실행
result = quick_pipeline(
    text="AI 기술의 발전...",  # 분석할 텍스트
    output_dir="./my_output",
    generation_strategy="fast"  # Gemini (빠름)
)

# 결과 확인
print(f"생성된 이미지: {len(result['images'])}개")
print(f"갤러리: {result['paths']['gallery_html']}")
```

---

## 📝 단계별 실행

### Step 1: 텍스트 분석 (Phase 1)

```python
from app.nodes.document_analysis_node import DocumentAnalysisNode, SourceDocument

analyzer = DocumentAnalysisNode()
sources = [SourceDocument(id="doc1", content="...", doc_type="text")]
analysis = analyzer.analyze_documents(sources)
```

### Step 2: 토픽 추출

```python
from app.nodes.topic_extraction_node import TopicExtractionNode
from dataclasses import asdict

topic_extractor = TopicExtractionNode()
topics = topic_extractor.extract_topics_from_analysis(
    asdict(analysis),
    min_topics=5,
    max_topics=15
)

# 결과 확인
print(f"추출된 토픽: {len(topics)}개")
for topic in topics:
    print(f"  - {topic.title} ({topic.style})")
```

### Step 3: 이미지 생성

```python
from app.nodes.image_generation_node import ImageGenerationNode

image_generator = ImageGenerationNode(output_dir="./images")
images = image_generator.generate_images_from_topics(
    topics,
    strategy="auto"  # 스타일에 따라 자동 선택
)

# 결과 확인
print(f"생성된 이미지: {len(images)}개")
for img in images:
    print(f"  - {img.topic_title}: {img.image_path}")
```

---

## 🎨 생성 전략

### 1. Fast (빠름)

```python
strategy="fast"
# - Gemini만 사용
# - 3-5초/이미지
# - 비용 효율적
# - 프로토타입, 테스트용
```

### 2. Quality (고품질)

```python
strategy="quality"
# - Imagen 4만 사용
# - 5-8초/이미지
# - 최고 품질
# - 최종 결과물용
```

### 3. Hybrid (혼합)

```python
strategy="hybrid"
# - 중요도에 따라 선택
# - 중요(0.8+): Imagen 4
# - 일반(0.8-): Gemini
# - 균형잡힌 접근
```

### 4. Auto (자동 - 추천!)

```python
strategy="auto"
# - 스타일에 따라 자동
# - abstract: Gemini
# - technical: Imagen 4
# - illustration: Gemini
# - photo: Imagen 4
# - scene: Imagen 4
```

---

## 🧪 테스트 시나리오

### 테스트 1: 빠른 테스트

```bash
python tests/test_phase2_pipeline.py
# → 메뉴 '1' 선택

# 출력:
# - 3-5개 토픽
# - 3-5개 이미지 (Gemini)
# - 소요 시간: 약 2분
# - 비용: ~$0.15
```

### 테스트 2: 긴 텍스트

```bash
python tests/test_phase2_pipeline.py
# → 메뉴 '2' 선택

# 출력:
# - 8-15개 토픽
# - 8-15개 이미지 (Auto)
# - 소요 시간: 약 5-10분
# - 비용: ~$0.50
```

### 테스트 3: 커스텀 입력

```bash
python tests/test_phase2_pipeline.py
# → 메뉴 '4' 선택
# → 텍스트 입력
# → 전략 선택
```

### 테스트 4: 토픽만 추출

```bash
python tests/test_phase2_pipeline.py
# → 메뉴 '6' 선택

# 이미지 생성 안 함
# 토픽만 확인 (빠름, 무료)
```

---

## 📊 출력 구조

### 파일 구조

```
pipeline_output/
├── images/                    ← 생성된 이미지
│   ├── topic_01_opening.png
│   ├── topic_02_ml_process.png
│   └── ...
├── json/                      ← 중간 데이터
│   ├── 01_analysis.json
│   ├── 02_topics.json
│   └── 03_images.json
└── gallery.html               ← 갤러리 (브라우저에서 열기)
```

### 갤러리 HTML

브라우저에서 열면:
- 이미지 그리드 뷰
- 토픽 제목, 스타일, 중요도 표시
- 클릭해서 확대 가능

```bash
# 갤러리 열기
open ./pipeline_output/gallery.html

# 또는
firefox ./pipeline_output/gallery.html
```

---

## 💡 실전 사용 예제

### 예제 1: 블로그 글 → 이미지

```python
blog_post = """
딥러닝의 기초

딥러닝은 인공 신경망을 여러 층으로 쌓아...
...
"""

result = quick_pipeline(
    text=blog_post,
    output_dir="./blog_images",
    generation_strategy="quality"  # 고품질
)

# 생성된 이미지를 블로그에 삽입
for img in result['images']:
    print(f"![{img.topic_title}]({img.image_path})")
```

### 예제 2: 프레젠테이션용 이미지

```python
presentation_script = """
[슬라이드 1] AI의 역사
[슬라이드 2] 머신러닝 개념
[슬라이드 3] 딥러닝 응용
...
"""

result = quick_pipeline(
    text=presentation_script,
    output_dir="./presentation_images",
    generation_strategy="quality"
)

# 슬라이드에 이미지 추가
```

### 예제 3: 교육 자료 이미지

```python
lecture_notes = """
1. 신경망의 구조
2. 학습 알고리즘
3. 활성화 함수
...
"""

result = quick_pipeline(
    text=lecture_notes,
    output_dir="./lecture_images",
    generation_strategy="auto"
)
```

---

## 🔧 커스터마이징

### 토픽 개수 조절

```python
from app.pipelines.pipeline_phase2 import DocumentToImagePipeline

pipeline = DocumentToImagePipeline()
result = pipeline.run(
    sources=...,
    min_topics=3,   # 최소 3개
    max_topics=10   # 최대 10개
)
```

### 이미지 스타일 선호도

토픽 추출 시 자동으로 스타일 결정되지만, 수동 조정 가능:

```python
# 토픽 추출 후
for topic in topics:
    if "기술" in topic.title:
        topic.style = "technical"
    elif "미래" in topic.title:
        topic.style = "abstract"
```

### 프롬프트 커스터마이징

```python
# ImagenService의 프롬프트 최적화 끄기
image_generator = ImageGenerationNode()
images = image_generator.generate_images_from_topics(
    topics,
    use_optimized_prompt=False  # 원본 description 사용
)
```

---

## 🐛 문제 해결

### 1. 토픽이 너무 적게 추출됨

```python
# min_topics 낮추기
pipeline.run(sources, min_topics=3)

# 또는 더 긴 텍스트 입력
```

### 2. 이미지 생성 실패

```python
# 429 에러: 자동 재시도됨 (기본 5회)
# 계속 실패하면 auto_delay 늘리기

image_generator = ImageGenerationNode(auto_delay=10)  # 10초 대기
```

### 3. 메모리 부족

```python
# 배치 크기 줄이기
# 토픽을 나눠서 생성

topics_batch1 = topics[:5]
topics_batch2 = topics[5:10]

images1 = image_generator.generate_images_from_topics(topics_batch1)
images2 = image_generator.generate_images_from_topics(topics_batch2)
```

### 4. JSON 파싱 에러

```
JSONDecodeError: ...
```

토픽 추출 결과를 확인:
```python
# 원본 Gemini 응답 확인
print(response.text)

# 수동 파싱 또는 프롬프트 조정
```

---

## 📈 성능 & 비용

### 소요 시간

| 텍스트 길이 | 토픽 수 | Gemini | Imagen 4 |
|-------------|---------|--------|----------|
| 짧음 (500자) | 3-5개 | 1-2분 | 2-3분 |
| 중간 (2000자) | 5-10개 | 3-5분 | 5-8분 |
| 김 (5000자+) | 10-20개 | 5-10분 | 10-20분 |

### 비용 추정

| 단계 | 비용 | 비고 |
|------|------|------|
| 분석 (Gemini 2.0) | ~$0.001 | 매우 저렴 |
| 토픽 추출 (Gemini 2.5) | ~$0.002 | 매우 저렴 |
| 이미지 생성 (Gemini) | $0.039/개 | 빠름 |
| 이미지 생성 (Imagen 4) | $0.020/개 | 고품질 |

**예시:**
- 10개 토픽 (All Gemini): ~$0.40
- 10개 토픽 (All Imagen 4): ~$0.20
- 10개 토픽 (Hybrid): ~$0.30

---

## ✅ Phase 2 체크리스트

- [ ] 파일 복사 완료
- [ ] 빠른 테스트 성공 (test 1)
- [ ] 긴 텍스트 테스트 (test 2)
- [ ] 갤러리 HTML 확인
- [ ] 생성된 이미지 품질 확인
- [ ] 토픽 추출 품질 확인
- [ ] 전략별 차이 이해
- [ ] 실제 텍스트로 테스트

---

## 🔜 다음 단계 (Phase 3)

Phase 2 완료 후:

1. **PDF/DOCX 입력 지원** (Phase 1 확장)
2. **오디오 생성** (TTS)
3. **타임스탬프 매칭**
4. **비디오 합성**

---

## 💡 팁

1. **처음에는 빠른 전략으로 테스트**
   ```python
   generation_strategy="fast"
   ```

2. **토픽 품질 확인 먼저**
   ```bash
   # 테스트 6: 토픽만 추출
   # 이미지 생성 전에 토픽 확인
   ```

3. **중요한 프로젝트는 hybrid**
   ```python
   generation_strategy="hybrid"
   # 균형잡힌 품질/비용
   ```

4. **갤러리로 빠르게 확인**
   ```bash
   open pipeline_output/gallery.html
   ```

---

**Phase 2 준비 완료! 🎨**

궁금한 점 있으면 언제든 물어보세요!
