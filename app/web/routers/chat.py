"""Streaming chat route (Server-Sent Events)."""

from __future__ import annotations

import asyncio
import copy
import json
import threading
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.chat_file_context import ChatFileValidationError, build_chat_file_context
from app.database import get_user_settings
from app.llm_client import stream_chat_completion
from app.ollama_web_search import (
    WebSearchError,
    build_augmented_user_content,
    search_web_with_keywords,
)
from app.paths import builtin_skill_dir, project_root
from app.settings import DEFAULT_API_BASE, DEFAULT_MODEL, DEFAULT_OLLAMA_WEB_SEARCH_URL
from app.skill_loader import build_system_prompt, discover_colleagues
from app.web.schemas import ChatRequest, ChatStopRequest

router = APIRouter()

# 按 colleague_id 记录当前活跃流，便于新请求到来时中断旧流
_active_streams: dict[str, dict[str, Any]] = {}
MAX_API_HISTORY_MESSAGES = 80


def _get_user_id(request: Request) -> int:
    """Get user_id from cookie, raise 401 if not logged in."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    return int(user_id)


def _get_user_settings(request: Request) -> dict:
    """Get user settings from database."""
    user_id = _get_user_id(request)
    settings = get_user_settings(user_id)
    if not settings:
        return {
            "api_base": DEFAULT_API_BASE,
            "api_key": "",
            "model": DEFAULT_MODEL,
            "web_search_url": DEFAULT_OLLAMA_WEB_SEARCH_URL,
            "web_search_api_key": "",
        }
    return {
        "api_base": settings.get("api_base") or DEFAULT_API_BASE,
        "api_key": settings.get("api_key") or "",
        "model": settings.get("model") or DEFAULT_MODEL,
        "web_search_url": settings.get("web_search_url") or DEFAULT_OLLAMA_WEB_SEARCH_URL,
        "web_search_api_key": settings.get("web_search_api_key") or "",
    }


def _get_colleague(request: Request, colleague_id: str):
    # 复用当前技能发现逻辑，确保请求目标同事存在
    settings = _get_user_settings(request)
    builtin = builtin_skill_dir()
    skill_lib_path = project_root() / "skill_lib"
    all_c = discover_colleagues(str(skill_lib_path), builtin)
    c = next((x for x in all_c if x.colleague_id == colleague_id), None)
    if not c:
        raise HTTPException(status_code=404, detail="Colleague not found")
    return c


def _filter_history_for_api(hist: list[dict[str, Any]]) -> list[dict[str, str]]:
    # 仅保留模型可消费的 user/assistant 消息，过滤 sticker 等非对话角色
    out: list[dict[str, str]] = []
    for m in hist:
        role = m.get("role")
        if role in ("user", "assistant"):
            out.append({"role": str(role), "content": str(m.get("content", ""))})
    return out


def _last_user_message(history: list[dict[str, Any]]) -> str:
    # 反向查找最后一条用户输入，用于 RAG/联网搜索
    for message in reversed(history):
        if message.get("role") == "user":
            return str(message.get("content", "")).strip()
    return ""


def _append_rag_context(system: str, rag_context: str) -> str:
    # RAG 结果注入 system 末尾
    block = (rag_context or "").strip()
    if not block:
        return system
    return f"{system}\n\n---\n\n## [RAG]\n\n{block}"


def _append_file_context(system: str, file_context: str) -> str:
    # 临时文件上下文注入 system 末尾（仅当前会话生效）
    block = (file_context or "").strip()
    if not block:
        return system
    return f"{system}\n\n---\n\n## [FILES]\n\n{block}"


def _parse_chat_request(colleague_id: str, messages: str, web_search_enabled: bool) -> ChatRequest:
    # multipart 中 messages 是字符串，这里转回 JSON 并走 Pydantic 校验
    try:
        parsed_messages = json.loads(messages)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="messages 必须是合法 JSON") from exc
    try:
        return ChatRequest(
            colleague_id=colleague_id,
            messages=parsed_messages,
            web_search_enabled=web_search_enabled,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="聊天请求参数无效") from exc


def _build_messages(
    history: list[dict[str, Any]],
    system: str,
    web_results: list[dict[str, str]] | None,
) -> list[dict[str, Any]]:
    # 1) 过滤并裁剪历史，控制上下文长度
    filtered = _filter_history_for_api(history)
    if len(filtered) > MAX_API_HISTORY_MESSAGES:
        filtered = filtered[-MAX_API_HISTORY_MESSAGES:]
    # 2) 先放 system（包含基础人设 + RAG + FILES）
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    tail = copy.deepcopy(filtered)
    # 3) 若有联网结果，仅改写最后一条 user 内容（保持历史结构不变）
    if web_results is not None and tail and tail[-1].get("role") == "user":
        tail[-1]["content"] = build_augmented_user_content(tail[-1]["content"], web_results)

    # 4) 拼接最终 messages
    for m in tail:
        messages.append({"role": m["role"], "content": m["content"]})
    return messages


def _run_chat_worker(
    colleague_id: str,
    history: list[dict[str, Any]],
    settings: dict,
    rag_context: str,
    file_context: str,
    web_results: list[dict[str, str]] | None,
    queue: asyncio.Queue,
    cancel_event: threading.Event,
):
    """Runs in a background thread; pumps SSE events into the async queue."""

    def on_status(msg: str):
        # 线程内状态消息 -> SSE 队列
        try:
            queue.put_nowait(("status", msg))
        except Exception:
            pass

    def on_stream_opened(stream: Any):
        # 保存流对象，供 /chat/stop 或新请求中断
        _active_streams[colleague_id] = {
            "cancel": cancel_event,
            "stream": stream,
        }

    def should_cancel() -> bool:
        # 提供给底层 LLM 流读取循环的取消信号
        return cancel_event.is_set()

    try:
        c = None
        builtin = builtin_skill_dir()
        skill_lib_path = project_root() / "skill_lib"
        all_c = discover_colleagues(str(skill_lib_path), builtin)
        c = next((x for x in all_c if x.colleague_id == colleague_id), None)
        if not c:
            queue.put_nowait(("error", "Colleague not found"))
            return

        # 组装最终 system（基础 prompt + RAG + FILES）
        system = _append_file_context(_append_rag_context(build_system_prompt(c.skill_path), rag_context), file_context)
        # 组装最终 messages（必要时把联网检索块并入最后一条 user）
        messages = _build_messages(
            history,
            system,
            web_results,
        )

        # 启动前再检查一次取消，避免无意义请求
        if cancel_event.is_set():
            queue.put_nowait(("done", None))
            return

        # 发起流式 LLM 请求
        stream = stream_chat_completion(
            api_base=settings["api_base"],
            api_key=settings["api_key"],
            model=settings["model"],
            messages=messages,
            on_status=on_status,
            on_stream_opened=on_stream_opened,
            should_cancel=should_cancel,
        )
        # 把模型增量片段持续推入队列供 SSE 输出
        for chunk in stream:
            if cancel_event.is_set():
                break
            queue.put_nowait(("chunk", chunk))
        queue.put_nowait(("done", None))
    except Exception as e:
        queue.put_nowait(("error", str(e)))
    finally:
        _active_streams.pop(colleague_id, None)


@router.post("/chat")
async def chat(
    request: Request,
    colleague_id: str = Form(...),
    messages: str = Form(...),
    web_search_enabled: bool = Form(False),
    files: list[UploadFile] | None = File(None),
):
    # 解析 multipart 参数并做结构校验
    body = _parse_chat_request(colleague_id, messages, web_search_enabled)
    # 拉取用户设置与目标同事
    settings = _get_user_settings(request)
    _get_colleague(request, body.colleague_id)

    # 前置硬校验：必须有 API key；文件数量不能超过上限
    if not settings["api_key"].strip():
        raise HTTPException(status_code=400, detail="API 密钥未配置")
    if files and len(files) > 3:
        raise HTTPException(status_code=400, detail="最多上传 3 个文件")

    # 同一 colleague 只允许一个活跃流：新请求先中断旧流
    existing = _active_streams.pop(body.colleague_id, None)
    if existing:
        existing["cancel"].set()
        s = existing.get("stream")
        if s is not None:
            try:
                close = getattr(s, "close", None)
                if callable(close):
                    close()
            except Exception:
                pass

    # 用异步队列承接线程侧事件，再以 SSE 输出给前端
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    cancel_event = threading.Event()
    # 运行时能力与上下文基础数据
    runtime = getattr(request.app.state, "rag_runtime", None)
    last_user_message = _last_user_message(body.messages)

    async def _event_generator():
        t: threading.Thread | None = None
        try:
            # 这些上下文会按 pipeline 顺序逐步填充
            rag_context = ""
            file_context = ""
            web_results: list[dict[str, str]] | None = None
            rag_sources: list[dict[str, Any]] = []
            # 1) 先做 RAG（如果可用）
            if runtime is not None and last_user_message:
                try:
                    def on_rag_status(message: str) -> None:
                        # RAG 阶段状态透传给前端
                        queue.put_nowait(("status", message))

                    rag_task = asyncio.create_task(runtime.retriever.retrieve_context_with_sources(
                        skill_id=body.colleague_id,
                        query=last_user_message,
                        on_status=on_rag_status,
                    ))
                    while not rag_task.done():
                        # RAG 进行中时持续吐状态，不阻塞前端进度条
                        try:
                            event_type, data = await asyncio.wait_for(queue.get(), timeout=0.2)
                        except asyncio.TimeoutError:
                            continue
                        if event_type == "status":
                            yield f"data: {json.dumps({'type': 'status', 'message': data}, ensure_ascii=False)}\n\n"
                    rag_context, source_docs = await rag_task
                    rag_sources = [doc.model_dump(mode="json") for doc in source_docs]
                except Exception:
                    # RAG 异常不打断主流程，降级继续
                    yield f"data: {json.dumps({'type': 'status', 'message': 'RAG 检索不可用，已跳过知识库检索…'}, ensure_ascii=False)}\n\n"

            # 把 RAG 阶段残留状态消息先清空
            while not queue.empty():
                event_type, data = queue.get_nowait()
                if event_type == "status":
                    yield f"data: {json.dumps({'type': 'status', 'message': data}, ensure_ascii=False)}\n\n"

            # 回传 RAG 命中文档列表供前端展示引用
            if rag_sources:
                yield f"data: {json.dumps({'type': 'rag_sources', 'sources': rag_sources}, ensure_ascii=False)}\n\n"

            # 2) 再做联网搜索（提词 + 多路检索）
            if body.web_search_enabled and last_user_message and not cancel_event.is_set():
                try:
                    def on_web_status(message: str) -> None:
                        # 联网阶段状态透传给前端
                        queue.put_nowait(("status", message))

                    web_task = asyncio.create_task(asyncio.to_thread(
                        search_web_with_keywords,
                        last_user_message,
                        api_base=settings["api_base"],
                        api_key=settings["api_key"],
                        model=settings["model"],
                        web_search_url=settings["web_search_url"],
                        web_search_api_key=settings["web_search_api_key"],
                        on_status=on_web_status,
                    ))
                    while not web_task.done():
                        # 联网进行中持续输出状态
                        try:
                            event_type, data = await asyncio.wait_for(queue.get(), timeout=0.2)
                        except asyncio.TimeoutError:
                            continue
                        if event_type == "status":
                            yield f"data: {json.dumps({'type': 'status', 'message': data}, ensure_ascii=False)}\n\n"
                    web_results = await web_task
                    # 回传联网来源供前端引用面板展示
                    yield f"data: {json.dumps({'type': 'web_sources', 'sources': web_results}, ensure_ascii=False)}\n\n"
                except WebSearchError:
                    # 联网失败降级，不中断主流程
                    yield f"data: {json.dumps({'type': 'status', 'message': '联网搜索不可用，已直接回答…'}, ensure_ascii=False)}\n\n"

            # 3) 再做文件解析（异步、失败跳过）
            if files:
                try:
                    file_context = await build_chat_file_context(
                        files,
                        on_status=lambda message: queue.put_nowait(("status", message)),
                    )
                except ChatFileValidationError as exc:
                    # 数量/大小/格式这类硬校验失败，直接返回错误
                    yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
                    return

            # 把联网/文件阶段积压状态继续刷给前端
            while not queue.empty():
                event_type, data = queue.get_nowait()
                if event_type == "status":
                    yield f"data: {json.dumps({'type': 'status', 'message': data}, ensure_ascii=False)}\n\n"

            # 4) 启动后台线程发起 LLM 流式推理
            t = threading.Thread(
                target=_run_chat_worker,
                args=(
                    body.colleague_id,
                    body.messages,
                    settings,
                    rag_context,
                    file_context,
                    web_results,
                    queue,
                    cancel_event,
                ),
                daemon=True,
            )
            t.start()

            # 持续消费线程事件并转换成 SSE 包
            while True:
                try:
                    event_type, data = await asyncio.wait_for(queue.get(), timeout=300.0)
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'error', 'message': '请求超时'})}\n\n"
                    break

                if event_type == "chunk":
                    yield f"data: {json.dumps({'type': 'chunk', 'content': data})}\n\n"
                elif event_type == "status":
                    yield f"data: {json.dumps({'type': 'status', 'message': data})}\n\n"
                elif event_type == "web_sources":
                    yield f"data: {json.dumps({'type': 'web_sources', 'sources': data}, ensure_ascii=False)}\n\n"
                elif event_type == "error":
                    yield f"data: {json.dumps({'type': 'error', 'message': data})}\n\n"
                    break
                elif event_type == "done":
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    break
        except Exception as e:
            # 兜底异常，避免生成器无响应
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            # 结束时统一清理取消标记和活跃流状态
            cancel_event.set()
            _active_streams.pop(body.colleague_id, None)

    return StreamingResponse(_event_generator(), media_type="text/event-stream")


@router.post("/chat/stop")
async def stop_chat(body: ChatStopRequest):
    # 手动停止当前 colleague 的流式生成
    existing = _active_streams.pop(body.colleague_id, None)
    if existing:
        existing["cancel"].set()
        s = existing.get("stream")
        if s is not None:
            try:
                close = getattr(s, "close", None)
                if callable(close):
                    close()
            except Exception:
                pass
    return {"success": True}
