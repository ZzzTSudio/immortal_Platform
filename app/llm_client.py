"""OpenAI-compatible chat completions with streaming."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from app.openai_client import make_openai_client


def _assistant_text_from_response(resp: Any) -> str:
    if not getattr(resp, "choices", None):
        return ""
    msg = resp.choices[0].message
    if msg is None:
        return ""
    c = getattr(msg, "content", None)
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: list[str] = []
        for block in c:
            if isinstance(block, dict):
                t = block.get("text") or block.get("content")
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def _is_network_timeout_or_disconnect(exc: Exception) -> bool:
    try:
        from openai import APIConnectionError, APITimeoutError

        if isinstance(exc, (APIConnectionError, APITimeoutError)):
            return True
    except ImportError:
        pass
    try:
        import httpx

        if isinstance(
            exc,
            (
                httpx.ConnectError,
                httpx.ConnectTimeout,
                httpx.ReadError,
                httpx.ReadTimeout,
                httpx.TimeoutException,
            ),
        ):
            return True
    except ImportError:
        pass
    return False


def stream_chat_completion(
    *,
    api_base: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    on_status: Callable[[str], None] | None = None,
    on_stream_opened: Callable[[Any], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> Iterator[str]:
    """
    Yield text deltas from the chat completions stream.

    If streaming is unsupported or returns no text (与设置里「API 测试」常用的非流式路径不一致时），
    自动回退为一次非流式请求并整段 yield，尽量与绿灯测试结果一致。

    on_status: 可选；在关键阶段回调短文案，供 UI 展示真实进度（运行于调用方线程）。
    on_stream_opened: 流式响应对象创建后回调，便于外部 close() 打断阻塞中的读取。
    should_cancel: 若返回 True，结束流并关闭连接（配合线程 requestInterruption 使用）。

    Raises APIError or other OpenAI client errors on failure.
    """

    def _cancelled() -> bool:
        return should_cancel is not None and should_cancel()

    def _st(msg: str) -> None:
        if on_status is not None:
            on_status(msg)

    _st("正在准备请求…")
    base = api_base.rstrip("/")
    client = make_openai_client(base_url=base, api_key=api_key)
    _st(f"正在获取对话中…")

    def non_stream_once() -> str:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
        )
        return _assistant_text_from_response(resp).strip()

    yielded_any = False
    stream: Any = None
    try:
        if _cancelled():
            return
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        if on_stream_opened is not None:
            on_stream_opened(stream)
        _st("流式连接已建立，等待模型首包…")
        try:
            for chunk in stream:
                if _cancelled():
                    break
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue
                content = getattr(delta, "content", None)
                if content:
                    yielded_any = True
                    yield content
        except Exception:
            if _cancelled():
                return
            raise
    except Exception as e:
        if _cancelled():
            return
        if yielded_any:
            raise
        if _is_network_timeout_or_disconnect(e):
            raise
        _st("流式请求未成功，正在尝试非流式完整回复…")
        try:
            if _cancelled():
                return
            text = non_stream_once()
            if text:
                yield text
                return
        except Exception as e2:
            raise e2 from e
        raise e
    finally:
        if stream is not None:
            try:
                close = getattr(stream, "close", None)
                if callable(close):
                    close()
            except Exception:
                pass

    if _cancelled():
        return
    if not yielded_any:
        _st("未收到流式内容，正在以非流式方式获取回复…")
        if _cancelled():
            return
        text = non_stream_once()
        if text:
            yield text
