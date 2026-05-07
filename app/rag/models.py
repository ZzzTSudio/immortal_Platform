"""Pydantic models used by the RAG pipeline."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


SourceType = Literal["pdf", "docx", "md", "txt"]


class PreprocessConfig(BaseModel):
    tag: str | None = None


class ChunkMetadata(BaseModel):
    source: SourceType
    title: str = ""
    tag: str = "api_doc"
    filename: str = ""


class TextChunk(BaseModel):
    skill_id: str
    doc_id: str
    chunk_id: str
    content: str
    metadata: ChunkMetadata


class RAGPayload(BaseModel):
    skill_id: str
    doc_id: str
    chunk_id: str
    content: str
    metadata: ChunkMetadata

    def to_qdrant_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SearchHit(BaseModel):
    chunk_id: str
    doc_id: str = ""
    content: str
    metadata: ChunkMetadata
    score: float = 0.0
    dense_score: float | None = None
    sparse_score: float | None = None
    rerank_score: float | None = None
    point_id: str | None = None


class RAGSourceChunk(BaseModel):
    chunk_id: str
    content: str
    score: float = 0.0


class RAGSourceDocument(BaseModel):
    doc_id: str
    filename: str
    source_type: str
    title: str = ""
    tag: str = ""
    chunks: list[RAGSourceChunk]


class UploadFileResult(BaseModel):
    filename: str
    doc_id: str
    source_type: SourceType
    chunks: int


class RAGUploadResponse(BaseModel):
    success: bool = True
    skill_id: str = Field(..., alias="target_skill_id")
    files: list[UploadFileResult]
    total_chunks: int

