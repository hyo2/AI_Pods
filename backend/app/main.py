# app/main.py
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from app.routers import auth,input, output, project, storage, voice
from app.routers.project import router as projects_router

app = FastAPI(
    title="AI Pods API",
    description="AI Pods API description",
    version="1.0.0"
)

print("SUPABASE_URL loaded:", os.getenv("SUPABASE_URL"))
print("FRONTEND_URL loaded:", os.getenv("FRONTEND_URL"))

FRONTEND_URL = os.getenv("FRONTEND_URL")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(auth.router, prefix="/api")
app.include_router(project.router, prefix="/api")
app.include_router(input.router, prefix="/api")
app.include_router(output.router, prefix="/api") 
app.include_router(voice.router, prefix="/api")
app.include_router(storage.router, prefix="/api")