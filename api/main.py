"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.routers import (
    auth_router,
    clients_router,
    files_router,
    health_router,
    incomes_router,
    investments_router,
    news_router,
    newspaper_router,
    portfolio_view_router,
    reminders_router,
)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.title,
        version=settings.version,
        description=(
            "Banker CRM + intel news API with S3-compatible file storage. "
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
    application.include_router(portfolio_view_router)
    application.include_router(news_router)
    application.include_router(newspaper_router)
    application.include_router(files_router)

    @application.middleware("http")
    async def prevent_private_file_caching(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/files/") or "/attachments" in path or path.endswith(
            "/export.zip"
        ):
            response.headers["Cache-Control"] = "private, no-store"
        return response

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
