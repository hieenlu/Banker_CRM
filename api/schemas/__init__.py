"""Schema package."""

from api.schemas.auth import LoginRequest, MeResponse, TokenResponse
from api.schemas.clients import ClientCreate, ClientOut, ClientUpdate
from api.schemas.common import HealthResponse, Message, Page
from api.schemas.files import StoredFileOut, TechcombankSyncResult
from api.schemas.news import (
    ArticleDetailOut,
    ArticleOut,
    BookmarkCreate,
    BookmarkOut,
    NewspaperOut,
)
from api.schemas.portfolio import (
    IncomeCreate,
    IncomeOut,
    IncomeUpdate,
    InvestmentCreate,
    InvestmentOut,
    InvestmentUpdate,
    ReminderCreate,
    ReminderOut,
    ReminderUpdate,
)

__all__ = [
    "LoginRequest",
    "MeResponse",
    "TokenResponse",
    "ClientCreate",
    "ClientOut",
    "ClientUpdate",
    "HealthResponse",
    "Message",
    "Page",
    "StoredFileOut",
    "TechcombankSyncResult",
    "ArticleDetailOut",
    "ArticleOut",
    "BookmarkCreate",
    "BookmarkOut",
    "NewspaperOut",
    "IncomeCreate",
    "IncomeOut",
    "IncomeUpdate",
    "InvestmentCreate",
    "InvestmentOut",
    "InvestmentUpdate",
    "ReminderCreate",
    "ReminderOut",
    "ReminderUpdate",
]
