# Alan Pods Frontend

> 문서를 업로드하고 AI 팟캐스트로 변환하는 웹 애플리케이션

## 📋 목차

- [프로젝트 개요](#프로젝트-개요)
- [주요 기능](#주요-기능)
- [기술 스택](#기술-스택)
- [프로젝트 구조](#프로젝트-구조)
- [설치 및 실행](#설치-및-실행)
- [페이지 구성](#페이지-구성)
- [컴포넌트 설명](#컴포넌트-설명)
- [API 연동](#api-연동)
- [개발 가이드](#개발-가이드)

## 🎯 프로젝트 개요

Alan Pods는 사용자가 업로드한 문서(PDF, DOCX, TXT)나 웹 링크를 AI 기반 팟캐스트로 자동 변환하는 서비스입니다. 두 명의 호스트가 대화하는 형식으로 콘텐츠를 재구성하며, 오디오, 스크립트, 관련 이미지를 함께 제공합니다.

## ✨ 주요 기능

### 1. 문서 관리

- PDF, DOCX, TXT 파일 업로드
- 웹 링크를 통한 문서 추가
- 드래그 앤 드롭 파일 업로드
- 소스 문서 선택 및 삭제

### 2. 팟캐스트 생성

- 4가지 스타일 선택 (설명형, 토론형, 인터뷰, 요약 중심)
- 2명의 AI 호스트 음성 선택
- 실시간 생성 상태 모니터링
- 다중 팟캐스트 생성 및 관리

### 3. 팟캐스트 재생

- 오디오 플레이어 통합
- 타임스탬프 기반 스크립트 싱크
- 시간대별 관련 이미지 표시
- 썸네일 클릭으로 구간 이동

### 4. 콘텐츠 다운로드

- 스크립트 텍스트 파일 다운로드
- 이미지 ZIP 파일 다운로드
- 오디오 파일 재생 및 다운로드

## 🛠 기술 스택

### Core

- **React 19.2.0** - UI 라이브러리
- **TypeScript 5.9.3** - 타입 안정성
- **Vite (Rolldown)** - 빌드 도구

### Styling

- **Tailwind CSS 3.4.17** - 유틸리티 기반 CSS 프레임워크
- **Lucide React** - 아이콘 라이브러리

### Routing & State

- **React Router DOM 7.9.6** - 클라이언트 사이드 라우팅

### File Handling

- **JSZip 3.10.1** - ZIP 파일 생성
- **File-Saver 2.0.5** - 파일 다운로드

## 📁 프로젝트 구조

```
frontend/
├── src/
│   ├── components/          # 재사용 가능한 컴포넌트
│   │   ├── GeneratePanel.tsx       # 팟캐스트 생성 패널
│   │   ├── Header.tsx              # 앱 헤더
│   │   ├── Layout.tsx              # 레이아웃 래퍼
│   │   ├── PodcastContents.tsx     # 팟캐스트 상세 뷰어
│   │   ├── ProjectSidebar.tsx      # 프로젝트 목록 사이드바
│   │   ├── Sidebar.tsx             # 좌측 네비게이션
│   │   └── SourcePanel.tsx         # 소스 관리 패널
│   │
│   ├── pages/               # 페이지 컴포넌트
│   │   ├── AuthPage.tsx            # 로그인/회원가입
│   │   ├── DocumentsPage.tsx       # 문서 업로드 (홈)
│   │   └── ProjectDetailPage.tsx   # 프로젝트 상세
│   │
│   ├── lib/                 # 유틸리티 & 설정
│   │   └── api.ts                  # API 기본 URL
│   │
│   ├── types/               # TypeScript 타입 정의
│   │   └── index.ts
│   │
│   ├── App.tsx              # 루트 컴포넌트
│   └── main.tsx             # 앱 엔트리 포인트
│
├── public/                  # 정적 파일
├── index.html               # HTML 템플릿
├── package.json             # 의존성 관리
├── tsconfig.json            # TypeScript 설정
├── tailwind.config.js       # Tailwind 설정
└── vite.config.ts           # Vite 설정
```

## 🚀 설치 및 실행

### 사전 요구사항

- Node.js 18.x 이상
- npm 또는 yarn

### 설치

```bash
# 저장소 클론
git clone <repository-url>
cd frontend

# 의존성 설치
npm install
```

### 환경 변수 설정

`src/lib/api.ts` 파일에서 API 기본 URL 확인:

```typescript
export const API_BASE_URL = "http://localhost:8000";
```

### 개발 서버 실행

```bash
npm run dev
```

- 개발 서버: http://localhost:5173

## 📄 페이지 구성

### 1. AuthPage (`/auth`)

- 로그인 및 회원가입 페이지
- 이메일/비밀번호 기반 인증
- JWT 토큰을 localStorage에 저장

### 2. DocumentsPage (`/`)

- 메인 랜딩 페이지
- 파일 업로드 (드래그 앤 드롭 지원)
- 웹 링크 추가
- 호스트 및 스타일 선택
- 프로젝트 생성 및 팟캐스트 생성 트리거

### 3. ProjectDetailPage (`/project/:id`)

- 3단 레이아웃 (소스 패널 / 콘텐츠 뷰어 / 생성 패널)
- 실시간 생성 상태 폴링
- 팟캐스트 재생 및 스크립트 동기화
- 이미지 썸네일 네비게이션

## 🧩 컴포넌트 설명

### Core Components

#### `Layout.tsx`

- 앱의 전체 레이아웃 구조 제공
- 사이드바 + 헤더 + 메인 콘텐츠 영역
- React Router Outlet으로 페이지 렌더링

#### `Header.tsx`

- 앱 상단 헤더
- Alan 로고, 사용자 아바타, 로그아웃 메뉴
- 로그인 상태에 따른 조건부 렌더링

#### `Sidebar.tsx`

- 좌측 네비게이션 바 (고정 60px)
- 프로젝트 목록, 검색, 노트 등 아이콘 버튼
- ProjectSidebar 토글 기능

#### `ProjectSidebar.tsx`

- 슬라이딩 프로젝트 목록 사이드바
- 프로젝트 생성, 삭제, 선택
- 애니메이션 트랜지션

### Content Panels

#### `SourcePanel.tsx`

- 소스 문서 관리
- 파일 업로드 모달 (드래그 앤 드롭)
- 웹 링크 추가
- 체크박스로 다중 선택
- 소스 삭제

**주요 기능:**

- PDF, DOCX, TXT 파일 검증
- FormData로 멀티파트 업로드
- 모달 UI

#### `GeneratePanel.tsx`

- 팟캐스트 생성 설정
- 호스트 선택 (API에서 음성 목록 fetch)
- 스타일 선택 (설명형, 토론형, 인터뷰, 요약)
- 생성된 팟캐스트 목록
- 접기/펼치기 UI

**주요 상태:**

- `processing`: 노란색 애니메이션
- `completed`: 초록색 완료 표시
- `failed`: 빨간색 실패 표시

#### `PodcastContents.tsx`

- 팟캐스트 상세 뷰어
- 오디오 플레이어
- 스크립트 (타임스탬프 기반 싱크)
- 이미지 뷰어 (메인 + 썸네일)
- 다운로드 메뉴 (스크립트, 이미지 ZIP)

**핵심 로직:**

```typescript
// 타임스탬프 파싱
function parseScript(script: string): ParsedLine[] {
  // [00:00:00] 텍스트 형식 파싱
}

// 현재 재생 중인 스크립트 라인 하이라이트
function isCurrentLine(idx: number, parsed: ParsedLine[], t: number);
```

## 🔌 API 연동

### Base URL

```typescript
export const API_BASE_URL = "http://localhost:8000";
```

### 주요 API 엔드포인트

#### 인증

- `POST /users/signup` - 회원가입
- `POST /users/login` - 로그인

#### 프로젝트

- `GET /projects?user_id={id}` - 프로젝트 목록
- `POST /projects/create` - 프로젝트 생성
- `DELETE /projects/{id}` - 프로젝트 삭제
- `GET /projects/{id}` - 프로젝트 상세

#### 입력 콘텐츠

- `POST /inputs/upload` - 파일/링크 업로드
- `GET /inputs/list?project_id={id}` - 소스 목록
- `DELETE /inputs/{id}` - 소스 삭제

#### 출력 (팟캐스트)

- `POST /outputs/generate` - 팟캐스트 생성
- `GET /outputs/list?project_id={id}` - 팟캐스트 목록
- `GET /outputs/{id}` - 팟캐스트 상세
- `GET /outputs/{id}/status` - 생성 상태 확인
- `DELETE /outputs/{id}` - 팟캐스트 삭제

#### 기타

- `GET /voices` - 사용 가능한 호스트 음성 목록
- `GET /storage/signed-url?path={path}` - S3 Signed URL 생성

### 인증 방식

```typescript
// LocalStorage에서 토큰 및 사용자 ID 관리
localStorage.getItem("access_token");
localStorage.getItem("user_id");
```
