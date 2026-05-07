"""Application settings routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.database import get_user_settings, save_user_settings

from app.llm_client import _assistant_text_from_response
from app.openai_client import make_openai_client
from app.ollama_web_search import test_web_search_connection
from app.settings import DEFAULT_API_BASE, DEFAULT_MODEL, DEFAULT_OLLAMA_WEB_SEARCH_URL
from app.web.schemas import SettingsUpdate, TestApiRequest, TestWebSearchRequest, ApiResponse

router = APIRouter()


def _get_user_id(request: Request) -> int:
    """Get user_id from cookie, raise 401 if not logged in."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    return int(user_id)


@router.get("/settings")
async def get_settings(request: Request):
    user_id = _get_user_id(request)
    settings = get_user_settings(user_id)

    # Get user email
    from app.database import get_db_path
    import sqlite3
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    user_email = row["email"] if row else ""

    if not settings:
        # Return default values if no settings exist
        return {
            "api_base": DEFAULT_API_BASE,
            "api_key": "",
            "model": DEFAULT_MODEL,
            "user_avatar_path": "",
            "chat_font_size": 16,
            "ollama_web_search_url": DEFAULT_OLLAMA_WEB_SEARCH_URL,
            "ollama_web_search_api_key": "",
            "hidden_colleague_ids": [],
            "api_last_test_ok": None,
            "api_last_test_hash": "",
            "web_last_test_ok": None,
            "web_last_test_hash": "",
            "user_email": user_email,
        }

    return {
        "api_base": settings.get("api_base") or DEFAULT_API_BASE,
        "api_key": settings.get("api_key") or "",
        "model": settings.get("model") or DEFAULT_MODEL,
        "user_avatar_path": settings.get("avatar") or "",
        "chat_font_size": settings.get("font_size") or 16,
        "ollama_web_search_url": settings.get("web_search_url") or DEFAULT_OLLAMA_WEB_SEARCH_URL,
        "ollama_web_search_api_key": settings.get("web_search_api_key") or "",
        "hidden_colleague_ids": [],
        "api_last_test_ok": None,
        "api_last_test_hash": "",
        "web_last_test_ok": None,
        "web_last_test_hash": "",
        "user_email": user_email,
    }


@router.post("/settings")
async def update_settings(body: SettingsUpdate, request: Request):
    user_id = _get_user_id(request)
    settings = get_user_settings(user_id) or {}

    if body.api_base is not None:
        settings["api_base"] = body.api_base
    if body.api_key is not None:
        settings["api_key"] = body.api_key
    if body.model is not None:
        settings["model"] = body.model
    if body.user_avatar_path is not None:
        settings["avatar"] = body.user_avatar_path
    if body.chat_font_size is not None:
        settings["font_size"] = max(6, min(36, body.chat_font_size))
    if body.ollama_web_search_url is not None:
        settings["web_search_url"] = body.ollama_web_search_url
    if body.ollama_web_search_api_key is not None:
        settings["web_search_api_key"] = body.ollama_web_search_api_key

    save_user_settings(user_id, settings)
    return {"success": True}


@router.post("/settings/test-api")
async def test_api(body: TestApiRequest, request: Request):
    _get_user_id(request)  # Verify user is logged in
    try:
        client = make_openai_client(base_url=body.api_base, api_key=body.api_key)
        resp = client.chat.completions.create(
            model=body.model,
            messages=[{"role": "user", "content": "hi"}],
            stream=False,
        )
        text = _assistant_text_from_response(resp)
        return ApiResponse(success=True, message=f"连通成功。模型返回：{text[:60]}")
    except Exception as e:
        return ApiResponse(success=False, message=str(e))


@router.post("/settings/test-web-search")
async def test_web_search(body: TestWebSearchRequest, request: Request):
    _get_user_id(request)  # Verify user is logged in
    ok = test_web_search_connection(body.url, body.api_key)
    return ApiResponse(success=ok, message="连通成功" if ok else "连通失败")
