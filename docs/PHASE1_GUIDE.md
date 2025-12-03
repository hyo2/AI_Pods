# 🚀 Phase 1: 단일/멀티 텍스트 분석 실행 가이드

텍스트 기반 문서 분석부터 시작하여 점진적으로 확장합니다.

---

## 📋 Phase 1 목표

✅ 단일 텍스트 문서 분석  
✅ 멀티 텍스트 문서 분석  
✅ Gemini를 통한 구조화된 요약  
✅ FastAPI 백엔드 엔드포인트  
✅ 테스트 및 검증

---

## 📦 준비 사항

### 1. 파일 복사

```bash
# 프로젝트 루트에서 실행

# 1. 노드 파일
cp /mnt/user-data/outputs/document_analysis_node.py app/nodes/

# 2. API 파일
cp /mnt/user-data/outputs/api_phase1.py app/api/

# 3. 테스트 파일
cp /mnt/user-data/outputs/test_phase1_analysis.py tests/
cp /mnt/user-data/outputs/test_api_client.py tests/

# 4. 문서
mkdir -p docs/phase1
cp /mnt/user-data/outputs/PHASE1_GUIDE.md docs/phase1/
```

### 2. 폴더 구조 확인

```
alan-document-lab/
├── app/
│   ├── nodes/
│   │   └── document_analysis_node.py    ← 메인 분석 노드
│   ├── api/
│   │   └── api_phase1.py                ← FastAPI 엔드포인트
│   └── services/
│       └── imagen_service.py            ← (나중에 사용)
├── tests/
│   ├── test_phase1_analysis.py          ← 직접 테스트
│   └── test_api_client.py               ← API 테스트
└── vertex-ai-service-account.json       ← Credentials
```

---

## 🧪 테스트 방법

### 방법 1: 직접 테스트 (노드만)

Vertex AI를 직접 호출하여 테스트합니다.

```bash
# 터미널에서 실행
python tests/test_phase1_analysis.py

# 메뉴 선택:
# 1. 단일 문서 분석
# 2. 멀티 문서 분석 (3개)
# 3. 커스텀 텍스트 입력
# 4. LangGraph 노드 형식
# 5. 엣지 케이스
# 6. 전체 테스트
```

**출력:**
- 콘솔: 요약 및 원본 출력
- 파일: `./test_output/*.json`

---

### 방법 2: API 서버 테스트

FastAPI 서버를 통한 테스트입니다.

#### Step 1: 서버 시작

```bash
# 터미널 1
python app/api/api_phase1.py

# 또는
uvicorn app.api.api_phase1:app --reload --host 0.0.0.0 --port 8000
```

서버가 시작되면:
```
🚀 Alan Document Lab - 문서 분석 API 서버
엔드포인트:
  - POST /api/v1/analyze       : 전체 분석
  - POST /api/v1/analyze/quick : 빠른 분석
  - POST /api/v1/analyze/raw   : 원본 출력만
문서:
  - http://localhost:8000/docs
```

#### Step 2: API 문서 확인

브라우저에서:
```
http://localhost:8000/docs
```

Swagger UI에서 직접 테스트 가능!

#### Step 3: 클라이언트로 테스트

```bash
# 터미널 2 (서버는 계속 실행)
python tests/test_api_client.py

# 메뉴 선택:
# 1. 헬스 체크
# 2. 빠른 분석
# 3. 단일 문서 분석
# 4. 멀티 문서 분석
# 5. 원본 출력만
# 6. 커스텀 입력
# 7. 에러 핸들링
# 8. 전체 테스트
```

**출력:**
- 콘솔: API 응답
- 파일: `./test_output/*.json`

---

### 방법 3: curl로 테스트

```bash
# 1. 헬스 체크
curl http://localhost:8000/health

# 2. 빠른 분석
curl -X POST http://localhost:8000/api/v1/analyze/quick \
  -H "Content-Type: application/json" \
  -d '{
    "content": "AI는 미래의 핵심 기술입니다."
  }'

# 3. 전체 분석
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "sources": [
      {
        "id": "doc_1",
        "content": "AI 기술의 발전과 미래...",
        "doc_type": "text"
      }
    ]
  }'
```

---

## 📝 실전 사용 예제

### 예제 1: Python 코드로 직접 사용

```python
from app.nodes.document_analysis_node import (
    DocumentAnalysisNode,
    SourceDocument
)

# 1. 노드 초기화
analyzer = DocumentAnalysisNode(model_name="gemini-2.5-flash")

# 2. 문서 생성
sources = [
    SourceDocument(
        id="doc_1",
        content="여기에 첫 번째 문서 내용...",
        doc_type="text"
    ),
    SourceDocument(
        id="doc_2",
        content="여기에 두 번째 문서 내용...",
        doc_type="text"
    )
]

# 3. 분석 실행
result = analyzer.analyze_documents(sources)

# 4. 결과 확인
print(result.metadata['raw_output'])

# 5. JSON 저장 (선택)
from app.nodes.document_analysis_node import save_analysis_to_json
save_analysis_to_json(result, "my_analysis.json")
```

---

### 예제 2: API로 사용

```python
import requests

# 1. 요청 데이터 준비
payload = {
    "sources": [
        {
            "id": "article_1",
            "content": "AI 기술의 발전...",
            "doc_type": "text"
        },
        {
            "id": "article_2",
            "content": "머신러닝의 이해...",
            "doc_type": "text"
        }
    ],
    "model_name": "gemini-2.5-flash"
}

# 2. API 호출
response = requests.post(
    "http://localhost:8000/api/v1/analyze",
    json=payload,
    timeout=120
)

# 3. 결과 확인
result = response.json()
if result['success']:
    raw_output = result['data']['metadata']['raw_output']
    print(raw_output)
```

---

### 예제 3: LangGraph 노드로 사용

```python
from langgraph.graph import StateGraph
from app.nodes.document_analysis_node import DocumentAnalysisNode

# 1. State 정의
class State:
    sources: list
    analysis_result: dict

# 2. 그래프 구성
workflow = StateGraph(State)

# 3. 노드 추가
analyzer_node = DocumentAnalysisNode()
workflow.add_node("analyze", analyzer_node)

# 4. 실행
initial_state = {
    "sources": [
        # ... SourceDocument 리스트
    ]
}

result = workflow.invoke(initial_state)
print(result['analysis_result'])
```

---

## 🔍 결과 구조 이해

### CompleteAnalysis 구조

```python
{
    "individual_analyses": [
        {
            "source_id": "doc_1",
            "doc_type": "text",
            "core_topic": "[주제]",
            "detailed_summary": "[요약]",
            "key_sentences": ["문장1", "문장2", "문장3"],
            "keywords": ["키워드1", "키워드2", ...],
            "raw_analysis": "[원본 텍스트]"
        }
    ],
    "relationship_analysis": {  # 문서가 2개 이상일 때만
        "common_themes": ["공통주제1", ...],
        "complementary_content": "[보완내용]",
        "differences": "[차이점]",
        "contradictions": "[모순점]",
        "mega_topic": "[메가 주제]",
        "raw_analysis": "[원본 텍스트]"
    },
    "clustering": {
        "topic_clusters": [
            {
                "name": "[클러스터명]",
                "description": "[설명]",
                "documents": [...],
                "insights": [...]
            }
        ],
        "sub_clusters": [...],
        "raw_analysis": "[원본 텍스트]"
    },
    "integrated_summary": {
        "sections": [
            {
                "title": "[섹션 제목]",
                "content": "[내용]",
                "key_points": [...]
            }
        ],
        "conclusion": "[결론]",
        "raw_analysis": "[원본 텍스트]"
    },
    "metadata": {
        "source_count": 2,
        "model": "gemini-2.5-flash",
        "raw_output_length": 5000,
        "raw_output": "[Gemini 전체 원본 출력]"
    }
}
```

---

## 🐛 문제 해결

### 1. Vertex AI 인증 에러

```
Error: Could not automatically determine credentials
```

**해결:**
```bash
# Credentials 파일 확인
ls -la vertex-ai-service-account.json

# 환경변수 설정
export GOOGLE_APPLICATION_CREDENTIALS="./vertex-ai-service-account.json"
```

---

### 2. 모듈 import 에러

```
ModuleNotFoundError: No module named 'app'
```

**해결:**
```python
# 스크립트 시작 부분에 추가
import sys
import os
sys.path.insert(0, os.path.abspath('.'))
```

또는:
```bash
# 프로젝트 루트에서 실행
PYTHONPATH=. python tests/test_phase1_analysis.py
```

---

### 3. API 서버 연결 실패

```
ConnectionError: Cannot connect to server
```

**해결:**
1. 서버가 실행 중인지 확인
2. 포트 8000이 사용 가능한지 확인
3. 방화벽 설정 확인

```bash
# 서버 프로세스 확인
lsof -i :8000

# 다른 포트로 실행
uvicorn app.api.api_phase1:app --port 8001
```

---

### 4. Gemini 응답 느림

Gemini 응답이 느릴 수 있습니다 (특히 긴 문서).

**해결:**
```python
# 타임아웃 늘리기
response = requests.post(
    url,
    json=payload,
    timeout=300  # 5분
)
```

---

## 📊 성능 체크리스트

### ✅ 테스트 완료 확인

- [ ] 단일 문서 분석 성공
- [ ] 멀티 문서 (2-3개) 분석 성공
- [ ] 긴 텍스트 (3000+ 단어) 분석 성공
- [ ] 많은 문서 (10개) 분석 성공
- [ ] API 엔드포인트 정상 동작
- [ ] 에러 핸들링 정상 동작

### 📈 품질 확인

Gemini 원본 출력(`metadata['raw_output']`)을 확인하여:

- [ ] 4가지 섹션 모두 생성됨
  - 소스별 핵심 분석
  - 소스 간 관계 분석 (멀티 문서)
  - 전체 문서 통합 클러스터링
  - 최종 통합 요약

- [ ] 각 섹션에 필요한 정보 포함됨
  - 핵심 주제, 상세 요약, 중요 문장, 키워드
  - 공통 주제, 보완 내용, 차이점, 메가 주제
  - 클러스터 이름, 설명, 인사이트
  - 섹션별 구성, 결론

---

## 🎯 다음 단계 (Phase 2 준비)

Phase 1이 완료되면:

1. **PDF/DOCX 지원** (Phase 2)
   - 파일 업로드 처리
   - OCR (필요시)
   - 메타데이터 추출

2. **웹 URL 크롤링** (Phase 3)
   - URL에서 콘텐츠 추출
   - 여러 페이지 처리
   - 크롤링 제한 처리

3. **이미지 생성 통합** (Phase 4)
   - 분석 결과 → 토픽 추출
   - 토픽별 이미지 생성
   - 메타데이터 연결

4. **팟캐스트 생성** (Phase 5)
   - 스크립트 생성
   - TTS 오디오 생성
   - 이미지와 타임스탬프 매칭
   - 최종 비디오 합성

---

## 📞 도움말

### 로그 확인

```bash
# API 서버 로그
# 서버 실행 터미널에서 실시간 확인

# Python 로그 (테스트)
python tests/test_phase1_analysis.py 2>&1 | tee test.log
```

### 디버그 모드

```python
# 더 상세한 출력
import logging
logging.basicConfig(level=logging.DEBUG)

# 또는 노드 내부에서
print(f"🐛 DEBUG: {변수명}")
```

---

## ✅ Phase 1 완료 체크리스트

- [ ] 모든 파일 복사 완료
- [ ] 직접 테스트 (노드) 성공
- [ ] API 서버 실행 성공
- [ ] API 테스트 클라이언트 성공
- [ ] 샘플 데이터로 전체 워크플로우 테스트
- [ ] 실제 데이터로 테스트 (선택)
- [ ] 결과 품질 확인
- [ ] 문제 해결 가이드 숙지

---

**Phase 1 완료 후, Phase 2로 진행하세요! 🚀**
