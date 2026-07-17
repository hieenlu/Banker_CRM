"""Repository upsert tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from intel_terminal.db.repository import upsert_article_draft
from intel_terminal.db.session import init_intel_tables
from intel_terminal.pipeline.normalize import ArticleDraft, normalize_url, to_naive_utc, url_hash
from models import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    init_intel_tables(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _draft(url: str, published_at: datetime | None) -> ArticleDraft:
    return ArticleDraft(
        url=url,
        url_hash=url_hash(url),
        canonical_url=normalize_url(url),
        title="Fed holds rates steady amid inflation concerns",
        source="Test",
        published_at=published_at,
        body_text="snippet",
        body_fetch_status="snippet_only",
        region="global",
        language="en",
        feed_key="test",
        source_quality=0.7,
    )


def test_upsert_compares_aware_draft_with_naive_row(db_session):
    naive = datetime(2026, 6, 1, 10, 0)
    aware_newer = datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
    _, is_new = upsert_article_draft(db_session, _draft("https://example.com/a", naive))
    assert is_new is True
    db_session.commit()

    row, is_new = upsert_article_draft(db_session, _draft("https://example.com/a", aware_newer))
    assert is_new is False
    assert row.published_at == to_naive_utc(aware_newer)
