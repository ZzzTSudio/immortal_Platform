"""Environment-driven settings for the web service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _b(name: str, default: bool = False) -> bool:
    v = (os.environ.get(name) or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return default


def _i(name: str, default: int) -> int:
    try:
        return int((os.environ.get(name) or "").strip() or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class WebConfig:
    data_dir: Path
    database_url: str
    jwt_secret: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    default_api_base: str
    default_api_key: str
    default_model: str
    cors_origins: list[str]
    require_email_verification: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_use_tls: bool
    verification_code_ttl_minutes: int
    verification_resend_seconds: int


@lru_cache
def get_web_config() -> WebConfig:
    data = Path(os.environ.get("IMMORTAL_DATA_DIR", "data")).resolve()
    db = (os.environ.get("IMMORTAL_DATABASE_URL") or "").strip()
    if not db:
        db = f"sqlite:///{data / 'immortal.db'}"

    cors = (os.environ.get("IMMORTAL_CORS_ORIGINS") or "http://localhost:5173,http://127.0.0.1:5173").strip()
    origins = [x.strip() for x in cors.split(",") if x.strip()]

    return WebConfig(
        data_dir=data,
        database_url=db,
        jwt_secret=(os.environ.get("IMMORTAL_JWT_SECRET") or "change-me-in-production").strip(),
        jwt_algorithm="HS256",
        access_token_expire_minutes=_i("IMMORTAL_JWT_EXPIRE_MINUTES", 60 * 24 * 7),
        default_api_base=(os.environ.get("IMMORTAL_DEFAULT_API_BASE") or "https://api.siliconflow.cn/v1").strip(),
        default_api_key=(os.environ.get("IMMORTAL_DEFAULT_API_KEY") or "").strip(),
        default_model=(os.environ.get("IMMORTAL_DEFAULT_MODEL") or "Pro/moonshotai/Kimi-K2.5").strip(),
        cors_origins=origins,
        require_email_verification=_b("IMMORTAL_REQUIRE_EMAIL_VERIFICATION", True),
        smtp_host=(os.environ.get("IMMORTAL_SMTP_HOST") or "").strip(),
        smtp_port=_i("IMMORTAL_SMTP_PORT", 587),
        smtp_user=(os.environ.get("IMMORTAL_SMTP_USER") or "").strip(),
        smtp_password=(os.environ.get("IMMORTAL_SMTP_PASSWORD") or "").strip(),
        smtp_from=(os.environ.get("IMMORTAL_SMTP_FROM") or "").strip(),
        smtp_use_tls=_b("IMMORTAL_SMTP_USE_TLS", True),
        verification_code_ttl_minutes=_i("IMMORTAL_VERIFICATION_CODE_TTL_MINUTES", 15),
        verification_resend_seconds=_i("IMMORTAL_VERIFICATION_RESEND_SECONDS", 60),
    )


def ensure_data_dirs(cfg: WebConfig) -> None:
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    (cfg.data_dir / "users").mkdir(parents=True, exist_ok=True)
