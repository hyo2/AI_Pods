# app/main.py
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from app.utils.vertex_env_patch import patch_vertex_ai_env
patch_vertex_ai_env()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import HTTPException
import os

import logging

# ✅ 전역 로깅 레벨 설정 (INFO 이상 모두 출력)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)8s] %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logging.getLogger("httpx").setLevel(logging.WARNING)

from app.routers import auth, input, output, project, storage, voice

app = FastAPI(
    title="AI Pods API",
    description="AI Pods API description",
    version="1.0.0",
    redirect_slashes=False
)

FRONTEND_URL = os.getenv("FRONTEND_URL")

# ✅ Railway 환경 감지 및 경로 설정
# Railway는 여러 환경 변수를 자동 제공 (RAILWAY_ENVIRONMENT, RAILWAY_PROJECT_ID 등)
IS_RAILWAY = (
    os.getenv("RAILWAY_ENVIRONMENT") is not None or 
    os.getenv("RAILWAY_PROJECT_ID") is not None or
    os.getenv("RAILWAY_SERVICE_NAME") is not None
)

if IS_RAILWAY:
    # Railway: /tmp 사용
    BASE_OUTPUT_DIR = "/tmp/outputs"
    print("🚂 Railway 환경 감지: /tmp/outputs 사용")
else:
    # 로컬: 프로젝트 루트의 outputs
    BASE_OUTPUT_DIR = os.path.abspath("outputs")
    print("💻 로컬 환경 감지: ./outputs 사용")

# ✅ 환경 변수로 저장 (다른 모듈에서 참조)
os.environ["BASE_OUTPUT_DIR"] = BASE_OUTPUT_DIR

REQUIRED_DIRS = [
    BASE_OUTPUT_DIR,
    os.path.join(BASE_OUTPUT_DIR, "podcasts"),
    os.path.join(BASE_OUTPUT_DIR, "podcasts", "wav"),
]

for d in REQUIRED_DIRS:
    os.makedirs(d, exist_ok=True)
    print(f"✅ 디렉토리 생성: {d}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# API routers
app.include_router(auth.router, prefix="/api")
app.include_router(project.router, prefix="/api")
app.include_router(input.router, prefix="/api")
app.include_router(output.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(storage.router, prefix="/api")

# Frontend (mobile only)
APP_DIR = Path(__file__).resolve().parent          # .../backend/app
STATIC_DIR = APP_DIR / "static"                    # .../backend/app/static
FAVICON_PATH = STATIC_DIR / "alan_favicon.svg"     # .../backend/app/static/alan_favicon.svg

app.mount(
    "/assets", 
    StaticFiles(directory=str(STATIC_DIR / "assets")), 
    name="assets"
)

@app.get("/alan_favicon.svg")
def favicon():
    if not FAVICON_PATH.is_file():
        # 디버깅용: 어떤 경로를 보고 있는지 에러 메시지로 확인
        raise HTTPException(status_code=404, detail=f"favicon not found: {FAVICON_PATH}")
    return FileResponse(FAVICON_PATH, media_type="image/svg+xml")

@app.get("/mobile")
def serve_mobile():
    return FileResponse("app/static/index.html")

@app.get("/mobile/{path:path}")
def serve_mobile_spa(path: str):
    return FileResponse("app/static/index.html")