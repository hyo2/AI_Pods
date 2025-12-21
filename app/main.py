# app/main.py
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.routers import auth, input, output, project, storage, voice

from app.utils.vertex_env_patch import patch_vertex_ai_env

patch_vertex_ai_env()  # 배포용

app = FastAPI(
    title="AI Pods API",
    description="AI Pods API description",
    version="1.0.0",
    redirect_slashes=False
)

FRONTEND_URL = os.getenv("FRONTEND_URL")

REQUIRED_DIRS = [
    "outputs",
    "outputs/podcasts",
    "outputs/podcasts/wav",
]

for d in REQUIRED_DIRS:
    os.makedirs(d, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ======================
# API routers
# ======================
app.include_router(auth.router, prefix="/api")
app.include_router(project.router, prefix="/api")
app.include_router(input.router, prefix="/api")
app.include_router(output.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(storage.router, prefix="/api")

# ======================
# Frontend (mobile only)
# ======================

# 1️⃣ Vite assets 서빙
app.mount(
    "/assets",
    StaticFiles(directory="app/static/assets"),
    name="assets"
)

# 2️⃣ /mobile → index.html
@app.get("/mobile")
def serve_mobile():
    return FileResponse("app/static/index.html")

# 3️⃣ /mobile/... (새로고침 대응)
@app.get("/mobile/{path:path}")
def serve_mobile_spa(path: str):
    return FileResponse("app/static/index.html")