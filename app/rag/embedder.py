"""SiliconFlow embedding and rerank clients."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.rag.config import RAGSettings


class SiliconFlowEmbedder:
    def __init__(self, settings: RAGSettings):
        self.settings = settings
        self._sem = asyncio.Semaphore(settings.embedding_concurrency)
        self._client = AsyncOpenAI(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_api_base,
        )
        self._http = httpx.AsyncClient(
            base_url=settings.siliconflow_api_base.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.siliconflow_api_key}"},
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=30.0),
            trust_env=False,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        batches = [texts[i : i + self.settings.embedding_batch_size] for i in range(0, len(texts), self.settings.embedding_batch_size)]
        results: list[list[float]] = []
        for batch in batches:
            results.extend(await self._embed_batch(batch))
        return results

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self.embed_texts([query])
        return vectors[0]

    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        async with self._sem:
            async def call() -> list[list[float]]:
                response = await self._client.embeddings.create(
                    model=self.settings.embedding_model,
                    input=batch,
                )
                ordered = sorted(response.data, key=lambda item: item.index)
                return [list(item.embedding) for item in ordered]

            return await self._with_retry(call)

    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        if not documents:
            return []

        async def call() -> list[tuple[int, float]]:
            response = await self._http.post(
                "/rerank",
                json={
                    "model": self.settings.rerank_model,
                    "query": query,
                    "documents": documents,
                    "top_n": min(top_n, len(documents)),
                    "return_documents": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            return _parse_rerank_results(data)

        return await self._with_retry(call)

    async def _with_retry(self, call):
        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries + 1):
            try:
                return await call()
            except Exception as exc:
                last_error = exc
                if attempt >= self.settings.max_retries:
                    break
                await asyncio.sleep(min(8.0, 0.5 * (2**attempt)))
        assert last_error is not None
        raise last_error


def _parse_rerank_results(data: dict[str, Any]) -> list[tuple[int, float]]:
    raw_results = data.get("results") or data.get("data") or []
    parsed: list[tuple[int, float]] = []
    if not isinstance(raw_results, list):
        return parsed
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        index = item.get("index", item.get("document_index"))
        score = item.get("relevance_score", item.get("score"))
        try:
            parsed.append((int(index), float(score)))
        except (TypeError, ValueError):
            continue
    return parsed

