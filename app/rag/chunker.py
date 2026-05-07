"""Markdown-aware chunking helpers."""

from __future__ import annotations

import hashlib
import re
import uuid

from app.rag.models import ChunkMetadata, SourceType, TextChunk

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_TOKEN_RE = re.compile(r"\w+|[\u4e00-\u9fff]|[^\s]")
_SPLITTERS = ["\n\n", "\n", "。", " "]


def estimate_tokens(text: str) -> int:
    return len(_TOKEN_RE.findall(text or ""))


def _doc_id(filename: str, content: str) -> str:
    h = hashlib.sha256()
    h.update(filename.encode("utf-8"))
    h.update(b"\0")
    h.update(content.encode("utf-8", errors="ignore"))
    return h.hexdigest()[:24]


def _split_by_markdown_headings(text: str) -> list[tuple[str, str]]:
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return []
    sections: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        title = match.group(2).strip()
        body = text[start:end].strip()
        if body:
            sections.append((title, body))
    leading = text[: matches[0].start()].strip()
    if leading:
        sections.insert(0, ("", leading))
    return sections


def _find_split_at(text: str, max_chars: int) -> int:
    window = text[:max_chars]
    for sep in _SPLITTERS:
        idx = window.rfind(sep)
        if idx > max_chars * 0.5:
            return idx + len(sep)
    return max_chars


def _split_long_text(text: str, chunk_size_tokens: int, overlap_tokens: int) -> list[str]:
    # Existing codebase uses character limits elsewhere; keep token sizing approximate and cheap.
    target_chars = max(200, chunk_size_tokens * 2)
    max_chars = int(target_chars * 1.2)
    overlap_chars = max(0, overlap_tokens * 2)
    chunks: list[str] = []
    rest = text.strip()
    while rest:
        if estimate_tokens(rest) <= int(chunk_size_tokens * 1.2):
            chunks.append(rest.strip())
            break
        split_at = _find_split_at(rest, max_chars)
        chunk = rest[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        if split_at >= len(rest):
            break
        start = max(0, split_at - overlap_chars)
        rest = rest[start:].strip()
    return chunks


def chunk_document(
    *,
    skill_id: str,
    filename: str,
    source_type: SourceType,
    text: str,
    tag: str = "api_doc",
    chunk_size_tokens: int = 400,
    overlap_tokens: int = 60,
) -> list[TextChunk]:
    doc_id = _doc_id(filename, text)
    sections = _split_by_markdown_headings(text)
    if not sections:
        sections = [("", text)]

    chunks: list[TextChunk] = []
    for title, section in sections:
        for content in _split_long_text(section, chunk_size_tokens, overlap_tokens):
            chunks.append(
                TextChunk(
                    skill_id=skill_id,
                    doc_id=doc_id,
                    chunk_id=str(uuid.uuid4()),
                    content=content,
                    metadata=ChunkMetadata(
                        source=source_type,
                        title=title,
                        tag=tag or "api_doc",
                        filename=filename,
                    ),
                )
            )
    return chunks

