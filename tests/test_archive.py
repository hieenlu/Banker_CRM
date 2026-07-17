"""Archive retention tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from intel_terminal.db.models import Article
from intel_terminal.db.session import init_intel_tables
from intel_terminal.pipeline.archive import (
    ARCHIVE_KEEP_LIMIT,
    count_archive_articles,
    delete_all_archive_articles,
    list_archive_articles,
    prune_archive_articles,
)
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


def _add(session, *, title: str, days_ago: int, region: str = "global") -> Article:
    when = datetime.utcnow() - timedelta(days=days_ago)
    row = Article(
        url_hash=f"hash-{title}-{days_ago}",
        url=f"https://example.com/{title}-{days_ago}",
        title=title,
        source="Test",
        published_at=when,
        fetched_at=when,
        body_text="body",
        body_fetch_status="snippet_only",
        region=region,
        category="Equities",
        mention_count=1,
    )
    session.add(row)
    session.flush()
    return row


def test_prune_keeps_fresh_and_caps_archive(db_session):
    # 5 fresh (<=14d) + 80 old
    for i in range(5):
        _add(db_session, title=f"Fresh {i}", days_ago=i)
    for i in range(80):
        _add(db_session, title=f"Old {i}", days_ago=20 + i)
    db_session.commit()

    result = prune_archive_articles(db_session, keep=50)
    db_session.commit()

    assert result.deleted == 30
    assert result.archive_remaining == 50
    assert result.fresh_remaining == 5
    assert count_archive_articles(db_session) == 50
    assert len(list_archive_articles(db_session)) == 50
    total = db_session.execute(select(func.count()).select_from(Article)).scalar_one()
    assert total == 55


def test_delete_all_archive_keeps_fresh(db_session):
    _add(db_session, title="Fresh", days_ago=1)
    _add(db_session, title="Old A", days_ago=30)
    _add(db_session, title="Old B", days_ago=40)
    db_session.commit()

    deleted = delete_all_archive_articles(db_session)
    db_session.commit()
    assert deleted == 2
    assert count_archive_articles(db_session) == 0
    total = db_session.execute(select(func.count()).select_from(Article)).scalar_one()
    assert total == 1


def test_archive_keep_constant():
    assert ARCHIVE_KEEP_LIMIT == 50
