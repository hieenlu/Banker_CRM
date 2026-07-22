"""Health check routes."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from api.config import get_settings
from api.deps import DbSession
from api.schemas.common import HealthResponse
from database import is_postgres_url, is_sqlite_url, normalize_db_url

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(session: DbSession) -> HealthResponse:
    settings = get_settings()
    db_url = normalize_db_url(settings.db_url)
    if is_postgres_url(db_url):
        dialect = "postgres"
    elif is_sqlite_url(db_url):
        dialect = "sqlite"
    else:
        dialect = "other"

    db_ok = False
    try:
        session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=settings.version,
        database=dialect,
        db_ok=db_ok,
    )
