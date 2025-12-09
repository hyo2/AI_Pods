# 🎧 AI Pods – AI 기반 멀티소스 팟캐스트 생성 서비스

AI Pods는 **PDF·문서·웹 링크 등 다양한 소스 콘텐츠를 자동으로 대화형 AI 팟캐스트로 변환하는 서비스**입니다.  
AI 호스트 2명이 대화하는 형태로 스크립트를 생성하고, **오디오·스크립트·타임라인 이미지까지 자동 생성**해 제공합니다.

<br>

## 🗂️ 프로젝트 구조

```
AI_Pods/
├── backend/ # FastAPI 기반 API 서버
├── frontend/ # React 기반 웹 프론트엔드
└── README.md # (현재 문서) 프로젝트 통합 설명
```
backend/frontend 각각의 README는 각 폴더 내부에서 확인할 수 있습니다.

<br>

## ✨ 주요 기능

### 🎙️ 1) AI 팟캐스트 자동 생성
- 여러 문서를 선택하여 하나의 팟캐스트 생성  
- 웹 링크도 자동 파싱하여 텍스트 변환  
- 두 명의 AI 호스트가 대화하는 스크립트 생성  
- Google Cloud TTS 기반 음성 합성  
- 타임라인 기반 이미지 자동 생성 (Imagen 활용)  
- 실시간 생성 상태 모니터링 (`processing → completed`)  


### 📚 2) 프로젝트·소스 관리
- 프로젝트 생성/삭제  
- 소스 문서 업로드(PDF, DOCX, TXT)  
- 웹 URL 링크 추가  
- 소스 선택 후 팟캐스트 생성  
- 입력 소스 만료 자동 관리 (마지막 사용일로부터 180일 후 만료)  


### 🎧 3) 팟캐스트 뷰어 기능
- 오디오 플레이어  
- 타임스탬프 기반 스크립트 하이라이트  
- 이미지 타임라인 매핑  
- 이미지 클릭으로 해당 구간 이동  
- 스크립트 다운로드, 이미지 ZIP 다운로드  

<br>

## 🚀 기술 스택

### Backend (FastAPI)
- FastAPI  
- LangGraph / LangChain  
- Google Gemini (Vertex AI)  
- Supabase (DB, Auth, Storage)  
- Google Cloud TTS  
- 백그라운드 태스크 기반 LangGraph 실행  

### Frontend (React)
- React 19 + TypeScript  
- Vite (Rolldown)  
- Tailwind CSS  
- React Router  
- JSZip / FileSaver  

<br>

## 📁 상세 폴더 구조

### backend/
```
backend/
├── app/
│ ├── main.py
│ ├── routers/ # API 엔드포인트
│ ├── services/ # LangGraph · Supabase 등 외부 서비스
│ └── langgraph_pipeline/ # LangGraph
├── requirements.txt
└── .env
```

**주요 기능**
- 사용자 인증  
- 프로젝트 / 입력 소스 / 출력 관리  
- 팟캐스트 생성 API (`/outputs/generate`)  
- 생성 상태 폴링(`/outputs/{id}/status`)  
- Supabase Storage 업로드 및 URL 관리  
- LangGraph 기반 AI 파이프라인 실행


### frontend/
```
frontend/
├── src/
│ ├── components/
│ ├── pages/
│ ├── lib/
│ ├── types/
│ └── App.tsx
└── package.json
```

**주요 기능**
- 문서 업로드  
- 소스 선택 및 팟캐스트 생성  
- 생성 상태 실시간 반영  
- 스크립트 & 이미지 뷰어  
- 오디오 연동 / 다운로드 기능  
- JWT 로그인/회원가입  

<br>

## 🔧 설치 및 실행

### 1) Backend 실행

**Python 3.11+ 필요**

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows = venv\Scripts\activate
pip install -r requirements.txt
```

**환경변수 설정 (backend/.env)**
```
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...

VERTEX_AI_PROJECT_ID=...
VERTEX_AI_REGION=us-central1
VERTEX_AI_SERVICE_ACCOUNT_FILE=service.json

FRONTEND_URL=http://localhost:5173
```
**서버 실행**
```
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Swagger 문서:
➡️ http://localhost:8000/docs


### 2) Frontend 실행
**Node 18+ 필요**
```
cd frontend
npm install
npm run dev
```
프론트엔드 URL:
➡️ http://localhost:5173

<br>

## 🔌 API 개요
### 핵심 엔드포인트
| 기능        | Method          | Endpoint                        |
| --------- | --------------- | ------------------------------- |
| 팟캐스트 생성   | POST            | `/api/outputs/generate`         |
| 생성 상태 조회  | GET             | `/api/outputs/{id}/status`      |
| 팟캐스트 목록   | GET             | `/api/outputs/list?project_id=` |
| 팟캐스트 상세   | GET             | `/api/outputs/{id}`             |
| 프로젝트 CRUD | GET/POST/DELETE | `/api/projects/...`             |
| 소스 업로드    | POST            | `/api/inputs/upload`            |
| 소스 삭제     | DELETE          | `/api/inputs/{id}`              |
| 로그인/회원가입  | POST            | `/api/users/...`                |

<br>

## 🧠 AI 생성 파이프라인
1. 입력 문서/링크 → 텍스트 추출
2. Gemini 기반 팟캐스트 스크립트 생성
3. Google Cloud TTS로 음성 합성
4. 오디오 병합
5. 이미지 기획 및 자동 생성 (Imagen)
6. 스크립트와 이미지 타임라인 매핑
7. Storage 업로드 (오디오/스크립트/이미지)
8. DB 업데이트
9. 실패 시 자동 에러 처리 + 7일 후 삭제 예약

<br>

## 🎯 향후 확장 계획
- 교육용 전문 콘텐츠 모드 강화
- 다국어 팟캐스트 생성
- 커스터마이징 옵션 추가
- 팟캐스트 → 비디오 자동 변환

<br>

## 🙌 참고 사항
브랜치 사용 규칙:
- backend/ → 백엔드 개발
- frontend/ → 프론트엔드 개발
- main → 전체 통합 및 배포

