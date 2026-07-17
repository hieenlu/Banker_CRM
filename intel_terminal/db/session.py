"""Table initialization (uses shared CRM SQLite engine)."""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from intel_terminal.db.models import (  # noqa: F401 — register mappers on Base
    Article,
    ArticleBookmark,
    ArticleSummary,
    DailyNewspaper,
    PipelineRun,
)
from models import Base


def init_intel_tables(engine: Engine) -> None:
    """Create intel_* tables if missing."""
    Base.metadata.create_all(bind=engine, tables=[
        Article.__table__,
        ArticleSummary.__table__,
        ArticleBookmark.__table__,
        DailyNewspaper.__table__,
        PipelineRun.__table__,
    ])


def intel_tables_present(engine: Engine) -> bool:
    names = set(inspect(engine).get_table_names())
    return "intel_articles" in names
