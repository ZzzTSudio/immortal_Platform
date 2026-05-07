import pytest

from app.qdrant.client import create_qdrant_client
from app.qdrant.store import QdrantRAGStore
from app.rag.bm25_index import BM25IndexManager
from app.rag.cache import QueryEmbeddingCache
from app.rag.config import RAGSettings
from app.rag.indexer import RAGIndexer
from app.rag.models import PreprocessConfig
from app.rag.retriever import RAGRetriever


class FakeEmbedder:
    def __init__(self, size: int):
        self.size = size

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    async def embed_query(self, query: str) -> list[float]:
        return self._vector(query)

    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        return [(idx, 0.9 - idx * 0.01) for idx in range(min(top_n, len(documents)))]

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.size
        vec[0] = 1.0 if "alpha" in text.lower() else 0.2
        vec[1] = 1.0 if "beta" in text.lower() else 0.1
        return vec


@pytest.mark.asyncio
async def test_local_qdrant_index_and_retrieve(tmp_path):
    settings = RAGSettings(
        qdrant_mode="local",
        qdrant_path=str(tmp_path / "qdrant"),
        qdrant_collection="test_skill_knowledge",
        vector_size=8,
        siliconflow_api_key="test",
    )
    client = create_qdrant_client(settings)
    store = QdrantRAGStore(client=client, settings=settings)
    bm25 = BM25IndexManager()
    embedder = FakeEmbedder(settings.vector_size)
    indexer = RAGIndexer(settings=settings, store=store, embedder=embedder, bm25=bm25)
    retriever = RAGRetriever(
        settings=settings,
        store=store,
        embedder=embedder,
        bm25=bm25,
        query_cache=QueryEmbeddingCache(100, 60),
    )

    try:
        await indexer.index_files(
            skill_id="skill_alpha",
            files=[("alpha.md", b"# Alpha\nalpha private knowledge for retrieval")],
            preprocess_config=PreprocessConfig(tag="test"),
        )

        context = await retriever.retrieve_context(skill_id="skill_alpha", query="alpha retrieval")

        assert "【知识库】" in context
        assert "alpha private knowledge" in context
    finally:
        await client.close()

