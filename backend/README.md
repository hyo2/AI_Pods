# AI Pods Backend API

AI 기반 팟캐스트 및 이미지 생성 플랫폼의 백엔드 API 서버입니다. FastAPI 기반으로 구축되었으며, LangGraph를 활용한 AI 파이프라인을 통해 소스 콘텐츠를 팟캐스트로 자동 변환합니다.

## 주요 기능

- 🎙️ **AI 팟캐스트 생성**: 문서/링크를 입력받아 대화형 팟캐스트 생성
- 🖼️ **비주얼 콘텐츠**: 타임라인 기반 이미지 자동 생성
- 👥 **사용자 인증**: Supabase Auth 기반 회원가입/로그인
- 📁 **프로젝트 관리**: 팟캐스트 프로젝트별 소스 및 결과물 관리
- ☁️ **클라우드 스토리지**: Supabase Storage를 통한 파일 관리

## 기술 스택

- **Framework**: FastAPI 0.121.2
- **AI Pipeline**: LangGraph 1.0.4, LangChain 1.1.0
- **LLM**: Google Gemini (Vertex AI)
- **Database**: Supabase (PostgreSQL)
- **Storage**: Supabase Storage
- **Auth**: Supabase Auth
- **TTS**: Google Cloud Text-to-Speech

## 프로젝트 구조

```
backend/
├── app/
│   ├── main.py                    # FastAPI 앱 진입점
│   ├── core/                      # 인증, 의존성 관리
│   ├── routers/                   # API 엔드포인트
│   │   ├── auth.py               # 회원가입/로그인
│   │   ├── project.py            # 프로젝트 관리
│   │   ├── input.py              # 입력 소스 관리
│   │   ├── output.py             # 팟캐스트 생성/조회
│   │   ├── voice.py              # TTS 음성 목록
│   │   └── storage.py            # 파일 URL 생성
│   ├── services/                  # 외부 서비스 연동
│   │   ├── supabase_service.py   # Supabase 클라이언트
│   │   └── langgraph_service.py  # LangGraph 실행
│   └── langgraph_pipeline/        # AI 파이프라인
│       ├── graph.py              # LangGraph 워크플로우
│       ├── state.py              # 상태 관리
│       ├── podcast/              # 팟캐스트 생성 노드
│       └── vision/               # 이미지 생성 노드
├── requirements.txt
└── .env
```

## 설치 및 실행

### 1. 환경 설정

Python 3.11 이상 필요

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화 (Windows)
venv\Scripts\activate

# 가상환경 활성화 (Mac/Linux)
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일 생성:

```bash
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_role_key

# Google Cloud / Vertex AI
VERTEX_AI_PROJECT_ID=your_gcp_project_id
VERTEX_AI_REGION=us-central1
VERTEX_AI_SERVICE_ACCOUNT_FILE=path/to/service-account.json
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Frontend
FRONTEND_URL=http://localhost:3000
```

### 3. 서버 실행

```bash
# 개발 모드 (hot reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

서버 실행 후:

- API: `http://localhost:8000`
- **Swagger 문서**: `http://localhost:8000/docs`

## API 문서

### Swagger UI 사용법

1. 서버 실행 후 `http://localhost:8000/docs` 접속
2. 각 엔드포인트를 클릭하여 상세 정보 확인
3. "Try it out" 버튼으로 직접 API 테스트 가능
4. 우측 상단 "Authorize" 버튼으로 JWT 토큰 설정 가능

### 주요 엔드포인트

#### 인증 (Auth)

- `POST /api/users/signup` - 회원가입
- `POST /api/users/login` - 로그인

#### 프로젝트 (Projects)

- `GET /api/projects/?user_id={uuid}` - 프로젝트 목록
- `POST /api/projects/create` - 새 프로젝트 생성
- `DELETE /api/projects/{project_id}?user_id={uuid}` - 프로젝트 삭제

#### 입력 소스 (Inputs)

- `GET /api/inputs/list?project_id={id}` - 소스 목록
- `POST /api/inputs/upload` - 파일/링크 업로드
- `DELETE /api/inputs/{input_id}` - 소스 삭제

#### 팟캐스트 생성 (Outputs)

- `GET /api/outputs/list?project_id={id}` - 결과물 목록
- `GET /api/outputs/{output_id}` - 결과물 상세 조회
- `GET /api/outputs/{output_id}/status` - 생성 상태 확인
- `POST /api/outputs/generate` - 팟캐스트 생성 요청
- `DELETE /api/outputs/{output_id}` - 결과물 삭제

#### 음성 (Voices)

- `GET /api/voices/` - TTS 음성 목록

#### 스토리지 (Storage)

- `GET /api/storage/signed-url?path={path}` - Signed URL 생성

## LangGraph 파이프라인

AI 팟캐스트 생성은 다음 단계로 진행됩니다:

1. **소스 추출** (Extractors): 문서/링크에서 텍스트 추출
2. **스크립트 생성** (Script Generator): 대화형 팟캐스트 스크립트 작성
3. **TTS 변환** (TTS Service): Google Cloud TTS로 음성 변환
4. **오디오 처리** (Audio Processor): 여러 음성 파일 병합
5. **이미지 생성** (Vision Pipeline):
   - 메타데이터 추출
   - 스크립트 파싱
   - 이미지 기획
   - 프롬프트 생성
   - 이미지 생성 (Imagen)
   - 타임라인 매핑

## 트러블슈팅

### Supabase 연결 실패

```bash
# .env 파일 확인
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_KEY
```

### Google Cloud 인증 오류

```bash
# 서비스 계정 파일 권한 확인
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

### CORS 에러

- `FRONTEND_URL` 환경 변수가 올바른지 확인
- main.py의 CORS 설정 확인
