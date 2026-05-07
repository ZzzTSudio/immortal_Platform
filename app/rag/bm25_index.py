"""In-memory BM25 indexes grouped by skill_id."""

from __future__ import annotations

import re
from dataclasses import dataclass
from threading import RLock

from rank_bm25 import BM25Okapi

from app.rag.models import ChunkMetadata, SearchHit, TextChunk

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")


@dataclass(frozen=True)
class BM25Document:
    chunk_id: str
    doc_id: str
    content: str
    metadata: ChunkMetadata
    point_id: str | None = None


@dataclass
class _SkillIndex:
    bm25: BM25Okapi
    docs: list[BM25Document]


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text or "")]


class BM25IndexManager:
    def __init__(self):
        self._indexes: dict[str, _SkillIndex] = {}
        self._lock = RLock()

    def rebuild_all(self, chunks_by_skill: dict[str, list[BM25Document]]) -> None:
        with self._lock:
            self._indexes = {
                skill_id: _SkillIndex(BM25Okapi([tokenize(doc.content) for doc in docs]), docs)
                for skill_id, docs in chunks_by_skill.items()
                if docs
            }

    def rebuild_skill(self, skill_id: str, docs: list[BM25Document]) -> None:
        with self._lock:
            if not docs:
                self._indexes.pop(skill_id, None)
                return
            self._indexes[skill_id] = _SkillIndex(BM25Okapi([tokenize(doc.content) for doc in docs]), docs)

    def add_chunks(self, skill_id: str, chunks: list[TextChunk]) -> None:
        docs = [
            BM25Document(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                content=chunk.content,
                metadata=chunk.metadata,
                point_id=chunk.chunk_id,
            )
            for chunk in chunks
        ]
        with self._lock:
            existing = self._indexes.get(skill_id)
            all_docs = (existing.docs if existing else []) + docs
        self.rebuild_skill(skill_id, all_docs)

    def search(self, skill_id: str, query: str, top_k: int) -> list[SearchHit]:
        tokens = tokenize(query)
        if not tokens:
            return []
        with self._lock:
            index = self._indexes.get(skill_id)
            if index is None:
                return []
            scores = index.bm25.get_scores(tokens)
            docs = list(index.docs)
        ranked = sorted(enumerate(scores), key=lambda item: float(item[1]), reverse=True)[:top_k]
        hits: list[SearchHit] = []
        for idx, score in ranked:
            if score <= 0:
                continue
            doc = docs[idx]
            hits.append(
                SearchHit(
                    chunk_id=doc.chunk_id,
                    doc_id=doc.doc_id,
                    content=doc.content,
                    metadata=doc.metadata,
                    score=float(score),
                    sparse_score=float(score),
                    point_id=doc.point_id,
                )
            )
        return hits

