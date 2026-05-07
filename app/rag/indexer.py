"""Upload-to-Qdrant indexing pipeline."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

from app.qdrant.store import QdrantRAGStore
from app.rag.bm25_index import BM25IndexManager
from app.rag.chunker import chunk_document
from app.rag.cleaner import clean_document
from app.rag.config import RAGSettings
from app.rag.embedder import SiliconFlowEmbedder
from app.rag.models import PreprocessConfig, SourceType, TextChunk, UploadFileResult

_SUPPORTED_TYPES: dict[str, SourceType] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".md": "md",
    ".txt": "txt",
}


class RAGIndexer:
    def __init__(
        self,
        *,
        settings: RAGSettings,
        store: QdrantRAGStore,
        embedder: SiliconFlowEmbedder,
        bm25: BM25IndexManager,
    ):
        self.settings = settings
        self.store = store
        self.embedder = embedder
        self.bm25 = bm25

    async def ensure_collection(self) -> None:
        await self.store.ensure_collection()

    async def index_files(
        self,
        *,
        skill_id: str,
        files: list[tuple[str, bytes]],
        preprocess_config: PreprocessConfig,
    ) -> list[UploadFileResult]:
        await self.ensure_collection()
        results: list[UploadFileResult] = []
        all_chunks_for_skill: list[TextChunk] = []

        for filename, data in files:
            source_type = source_type_for_filename(filename)
            text, pages = extract_text(filename, data, source_type)
            cleaned = clean_document(text, pages=pages)
            chunks = chunk_document(
                skill_id=skill_id,
                filename=filename,
                source_type=source_type,
                text=cleaned,
                tag=preprocess_config.tag or "api_doc",
                chunk_size_tokens=self.settings.chunk_size_tokens,
                overlap_tokens=self.settings.chunk_overlap_tokens,
            )
            if chunks:
                await self._upsert_chunks(chunks)
                all_chunks_for_skill.extend(chunks)
            doc_id = chunks[0].doc_id if chunks else ""
            results.append(
                UploadFileResult(
                    filename=filename,
                    doc_id=doc_id,
                    source_type=source_type,
                    chunks=len(chunks),
                )
            )

        if all_chunks_for_skill:
            await self.rebuild_skill_bm25(skill_id)
        return results

    async def _upsert_chunks(self, chunks: list[TextChunk]) -> None:
        vectors = await self.embedder.embed_texts([chunk.content for chunk in chunks])
        await self.store.upsert_chunks(chunks, vectors)

    async def load_bm25_from_qdrant(self) -> None:
        self.bm25.rebuild_all(await self.store.load_bm25_documents())

    async def rebuild_skill_bm25(self, skill_id: str) -> None:
        docs = await self.store.load_skill_bm25_documents(skill_id)
        self.bm25.rebuild_skill(skill_id, docs)

    async def list_documents(self) -> list[dict]:
        return await self.store.list_documents()

    async def delete_document(self, *, skill_id: str, doc_id: str) -> int:
        deleted_chunks = await self.store.delete_document(skill_id=skill_id, doc_id=doc_id)
        if deleted_chunks:
            await self.rebuild_skill_bm25(skill_id)
        return deleted_chunks

    async def list_document_chunks(self, *, skill_id: str, doc_id: str) -> list[dict]:
        return await self.store.list_document_chunks(skill_id=skill_id, doc_id=doc_id)


def source_type_for_filename(filename: str) -> SourceType:
    suffix = Path(filename).suffix.lower()
    source_type = _SUPPORTED_TYPES.get(suffix)
    if source_type is None:
        raise ValueError(f"不支持的文件类型：{suffix or filename}")
    return source_type


def extract_text(filename: str, data: bytes, source_type: SourceType) -> tuple[str, list[str] | None]:
    if source_type == "pdf":
        return _extract_pdf(data)
    if source_type == "docx":
        return _extract_docx(data), None
    if source_type in ("md", "txt"):
        return data.decode("utf-8", errors="replace"), None
    raise ValueError(f"不支持的文件类型：{filename}")


def _extract_pdf(data: bytes) -> tuple[str, list[str]]:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n\n".join(pages), pages


def _extract_docx(data: bytes) -> str:
    from docx import Document

    document = Document(BytesIO(data))
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def parse_preprocess_config(raw: str | None) -> PreprocessConfig:
    if not raw:
        return PreprocessConfig()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("preprocess_config 必须是合法 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("preprocess_config 必须是 JSON object")
    return PreprocessConfig.model_validate(value)


