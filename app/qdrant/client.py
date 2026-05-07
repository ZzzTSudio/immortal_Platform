"""Qdrant client construction."""

from __future__ import annotations

from pathlib import Path

from qdrant_client import AsyncQdrantClient

from app.paths import project_root
from app.rag.config import RAGSettings


def create_qdrant_client(settings: RAGSettings) -> AsyncQdrantClient:
    """Create a Qdrant client.

    Default mode is embedded local storage, so the app can run without a
    separately installed Qdrant service. Set RAG_QDRANT_MODE=server to use
    RAG_QDRANT_URL instead.
    """
    mode = settings.qdrant_mode.strip().lower()
    if mode == "server":
        return AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            pool_size=settings.qdrant_max_connections,
        )
    if mode != "local":
        raise ValueError("RAG_QDRANT_MODE 仅支持 local 或 server")

    path = Path(settings.qdrant_path).expanduser()
    if not path.is_absolute():
        path = project_root() / path
    path.mkdir(parents=True, exist_ok=True)
    return AsyncQdrantClient(path=str(path))

