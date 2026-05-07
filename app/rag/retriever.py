"""Hybrid search retrieval orchestrator."""

from __future__ import annotations

import asyncio

from app.qdrant.store import QdrantRAGStore
from app.rag.bm25_index import BM25IndexManager
from app.rag.cache import QueryEmbeddingCache
from app.rag.config import RAGSettings
from app.rag.embedder import SiliconFlowEmbedder
from app.rag.models import RAGSourceChunk, RAGSourceDocument, SearchHit
from app.rag.prompt_builder import build_knowledge_prompt


class RAGRetriever:
    def __init__(
        self,
        *,
        settings: RAGSettings,
        store: QdrantRAGStore,
        embedder: SiliconFlowEmbedder,
        bm25: BM25IndexManager,
        query_cache: QueryEmbeddingCache,
    ):
        self.settings = settings
        self.store = store
        self.embedder = embedder
        self.bm25 = bm25
        self.query_cache = query_cache

    async def retrieve_context(self, *, skill_id: str, query: str) -> str:
        hits = await self.retrieve(skill_id=skill_id, query=query)
        return build_knowledge_prompt(hits, max_tokens=self.settings.prompt_token_limit)

    async def retrieve_context_with_sources(
        self,
        *,
        skill_id: str,
        query: str,
        on_status=None,
    ) -> tuple[str, list[RAGSourceDocument]]:
        hits = await self.retrieve(skill_id=skill_id, query=query, on_status=on_status)
        if on_status:
            on_status("正在合成 RAG 提示词…")
        return build_knowledge_prompt(hits, max_tokens=self.settings.prompt_token_limit), build_source_documents(hits)

    async def retrieve(self, *, skill_id: str, query: str, on_status=None) -> list[SearchHit]:
        query = (query or "").strip()
        if not skill_id or not query:
            return []

        if on_status:
            on_status("正在生成查询向量…")
        vector = self.query_cache.get(query)
        if vector is None:
            vector = await self.embedder.embed_query(query)
            self.query_cache.set(query, vector)
        elif on_status:
            on_status("命中查询向量缓存…")

        if on_status:
            on_status("正在进行向量检索…")
        dense_task = self._dense_search(skill_id, vector)
        if on_status:
            on_status("正在进行关键词检索…")
        sparse_task = asyncio.to_thread(self.bm25.search, skill_id, query, self.settings.sparse_top_k)
        dense_hits, sparse_hits = await asyncio.gather(dense_task, sparse_task)
        if on_status:
            on_status("正在融合向量与关键词检索结果…")
        fused = rrf_fuse(
            dense_hits,
            sparse_hits,
            k=self.settings.rrf_k,
            weight_dense=self.settings.weight_dense,
            weight_sparse=self.settings.weight_sparse,
            limit=self.settings.rrf_top_k,
        )
        if not fused:
            return []

        if on_status:
            on_status("正在重排候选知识片段…")
        reranked = await self._rerank(query, fused)
        if on_status:
            on_status("正在筛选高相关知识片段…")
        return _threshold_hits(
            reranked,
            primary=self.settings.rerank_threshold,
            relaxed=self.settings.rerank_relaxed_threshold,
        )

    async def _dense_search(self, skill_id: str, vector: list[float]) -> list[SearchHit]:
        return await self.store.dense_search(
            skill_id=skill_id,
            vector=vector,
            top_k=self.settings.dense_top_k,
        )

    async def _rerank(self, query: str, hits: list[SearchHit]) -> list[SearchHit]:
        docs = [hit.content for hit in hits]
        results = await self.embedder.rerank(query, docs, top_n=self.settings.rerank_top_k)
        if not results:
            return hits[: self.settings.rerank_top_k]
        reranked: list[SearchHit] = []
        for idx, score in results:
            if idx < 0 or idx >= len(hits):
                continue
            hit = hits[idx].model_copy()
            hit.rerank_score = score
            hit.score = score
            reranked.append(hit)
        return reranked[: self.settings.rerank_top_k]


def rrf_fuse(
    dense_hits: list[SearchHit],
    sparse_hits: list[SearchHit],
    *,
    k: int,
    weight_dense: float,
    weight_sparse: float,
    limit: int,
) -> list[SearchHit]:
    merged: dict[str, SearchHit] = {}
    scores: dict[str, float] = {}

    def add(hits: list[SearchHit], weight: float, score_attr: str) -> None:
        for rank, hit in enumerate(hits, start=1):
            key = hit.chunk_id
            existing = merged.get(key)
            if existing is None:
                existing = hit.model_copy()
                merged[key] = existing
            setattr(existing, score_attr, hit.score)
            scores[key] = scores.get(key, 0.0) + weight / (k + rank)

    add(dense_hits, weight_dense, "dense_score")
    add(sparse_hits, weight_sparse, "sparse_score")

    ordered: list[SearchHit] = []
    for chunk_id, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]:
        hit = merged[chunk_id]
        hit.score = score
        ordered.append(hit)
    return ordered


def _threshold_hits(hits: list[SearchHit], *, primary: float, relaxed: float) -> list[SearchHit]:
    strong = [hit for hit in hits if (hit.rerank_score if hit.rerank_score is not None else hit.score) > primary]
    if len(strong) >= 3:
        return strong
    relaxed_hits = [hit for hit in hits if (hit.rerank_score if hit.rerank_score is not None else hit.score) > relaxed]
    if relaxed_hits:
        return relaxed_hits
    return [] #低于0.3不引用任何检索结果


def build_source_documents(hits: list[SearchHit]) -> list[RAGSourceDocument]:
    grouped: dict[tuple[str, str], RAGSourceDocument] = {}
    for hit in hits:
        filename = hit.metadata.filename or hit.metadata.title or "未命名文档"
        doc_id = hit.doc_id or hit.point_id or filename
        key = (doc_id, filename)
        source = grouped.get(key)
        if source is None:
            source = RAGSourceDocument(
                doc_id=doc_id,
                filename=filename,
                source_type=str(hit.metadata.source),
                title=hit.metadata.title,
                tag=hit.metadata.tag,
                chunks=[],
            )
            grouped[key] = source
        source.chunks.append(
            RAGSourceChunk(
                chunk_id=hit.chunk_id,
                content=hit.content,
                score=hit.rerank_score if hit.rerank_score is not None else hit.score,
            )
        )
    return list(grouped.values())


