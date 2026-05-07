"""Ollama Cloud Web Search API (REST). URL 与密钥由应用设置传入。"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.openai_client import make_openai_client
from app.settings import DEFAULT_OLLAMA_WEB_SEARCH_URL

_CONNECT_TIMEOUT_S = 10.0
_READ_TIMEOUT_S = 30.0

# 控制检索块体积，避免撑爆上下文（与 Skill system 并存）
MAX_QUERY_CHARS = 500
MAX_RESULTS_DEFAULT = 5
MAX_PER_RESULT_CONTENT_CHARS = 1200
MAX_SEARCH_BLOCK_CHARS = 6000
MAX_SEARCH_KEYWORDS = 3


class WebSearchError(Exception):
    """联网搜索请求失败（HTTP、超时、解析错误等）。"""


def _client_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=_CONNECT_TIMEOUT_S,
        read=_READ_TIMEOUT_S,
        write=60.0,
        pool=30.0,
    )


def _truncate(s: str, limit: int) -> str:
    s = s.strip()
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 20)] + "\n…(已截断)"


def truncate_search_query(user_text: str) -> str:
    """将用户输入截断为搜索 query。"""
    t = (user_text or "").strip()
    return _truncate(t, MAX_QUERY_CHARS)


def search_web(
    query: str,
    *,
    api_url: str,
    api_key: str,
    max_results: int = MAX_RESULTS_DEFAULT,
) -> list[dict[str, str]]:
    """
    POST 给定 web_search 端点。
    返回 results 列表，每项含 title, url, content（字符串）。
    """
    q = (query or "").strip()
    if not q:
        return []

    url = (api_url or "").strip().rstrip("/") or DEFAULT_OLLAMA_WEB_SEARCH_URL
    key = (api_key or "").strip()
    if not key:
        raise WebSearchError("联网 API 密钥未配置")

    mr = max(1, min(int(max_results), 10))
    with httpx.Client(trust_env=False, timeout=_client_timeout()) as client:
        try:
            resp = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={"query": q, "max_results": mr},
            )
        except httpx.HTTPError as e:
            raise WebSearchError(str(e)) from e

    if resp.status_code >= 400:
        raise WebSearchError(f"HTTP {resp.status_code}")

    try:
        data: dict[str, Any] = resp.json()
    except json.JSONDecodeError as e:
        raise WebSearchError("响应非 JSON") from e

    raw_results = data.get("results")
    if not isinstance(raw_results, list):
        return []

    out: list[dict[str, str]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        url_v = item.get("url")
        content = item.get("content")
        out.append(
            {
                "title": str(title) if title is not None else "",
                "url": str(url_v) if url_v is not None else "",
                "content": str(content) if content is not None else "",
            }
        )
    return out


def extract_search_keywords(
    user_text: str,
    *,
    api_base: str,
    api_key: str,
    model: str,
) -> list[str]:
    """Ask the configured chat model for up to three concise web-search keywords."""
    plain = (user_text or "").strip()
    if not plain:
        return []

    client = make_openai_client(base_url=api_base.rstrip("/"), api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是搜索关键词提取器。只返回 JSON 字符串数组，最多 3 个元素。"
                    "每个元素必须是最核心、适合联网搜索的中文或英文关键词/短语。"
                ),
            },
            {"role": "user", "content": truncate_search_query(plain)},
        ],
        stream=False,
    )
    text = ""
    if getattr(resp, "choices", None):
        msg = resp.choices[0].message
        text = str(getattr(msg, "content", "") or "")
    return _parse_keywords(text)


def search_web_with_keywords(
    user_text: str,
    *,
    api_base: str,
    api_key: str,
    model: str,
    web_search_url: str,
    web_search_api_key: str,
    on_status=None,
) -> list[dict[str, str]]:
    """Extract keywords, run individual and combined searches, and dedupe results."""
    try:
        if on_status is not None:
            on_status("正在提取联网搜索关键词…")
        keywords = extract_search_keywords(
            user_text,
            api_base=api_base,
            api_key=api_key,
            model=model,
        )
    except Exception:
        keywords = []

    queries = _build_search_queries(keywords)
    if not queries:
        queries = [truncate_search_query(user_text)]

    results: list[dict[str, str]] = []
    failures = 0
    for query in queries:
        if on_status is not None:
            on_status(f"联网搜索 {query} 中…")
        try:
            results.extend(
                search_web(
                    query,
                    api_url=web_search_url,
                    api_key=web_search_api_key,
                )
            )
        except WebSearchError:
            failures += 1
            continue

    if failures == len(queries) and not results:
        raise WebSearchError("联网搜索不可用")
    return _dedupe_results(results)


def _parse_keywords(text: str) -> list[str]:
    raw = (text or "").strip()
    values: list[Any]
    try:
        parsed = json.loads(raw)
        values = parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        values = [line.strip("-* \t\r\n") for line in raw.replace("，", "\n").replace(",", "\n").splitlines()]

    keywords: list[str] = []
    seen: set[str] = set()
    for value in values:
        keyword = str(value).strip().strip("\"'`")
        if not keyword:
            continue
        keyword = _truncate(keyword, 80)
        key = keyword.lower()
        if key in seen:
            continue
        seen.add(key)
        keywords.append(keyword)
        if len(keywords) >= MAX_SEARCH_KEYWORDS:
            break
    return keywords


def _build_search_queries(keywords: list[str]) -> list[str]:
    queries = [kw for kw in keywords[:MAX_SEARCH_KEYWORDS] if kw.strip()]
    if len(queries) > 1:
        queries.append(" ".join(queries))
    return queries


def _dedupe_results(results: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for result in results:
        key = (result.get("url") or result.get("title") or result.get("content") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def test_web_search_connection(api_url: str, api_key: str) -> bool:
    """
    最小请求验证端点与密钥：2xx 且响应为 JSON 即视为成功。
    """
    url = (api_url or "").strip().rstrip("/") or DEFAULT_OLLAMA_WEB_SEARCH_URL
    key = (api_key or "").strip()
    if not key:
        return False
    try:
        with httpx.Client(trust_env=False, timeout=_client_timeout()) as client:
            resp = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={"query": "ping", "max_results": 1},
            )
    except httpx.HTTPError:
        return False
    if resp.status_code < 200 or resp.status_code >= 300:
        return False
    try:
        resp.json()
    except json.JSONDecodeError:
        return False
    return True


def format_search_block(results: list[dict[str, str]]) -> str:
    """
    将检索结果格式化为纯文本块（含长度上限）。
    results 为空时返回简短说明，供模型知晓「无摘要」。
    """
    if not results:
        return (
            "【联网检索】未找到相关网页摘要。请仅根据你的知识与用户问题回答，"
            "不要编造检索来源。"
        )

    lines: list[str] = [
        "【联网检索】以下为与用户问题相关的网页摘要（供参考，注意时效与准确性）：",
        "",
    ]
    total = 0
    for i, r in enumerate(results, start=1):
        title = (r.get("title") or "").strip()
        url_line = (r.get("url") or "").strip()
        body = _truncate((r.get("content") or "").strip(), MAX_PER_RESULT_CONTENT_CHARS)
        chunk = (
            f"{i}. {title}\n"
            f"   链接: {url_line}\n"
            f"   摘要: {body}\n"
        )
        if total + len(chunk) > MAX_SEARCH_BLOCK_CHARS:
            lines.append("…(后续结果已省略以控制长度)")
            break
        lines.append(chunk)
        total += len(chunk)

    return "\n".join(lines).strip()


def build_augmented_user_content(plain_user_message: str, results: list[dict[str, str]]) -> str:
    """拼出发往 API 的最后一条 user：检索块 + 用户原文。"""
    plain = (plain_user_message or "").strip()
    block = format_search_block(results)
    return f"{block}\n\n【用户问题】\n{plain}"
