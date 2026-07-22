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
    storage_backend: str
    local_storage_path: Path
    s3_endpoint_url: str
    s3_region: str
    s3_bucket: str
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_prefix: str
    signed_url_ttl_seconds: int
    max_upload_bytes: int
    max_export_bytes: int
    allowed_upload_types: tuple[str, ...]
    title: str = "Banker CRM API"
    version: str = "0.3.0"


def _csv_tuple(raw: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not raw or not raw.strip():
        return default
    items = tuple(part.strip() for part in raw.split(",") if part.strip())
    return items or default


@lru_cache(maxsize=1)
def get_settings() -> ApiSettings:
    db_url = os.environ.get("CRM_DB_URL", "").strip() or f"sqlite:///{default_db_path()}"
    project_dir = Path(__file__).resolve().parent.parent
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
        storage_backend=os.environ.get("CRM_STORAGE_BACKEND", "local").strip().lower()
        or "local",
        local_storage_path=Path(
            os.environ.get("CRM_LOCAL_STORAGE_PATH", str(project_dir / "data" / "files"))
        ),
        s3_endpoint_url=os.environ.get("CRM_S3_ENDPOINT_URL", "").strip(),
        s3_region=os.environ.get("CRM_S3_REGION", "auto").strip() or "auto",
        s3_bucket=os.environ.get("CRM_S3_BUCKET", "").strip(),
        s3_access_key_id=os.environ.get("CRM_S3_ACCESS_KEY_ID", "").strip(),
        s3_secret_access_key=os.environ.get("CRM_S3_SECRET_ACCESS_KEY", "").strip(),
        s3_prefix=os.environ.get("CRM_S3_PREFIX", "banker-crm").strip().strip("/")
        or "banker-crm",
        signed_url_ttl_seconds=max(
            60, min(int(os.environ.get("CRM_S3_SIGNED_URL_TTL_SECONDS", "3600")), 86400)
        ),
        max_upload_bytes=max(
            1024, int(os.environ.get("CRM_S3_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
        ),
        max_export_bytes=max(
            1024, int(os.environ.get("CRM_MAX_EXPORT_BYTES", str(100 * 1024 * 1024)))
        ),
        allowed_upload_types=_csv_tuple(
            os.environ.get("CRM_ALLOWED_UPLOAD_TYPES"),
            (
                "application/pdf",
                "image/jpeg",
                "image/png",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "text/plain",
            ),
        ),
    )


def clear_settings_cache() -> None:
    get_settings.cache_clear()


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent
