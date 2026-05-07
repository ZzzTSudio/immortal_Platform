"""RAG runtime wiring for FastAPI lifespan and routes."""

from __future__ import annotations

from app.qdrant.client import create_qdrant_client
from app.qdrant.store import QdrantRAGStore
from app.rag.bm25_index import BM25IndexManager
from app.rag.cache import QueryEmbeddingCache
from app.rag.config import RAGSettings
from app.rag.embedder import SiliconFlowEmbedder
from app.rag.indexer import RAGIndexer
from app.rag.retriever import RAGRetriever


class RAGRuntime:
    def __init__(self, settings: RAGSettings):
        self.settings = settings
        self.qdrant = create_qdrant_client(settings)
        self.store = QdrantRAGStore(client=self.qdrant, settings=settings)
        self.embedder = SiliconFlowEmbedder(settings)
        self.bm25 = BM25IndexManager()
        self.query_cache = QueryEmbeddingCache(
            maxsize=settings.query_cache_maxsize,
            ttl_seconds=settings.query_cache_ttl_seconds,
        )
        self.indexer = RAGIndexer(
            settings=settings,
            store=self.store,
            embedder=self.embedder,
            bm25=self.bm25,
        )
        self.retriever = RAGRetriever(
            settings=settings,
            store=self.store,
            embedder=self.embedder,
            bm25=self.bm25,
            query_cache=self.query_cache,
        )

    async def start(self) -> None:
        await self.indexer.ensure_collection()
        await self.indexer.load_bm25_from_qdrant()

    async def close(self) -> None:
        await self.embedder.close()
        await self.qdrant.close()

