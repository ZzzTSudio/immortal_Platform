"""Build bounded RAG prompt context."""

from __future__ import annotations

from app.rag.chunker import estimate_tokens
from app.rag.models import SearchHit


def build_knowledge_prompt(hits: list[SearchHit], max_tokens: int = 1500) -> str:
    if not hits:
        return ""

    ordered = sorted(hits, key=lambda hit: hit.rerank_score if hit.rerank_score is not None else hit.score, reverse=True)
    lines = ["【知识库】"]
    total_tokens = estimate_tokens(lines[0])
    kept = 0
    for hit in ordered:
        source = hit.metadata.source
        title = hit.metadata.title or hit.metadata.filename or "未命名"
        item = f"[{kept + 1}] {hit.content.strip()}（来源：{source}，标题：{title}）"
        item_tokens = estimate_tokens(item)
        if kept > 0 and total_tokens + item_tokens > max_tokens:
            break
        if total_tokens + item_tokens > max_tokens:
            item = _truncate_to_tokens(item, max_tokens - total_tokens)
        lines.append(item)
        total_tokens += estimate_tokens(item)
        kept += 1
    return "\n".join(lines).strip() if kept else ""


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    # Cheap approximation: Chinese chars and Latin words average close to two chars here.
    max_chars = max(20, max_tokens * 2)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 8].rstrip() + "…(截断)"

