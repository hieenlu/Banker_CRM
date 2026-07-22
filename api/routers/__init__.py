"""API routers package."""

from api.routers.auth import router as auth_router
from api.routers.clients import router as clients_router
from api.routers.health import router as health_router
from api.routers.news import news_router, newspaper_router
from api.routers.portfolio import incomes_router, investments_router, reminders_router

__all__ = [
    "auth_router",
    "clients_router",
    "health_router",
    "news_router",
    "newspaper_router",
    "incomes_router",
    "investments_router",
    "reminders_router",
]
