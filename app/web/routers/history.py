"""Chat history persistence routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.chat_history_store import (
    chat_histories_path,
    load_chat_histories,
    save_chat_histories,
)
from app.paths import config_dir
from app.web.schemas import MessageEntry

router = APIRouter()


def _get_user_id(request: Request) -> int:
    """Get user_id from cookie, raise 401 if not logged in."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    return int(user_id)


def _hist_path(user_id: int):
    return chat_histories_path(config_dir(), user_id)


@router.get("/histories")
async def get_histories(request: Request):
    user_id = _get_user_id(request)
    return load_chat_histories(_hist_path(user_id))


@router.post("/histories/{colleague_id}/messages")
async def add_message(colleague_id: str, entry: MessageEntry, request: Request):
    user_id = _get_user_id(request)
    path = _hist_path(user_id)
    data = load_chat_histories(path)
    hist = data.setdefault(colleague_id, [])
    import time
    hist.append({
        "role": entry.role,
        "content": entry.content,
        "ts": entry.ts or time.time(),
    })
    save_chat_histories(path, data)
    return {"success": True}


@router.post("/histories/{colleague_id}/clear")
async def clear_history(colleague_id: str, request: Request):
    user_id = _get_user_id(request)
    path = _hist_path(user_id)
    data = load_chat_histories(path)
    if colleague_id in data:
        data[colleague_id] = []
    save_chat_histories(path, data)
    return {"success": True}
