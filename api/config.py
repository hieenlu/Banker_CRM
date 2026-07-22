"""API settings from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from database import default_db_path


@dataclass(frozen=True)
class ApiSettings:
    db_url: str
    api_user: str
    api_password: str
    jwt_secret: str
    jwt_algorithm: str
    jwt_expire_minutes: int
    cors_origins: tuple[str, ...]
    title: str = "Banker CRM API"
    version: str = "0.2.0"


def _csv_tuple(raw: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not raw or not raw.strip():
        return default
    items = tuple(part.strip() for part in raw.split(",") if part.strip())
    return items or default


@lru_cache(maxsize=1)
def get_settings() -> ApiSettings:
    db_url = os.environ.get("CRM_DB_URL", "").strip() or f"sqlite:///{default_db_path()}"
    return ApiSettings(
        db_url=db_url,
        api_user=os.environ.get("CRM_API_USER", "banker").strip() or "banker",
        api_password=os.environ.get("CRM_API_PASSWORD", "changeme").strip() or "changeme",
        jwt_secret=os.environ.get("CRM_JWT_SECRET", "dev-insecure-change-me").strip()
        or "dev-insecure-change-me",
        jwt_algorithm=os.environ.get("CRM_JWT_ALGORITHM", "HS256").strip() or "HS256",
        jwt_expire_minutes=int(os.environ.get("CRM_JWT_EXPIRE_MINUTES", "720") or "720"),
        cors_origins=_csv_tuple(
            os.environ.get("CRM_API_CORS_ORIGINS"),
            ("http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8501"),
        ),
    )


def clear_settings_cache() -> None:
    get_settings.cache_clear()


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent
