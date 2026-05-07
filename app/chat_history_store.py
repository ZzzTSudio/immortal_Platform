"""Persistent chat histories keyed by colleague id (JSON in config dir)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CHAT_HISTORIES_FILENAME = "chat_histories.json"


def chat_histories_path(config_dir: Path, user_id: int | None = None) -> Path:
    """Get chat histories path. If user_id is provided, return user-specific path."""
    if user_id is not None:
        return config_dir / f"chat_histories_user_{user_id}.json"
    return config_dir / CHAT_HISTORIES_FILENAME


def load_chat_histories(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not isinstance(v, list):
            continue
        out[k] = [x for x in v if isinstance(x, dict)]
    return out


def save_chat_histories(path: Path, data: dict[str, list[dict[str, Any]]]) -> None:
    """Atomic write: tmp then replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
