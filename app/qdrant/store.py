"""Qdrant operations used by the RAG pipeline."""

from __future__ import annotations

from collections import defaultdict

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchValue,
    PointStruct,
    SearchParams,
    VectorParams,
)

from app.rag.bm25_index import BM25Document
from app.rag.config import RAGSettings
from app.rag.models import ChunkMetadata, RAGPayload, SearchHit, TextChunk


class QdrantRAGStore:
    def __init__(self, *, client: AsyncQdrantClient, settings: RAGSettings):
        self.client = client
        self.settings = settings

    async def ensure_collection(self) -> None:
        collections = await self.client.get_collections()
        exists = any(c.name == self.settings.qdrant_collection for c in collections.collections)
        if exists:
            return
        await self.client.create_collection(
            collection_name=self.settings.qdrant_collection,
            vectors_config={
                self.settings.vector_name: VectorParams(
                    size=self.settings.vector_size,
                    distance=Distance.COSINE,
                    hnsw_config=HnswConfigDiff(
                        m=self.settings.hnsw_m,
                        ef_construct=self.settings.hnsw_ef_construct,
                    ),
                )
            },
        )

    async def upsert_chunks(self, chunks: list[TextChunk], vectors: list[list[float]]) -> None:
        points: list[PointStruct] = []
        for chunk, vector in zip(chunks, vectors):
            payload = RAGPayload(
                skill_id=chunk.skill_id,
                doc_id=chunk.doc_id,
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                metadata=chunk.metadata,
            )
            points.append(
                PointStruct(
                    id=chunk.chunk_id,
                    vector={self.settings.vector_name: vector},
                    payload=payload.to_qdrant_payload(),
                )
            )
        await self.client.upsert(
            collection_name=self.settings.qdrant_collection,
            points=points,
        )

    async def load_bm25_documents(self) -> dict[str, list[BM25Document]]:
        grouped: dict[str, list[BM25Document]] = defaultdict(list)
        offset = None
        while True:
            points, offset = await self.client.scroll(
                collection_name=self.settings.qdrant_collection,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                doc = _payload_to_bm25_doc(payload, str(point.id))
                skill_id = payload.get("skill_id")
                if doc is not None and isinstance(skill_id, str) and skill_id:
                    grouped[skill_id].append(doc)
            if offset is None:
                break
        return dict(grouped)

    async def load_skill_bm25_documents(self, skill_id: str) -> list[BM25Document]:
        docs: list[BM25Document] = []
        offset = None
        while True:
            points, offset = await self.client.scroll(
                collection_name=self.settings.qdrant_collection,
                scroll_filter=_skill_filter(skill_id),
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                doc = _payload_to_bm25_doc(point.payload or {}, str(point.id))
                if doc is not None:
                    docs.append(doc)
            if offset is None:
                break
        return docs

    async def dense_search(self, *, skill_id: str, vector: list[float], top_k: int) -> list[SearchHit]:
        response = await self.client.query_points(
            collection_name=self.settings.qdrant_collection,
            query=vector,
            using=self.settings.vector_name,
            query_filter=_skill_filter(skill_id),
            limit=top_k,
            with_payload=True,
            search_params=SearchParams(hnsw_ef=self.settings.hnsw_ef_search),
        )
        hits: list[SearchHit] = []
        for point in response.points:
            payload = point.payload or {}
            hit = _payload_to_hit(payload, score=float(point.score), point_id=str(point.id))
            if hit is not None:
                hit.dense_score = float(point.score)
                hits.append(hit)
        return hits

    async def list_documents(self) -> list[dict]:
        docs: dict[tuple[str, str], dict] = {}
        offset = None
        while True:
            points, offset = await self.client.scroll(
                collection_name=self.settings.qdrant_collection,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                skill_id = payload.get("skill_id")
                doc_id = payload.get("doc_id")
                metadata = payload.get("metadata") or {}
                if not isinstance(skill_id, str) or not isinstance(doc_id, str) or not isinstance(metadata, dict):
                    continue
                key = (skill_id, doc_id)
                item = docs.setdefault(
                    key,
                    {
                        "skill_id": skill_id,
                        "doc_id": doc_id,
                        "filename": str(metadata.get("filename") or ""),
                        "source_type": str(metadata.get("source") or ""),
                        "tag": str(metadata.get("tag") or ""),
                        "chunk_count": 0,
                    },
                )
                item["chunk_count"] += 1
            if offset is None:
                break
        return sorted(docs.values(), key=lambda item: (item["skill_id"], item["filename"], item["doc_id"]))

    async def delete_document(self, *, skill_id: str, doc_id: str) -> int:
        docs = await self.list_documents()
        chunk_count = next(
            (
                int(doc["chunk_count"])
                for doc in docs
                if doc.get("skill_id") == skill_id and doc.get("doc_id") == doc_id
            ),
            0,
        )
        if chunk_count <= 0:
            return 0
        await self.client.delete(
            collection_name=self.settings.qdrant_collection,
            points_selector=_document_filter(skill_id, doc_id),
            wait=True,
        )
        return chunk_count

    async def list_document_chunks(self, *, skill_id: str, doc_id: str) -> list[dict]:
        chunks: list[dict] = []
        offset = None
        while True:
            points, offset = await self.client.scroll(
                collection_name=self.settings.qdrant_collection,
                scroll_filter=_document_filter(skill_id, doc_id),
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                metadata = payload.get("metadata") or {}
                chunks.append(
                    {
                        "point_id": str(point.id),
                        "chunk_id": str(payload.get("chunk_id") or point.id),
                        "doc_id": str(payload.get("doc_id") or ""),
                        "skill_id": str(payload.get("skill_id") or ""),
                        "content": str(payload.get("content") or ""),
                        "metadata": metadata if isinstance(metadata, dict) else {},
                    }
                )
            if offset is None:
                break
        return sorted(chunks, key=lambda item: item["chunk_id"])


def _skill_filter(skill_id: str) -> Filter:
    return Filter(
        must=[
            FieldCondition(
                key="skill_id",
                match=MatchValue(value=skill_id),
            )
        ]
    )


def _document_filter(skill_id: str, doc_id: str) -> Filter:
    return Filter(
        must=[
            FieldCondition(
                key="skill_id",
                match=MatchValue(value=skill_id),
            ),
            FieldCondition(
                key="doc_id",
                match=MatchValue(value=doc_id),
            ),
        ]
    )


def _payload_to_bm25_doc(payload: dict, point_id: str) -> BM25Document | None:
    content = payload.get("content")
    metadata = payload.get("metadata") or {}
    chunk_id = payload.get("chunk_id")
    if not isinstance(content, str) or not isinstance(chunk_id, str) or not isinstance(metadata, dict):
        return None
    return BM25Document(
        chunk_id=chunk_id,
        doc_id=str(payload.get("doc_id") or ""),
        content=content,
        metadata=ChunkMetadata.model_validate(metadata),
        point_id=point_id,
    )


def _payload_to_hit(payload: dict, *, score: float, point_id: str) -> SearchHit | None:
    content = payload.get("content")
    chunk_id = payload.get("chunk_id")
    metadata = payload.get("metadata") or {}
    if not isinstance(content, str) or not isinstance(chunk_id, str) or not isinstance(metadata, dict):
        return None
    return SearchHit(
        chunk_id=chunk_id,
        doc_id=str(payload.get("doc_id") or ""),
        content=content,
        metadata=ChunkMetadata.model_validate(metadata),
        score=score,
        point_id=point_id,
    )

