"""FastAPI entry point for the web version of Immortal."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.paths import project_root
from app.rag.config import RAGSettings
from app.rag.runtime import RAGRuntime
from app.settings import AppSettings
from app.web.routers import auth, chat, history, rag, settings as settings_router, skills

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure settings are loadable at startup
    _ = AppSettings.load()
    rag_runtime = None
    rag_settings = RAGSettings()
    if rag_settings.enabled:
        try:
            rag_runtime = RAGRuntime(rag_settings)
            await rag_runtime.start()
            app.state.rag_runtime = rag_runtime
        except Exception as exc:
            logger.warning("RAG runtime startup failed: %s", exc)
            app.state.rag_runtime = None
    try:
        yield
    finally:
        if rag_runtime is not None:
            await rag_runtime.close()


app = FastAPI(
    title="Immortal API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(skills.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(rag.router, prefix="/api")

# Sticker images
app.mount("/static/stickers", StaticFiles(directory=str(project_root() / "pic" / "bqb")), name="stickers")
# General pic resources
app.mount("/static/pic", StaticFiles(directory=str(project_root() / "pic")), name="pic")

# Built frontend (production)
dist_dir = project_root() / "web" / "dist"
if dist_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="spa")
else:
    @app.get("/")
    async def root():
        return {"message": "Immortal API is running. Frontend dist not found."}
