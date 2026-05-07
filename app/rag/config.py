"""RAG runtime settings."""

from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RAGSettings(BaseSettings):
    """Environment-backed settings for local Qdrant and SiliconFlow APIs."""

    model_config = SettingsConfigDict(env_prefix="RAG_", extra="ignore")

    enabled: bool = True

    qdrant_mode: str = "local"
    qdrant_url: str = "http://localhost:6333"
    qdrant_path: str = "data/qdrant"
    qdrant_api_key: str = ""
    qdrant_collection: str = "skill_knowledge"
    qdrant_max_connections: int = 20

    siliconflow_api_base: str = Field(
        default_factory=lambda: os.environ.get("CYBER_COLLEAGUE_API_BASE", "https://api.siliconflow.cn/v1")
    )
    siliconflow_api_key: str = Field(
        default_factory=lambda: os.environ.get("CYBER_COLLEAGUE_API_KEY", ""),
        repr=False,
    )
    embedding_model: str = "Pro/BAAI/bge-m3"
    rerank_model: str = "Pro/BAAI/bge-reranker-v2-m3"

    vector_name: str = "dense"
    vector_size: int = 1024
    hnsw_m: int = 16
    hnsw_ef_construct: int = 100
    hnsw_ef_search: int = 64

    chunk_size_tokens: int = 400
    chunk_overlap_tokens: int = 60
    prompt_token_limit: int = 1500

    embedding_batch_size: int = 8
    embedding_concurrency: int = 4
    max_retries: int = 3

    dense_top_k: int = 10
    sparse_top_k: int = 10
    rrf_top_k: int = 20
    rerank_top_k: int = 10
    rrf_k: int = 60
    weight_dense: float = 0.7
    weight_sparse: float = 0.3
    rerank_threshold: float = 0.5
    rerank_relaxed_threshold: float = 0.3

    query_cache_maxsize: int = 1000
    query_cache_ttl_seconds: int = 300

