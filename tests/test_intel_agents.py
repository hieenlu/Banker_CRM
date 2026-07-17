"""Module 4: agents, cache, newspaper fallback."""

from __future__ import annotations

import json
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from intel_terminal.agents.base import AgentOutput, extract_json_object, parse_agent_response
from intel_terminal.agents.newspaper import generate_daily_newspaper
from intel_terminal.agents.prompts import pick_agent_for_article
from intel_terminal.agents.summarize import run_summary_pipeline, summarize_article
from intel_terminal.db.models import Article
from intel_terminal.db.session import init_intel_tables
from intel_terminal.llm.base import LLMResponse
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


def test_extract_json_from_fence():
    raw = 'Here is output:\n```json\n{"headline": "Test", "summary": "Ok"}\n```'
    data = extract_json_object(raw)
    assert data["headline"] == "Test"


def test_parse_agent_response():
    text = json.dumps(
        {
            "headline": "Fed on hold",
            "summary": "Rates unchanged.",
            "key_points": ["Hawkish tone"],
            "sentiment": "neutral",
            "client_talking_point": "Discuss duration risk.",
            "confidence": 0.8,
        }
    )
    out = parse_agent_response(text, agent_type="macro", article_id=1)
    assert out.headline == "Fed on hold"
    assert out.agent_type == "macro"


def test_pick_agent_vietnam_banking():
    agent = pick_agent_for_article(
        "Vietnam",
        "vietnam",
        vietnam_banking_score=0.6,
        vietnam_macro_score=0.2,
    )
    assert agent == "vietnam_banking"


def test_pick_agent_crypto():
    assert pick_agent_for_article("Crypto", "global") == "crypto"


def test_summarize_uses_mock_llm(db_session: Session):
    article = Article(
        url_hash="h1",
        url="https://example.com/1",
        title="Bitcoin rallies on ETF inflows",
        source="CoinDesk",
        fetched_at=datetime.utcnow(),
        body_text="Crypto markets rose sharply.",
        body_fetch_status="snippet_only",
        category="Crypto",
        relevance_score=0.9,
        region="global",
    )
    db_session.add(article)
    db_session.flush()

    mock_llm = MagicMock()
    mock_llm.is_configured.return_value = True
    mock_llm.model = "test-model"
    mock_llm.name = "openai"
    mock_llm.complete.return_value = LLMResponse(
        text=json.dumps(
            {
                "headline": "BTC rally",
                "summary": "ETF flows drive gains.",
                "key_points": ["Inflows"],
                "sentiment": "bullish",
                "client_talking_point": "Review crypto sleeve.",
                "confidence": 0.7,
            }
        ),
        provider="openai",
        model="test-model",
        input_tokens=100,
        output_tokens=50,
    )

    out = summarize_article(db_session, article, agent_type="crypto", llm=mock_llm)
    assert out is not None
    assert out.summary.startswith("ETF")

    # cache hit on second call
    mock_llm.complete.reset_mock()
    out2 = summarize_article(db_session, article, agent_type="crypto", llm=mock_llm)
    mock_llm.complete.assert_not_called()
    assert out2.summary == out.summary


def test_newspaper_fallback_without_api_key(db_session: Session):
    for i in range(3):
        db_session.add(
            Article(
                url_hash=f"h{i}",
                url=f"https://example.com/{i}",
                title=f"Market story {i} rally",
                source="CNBC",
                fetched_at=datetime.utcnow(),
                category="Equities",
                relevance_score=0.8 - i * 0.1,
                region="global",
            )
        )
    db_session.flush()

    mock_llm = MagicMock()
    mock_llm.is_configured.return_value = False

    result = generate_daily_newspaper(
        db_session,
        report_date=date(2026, 6, 1),
        llm=mock_llm,
        force=True,
    )
    assert result.provider == "fallback"
    assert "executive_summary" in result.content
    assert result.content.get("mode") == "fallback"


def test_run_summary_pipeline_no_key(db_session: Session):
    mock_llm = MagicMock()
    mock_llm.is_configured.return_value = False
    r = run_summary_pipeline(db_session, llm=mock_llm)
    assert r.skipped_no_llm > 0
