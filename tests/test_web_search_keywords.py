from app import ollama_web_search
from app.ollama_web_search import search_web_with_keywords


def test_search_web_with_keywords_runs_individual_and_combined_queries(monkeypatch):
    calls: list[str] = []
    statuses: list[str] = []

    monkeypatch.setattr(
        ollama_web_search,
        "extract_search_keywords",
        lambda *args, **kwargs: ["词1", "词2", "词3"],
    )

    def fake_search(query, *, api_url, api_key, max_results=5):
        calls.append(query)
        return [
            {"title": query, "url": f"https://example.com/{query}", "content": "摘要"},
            {"title": "重复", "url": "https://example.com/shared", "content": "重复摘要"},
        ]

    monkeypatch.setattr(ollama_web_search, "search_web", fake_search)

    results = search_web_with_keywords(
        "用户问题",
        api_base="https://api.example.com/v1",
        api_key="llm-key",
        model="model",
        web_search_url="https://search.example.com",
        web_search_api_key="search-key",
        on_status=statuses.append,
    )

    assert calls == ["词1", "词2", "词3", "词1 词2 词3"]
    assert statuses[0] == "正在提取联网搜索关键词…"
    assert "联网搜索 词1 中…" in statuses
    assert len(results) == 5


def test_search_web_with_keywords_falls_back_to_plain_query(monkeypatch):
    calls: list[str] = []

    def fail_extract(*args, **kwargs):
        raise RuntimeError("extract failed")

    def fake_search(query, *, api_url, api_key, max_results=5):
        calls.append(query)
        return [{"title": "t", "url": "https://example.com", "content": "c"}]

    monkeypatch.setattr(ollama_web_search, "extract_search_keywords", fail_extract)
    monkeypatch.setattr(ollama_web_search, "search_web", fake_search)

    results = search_web_with_keywords(
        "这是一个需要搜索的长问题",
        api_base="https://api.example.com/v1",
        api_key="llm-key",
        model="model",
        web_search_url="https://search.example.com",
        web_search_api_key="search-key",
    )

    assert calls == ["这是一个需要搜索的长问题"]
    assert results == [{"title": "t", "url": "https://example.com", "content": "c"}]
