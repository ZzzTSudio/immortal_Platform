"""Background thread for streaming LLM output."""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.llm_client import stream_chat_completion
from app.ollama_web_search import (
    WebSearchError,
    build_augmented_user_content,
    search_web,
    truncate_search_query,
)

# 与界面中保存的完整历史分离：仅限制发往 API 的条数，避免上下文过长。
MAX_API_HISTORY_MESSAGES = 80


class StreamWorker(QThread):
    chunk_received = Signal(str)
    failed = Signal(str, object)
    finished_ok = Signal()
    # 与 llm_client.on_status 对应，主线程更新首包前加载文案
    status_changed = Signal(str)

    def __init__(
        self,
        *,
        api_base: str,
        api_key: str,
        model: str,
        system: str,
        history: list[dict[str, Any]],
        web_search_enabled: bool = False,
        web_search_url: str = "",
        web_search_api_key: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api_base = api_base
        self._api_key = api_key
        self._model = model
        self._system = system
        self._history = history
        self._web_search_enabled = web_search_enabled
        self._web_search_url = web_search_url
        self._web_search_api_key = web_search_api_key
        self._openai_stream: Any = None
        self._user_aborted: bool = False

    @property
    def user_aborted(self) -> bool:
        return self._user_aborted

    def _on_stream_opened(self, stream: Any) -> None:
        self._openai_stream = stream

    def abort(self) -> None:
        """打断流式读取：请求中断并关闭 SDK 流，便于从阻塞的 next(chunk) 中尽快退出。"""
        if not self.isRunning():
            return
        self._user_aborted = True
        self.requestInterruption()
        s = self._openai_stream
        if s is not None:
            try:
                close = getattr(s, "close", None)
                if callable(close):
                    close()
            except Exception:
                pass

    def _filter_history_for_api(
        self, hist: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for m in hist:
            role = m.get("role")
            if role in ("user", "assistant"):
                out.append({"role": str(role), "content": str(m.get("content", ""))})
        return out

    def _build_messages(self) -> list[dict[str, Any]]:
        """system + user/assistant 历史；联网开启时仅增强最后一条 user。"""
        filtered = self._filter_history_for_api(self._history)
        if len(filtered) > MAX_API_HISTORY_MESSAGES:
            filtered = filtered[-MAX_API_HISTORY_MESSAGES:]
        messages: list[dict[str, Any]] = [{"role": "system", "content": self._system}]
        if not self._web_search_enabled or not filtered:
            for m in filtered:
                messages.append({"role": m["role"], "content": m["content"]})
            return messages

        if filtered[-1].get("role") != "user":
            for m in filtered:
                messages.append({"role": m["role"], "content": m["content"]})
            return messages

        # 复制并在末条 user 上附加检索（失败则降级为原文）
        tail = copy.deepcopy(filtered)
        last_plain = tail[-1]["content"]
        self.status_changed.emit("正在联网搜索…")
        if self.isInterruptionRequested():
            self._user_aborted = True
            for m in filtered:
                messages.append({"role": m["role"], "content": m["content"]})
            return messages

        try:
            q = truncate_search_query(last_plain)
            results = search_web(
                q,
                api_url=self._web_search_url,
                api_key=self._web_search_api_key,
            )
            tail[-1]["content"] = build_augmented_user_content(last_plain, results)
        except WebSearchError:
            self.status_changed.emit("联网搜索不可用，已直接回答…")
            for m in filtered:
                messages.append({"role": m["role"], "content": m["content"]})
            return messages

        for m in tail:
            messages.append({"role": m["role"], "content": m["content"]})
        return messages

    def run(self) -> None:
        self._openai_stream = None
        messages = self._build_messages()
        if self.isInterruptionRequested():
            self._user_aborted = True
            self.finished_ok.emit()
            return

        try:
            for piece in stream_chat_completion(
                api_base=self._api_base,
                api_key=self._api_key,
                model=self._model,
                messages=messages,
                on_status=lambda m: self.status_changed.emit(m),
                on_stream_opened=self._on_stream_opened,
                should_cancel=lambda: self.isInterruptionRequested(),
            ):
                if self.isInterruptionRequested():
                    self._user_aborted = True
                    break
                self.chunk_received.emit(piece)
            self.finished_ok.emit()
        except Exception as e:
            if self._user_aborted or self.isInterruptionRequested():
                self.finished_ok.emit()
            else:
                self.failed.emit(str(e), e)
        finally:
            self._openai_stream = None
