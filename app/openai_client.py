"""Shared OpenAI SDK client: always direct (ignore system / env proxies)."""

from __future__ import annotations

import httpx
from openai import DefaultHttpxClient, OpenAI

# 建连超时：发起 TCP/TLS 连接时，最多等待 10 秒。
_OPENAI_CONNECT_TIMEOUT_S = 10.0
# 读取超时：收到响应后，后续 30 秒内如果没有新的字节到达（含流式无新 chunk），就判定超时。
_OPENAI_READ_TIMEOUT_S = 60.0
# 写入超时：向服务端发送请求体时，单次写操作最多等待 30 秒。
_OPENAI_WRITE_TIMEOUT_S = 60.0
# 连接池超时：从 httpx 连接池里获取一个可用连接时，最多等待 30 秒。
_OPENAI_POOL_TIMEOUT_S = 60.0


def make_openai_client(*, base_url: str, api_key: str) -> OpenAI:
    """
    Use httpx with trust_env=False so HTTP(S)_PROXY / NO_PROXY and Windows
    registry proxies are not applied. Same behavior for chat and API test.
    """
    http_client = DefaultHttpxClient(
        trust_env=False,
        timeout=httpx.Timeout(
            connect=_OPENAI_CONNECT_TIMEOUT_S,
            read=_OPENAI_READ_TIMEOUT_S,
            write=_OPENAI_WRITE_TIMEOUT_S,
            pool=_OPENAI_POOL_TIMEOUT_S,
        ),
    )
    return OpenAI(
        base_url=base_url.rstrip("/"),
        api_key=api_key or "dummy",
        http_client=http_client,
    )
