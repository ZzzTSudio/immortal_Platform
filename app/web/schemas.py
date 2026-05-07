"""Pydantic schemas for web API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    colleague_id: str
    messages: list[dict[str, str]]
    web_search_enabled: bool = False


class ChatStopRequest(BaseModel):
    colleague_id: str
    messages: list[dict[str, str]] = Field(default_factory=list)
    web_search_enabled: bool = False


class MessageEntry(BaseModel):
    role: Literal["user", "assistant", "sticker"]
    content: str
    ts: float | None = None


class SettingsUpdate(BaseModel):
    api_base: str | None = None
    api_key: str | None = None
    model: str | None = None
    user_avatar_path: str | None = None
    chat_font_size: int | None = None
    ollama_web_search_url: str | None = None
    ollama_web_search_api_key: str | None = None


class ImportSkillRequest(BaseModel):
    source_dir: str
    display_name: str


class RenameSkillRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=8)


class TestApiRequest(BaseModel):
    api_base: str
    api_key: str
    model: str


class TestWebSearchRequest(BaseModel):
    url: str
    api_key: str


class ApiResponse(BaseModel):
    success: bool
    message: str = ""
