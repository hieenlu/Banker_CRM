"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.routers import (
    auth_router,
    clients_router,
    health_router,
    incomes_router,
    investments_router,
    news_router,
    newspaper_router,
    reminders_router,
)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.title,
        version=settings.version,
        description=(
            "Phase 2 HTTP API over Banker CRM + intel news models. "
            "Uses the same CRM_DB_URL as Streamlit (SQLite locally, Postgres in prod)."
        ),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(clients_router)
    application.include_router(investments_router)
    application.include_router(incomes_router)
    application.include_router(reminders_router)
    application.include_router(news_router)
    application.include_router(newspaper_router)

    @application.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": settings.title,
            "version": settings.version,
            "docs": "/docs",
            "health": "/health",
        }

    return application


app = create_app()
