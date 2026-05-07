"""API connectivity: real chat completion with a minimal user message."""

from __future__ import annotations

from app.settings import DEFAULT_MODEL


def test_api_connection(api_base: str, api_key: str, model: str) -> bool:
    """
    Return True only if chat completions returns a non-empty assistant reply
    (same path as normal dialogue: POST .../chat/completions).
    """
    base = (api_base or "").strip().rstrip("/")
    key = (api_key or "").strip()
    m = (model or "").strip() or DEFAULT_MODEL
    if not base or not key:
        return False
    try:
        from app.openai_client import make_openai_client

        client = make_openai_client(base_url=base, api_key=key)
        resp = client.chat.completions.create(
            model=m,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=64,
            stream=False,
        )
        if not resp.choices:
            return False
        choice0 = resp.choices[0]
        msg = getattr(choice0, "message", None)
        if msg is None:
            return False
        content = getattr(msg, "content", None)
        if content is None:
            return False
        if isinstance(content, str):
            return bool(content.strip())
        # 少数返回类型为 list（多段内容）
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    t = block.get("text") or block.get("content")
                    if isinstance(t, str):
                        parts.append(t)
                elif isinstance(block, str):
                    parts.append(block)
            return bool("".join(parts).strip())
        return False
    except Exception:
        return False
