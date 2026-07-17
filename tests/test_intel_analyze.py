"""Module 3: classify, rank, Vietnam scoring."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from intel_terminal.db.models import Article
from intel_terminal.db.session import init_intel_tables
from intel_terminal.pipeline.analyze import analyze_article, top_articles
from intel_terminal.pipeline.classify import classify_text
from intel_terminal.pipeline.rank import recency_factor
from intel_terminal.pipeline.vietnam import score_vietnam_relevance
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


def test_classify_fed_inflation():
    r = classify_text("Fed holds rates as inflation cools", "Powell cited progress on CPI.")
    assert r.category in {"Central Banks", "Inflation", "Global Macro"}
    assert r.confidence > 0


def test_classify_vietnam_banking():
    r = classify_text(
        "Techcombank profit rises on credit growth",
        source="CafeF",
        region="vietnam",
    )
    assert r.category == "Vietnam"
    assert r.confidence >= 0.3


def test_vietnam_scores_banking():
    vn = score_vietnam_relevance(
        "SBV keeps policy rate; banks see credit growth",
        region="vietnam",
        category="Vietnam",
    )
    assert vn.banking > 0.2
    assert vn.composite > 0.1


def test_relevance_recent_article_scores_higher():
    recent = recency_factor(datetime.utcnow())
    old = recency_factor(datetime.utcnow() - timedelta(days=5))
    assert recent > old


def test_top_articles_prefers_recent_window(db_session):
    old = Article(
        url_hash="old1",
        url="https://example.com/old",
        title="Old VN-Index article from last month",
        source="VnExpress",
        published_at=datetime.utcnow() - timedelta(days=30),
        fetched_at=datetime.utcnow() - timedelta(days=30),
        body_text="VN-Index banking rates",
        body_fetch_status="snippet_only",
        region="vietnam",
        category="Vietnam",
        relevance_score=0.95,
        mention_count=1,
    )
    new = Article(
        url_hash="new1",
        url="https://example.com/new",
        title="Fresh bank earnings beat today",
        source="CNBC Markets",
        published_at=datetime.utcnow() - timedelta(hours=2),
        fetched_at=datetime.utcnow(),
        body_text="Jamie Dimon JPMorgan earnings AI",
        body_fetch_status="snippet_only",
        region="global",
        category="Equities",
        relevance_score=0.55,
        mention_count=1,
    )
    db_session.add_all([old, new])
    db_session.commit()

    rows = top_articles(db_session, limit=10, max_age_hours=120, min_relevance=0.1)
    assert len(rows) == 1
    assert rows[0].url_hash == "new1"

    latest = top_articles(db_session, limit=10, max_age_hours=720, min_relevance=0.0, sort="latest")
    assert latest[0].url_hash == "new1"


def test_classify_vietnamese_headline():
    r = classify_text("Giá USD tự do về thấp hơn ngân hàng", region="vietnam", source="VnExpress")
    assert r.category == "Vietnam"
    assert r.confidence > 0


def test_classify_vietnam_feed_fallback():
    r = classify_text("Tin tức mới trong ngày", region="vietnam", source="VietnamNet")
    assert r.category == "Vietnam"
    assert r.confidence >= 0.45


def test_analyze_article_updates_fields():
    article = Article(
        url_hash="abc",
        url="https://example.com/1",
        title="Bitcoin surges as crypto markets rally",
        source="CoinDesk",
        fetched_at=datetime.utcnow(),
        body_text="Ethereum and BTC lead gains.",
        body_fetch_status="snippet_only",
        region="global",
        mention_count=2,
    )
    changed = analyze_article(article)
    assert changed
    assert article.category == "Crypto"
    assert article.relevance_score > 0.1
