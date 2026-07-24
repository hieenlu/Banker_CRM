"""Phase 2 FastAPI smoke tests."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Configure API env before importing the app.
_TEST_DB = Path(__file__).resolve().parent / "_phase2_api_test.sqlite3"
os.environ["CRM_DB_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["CRM_API_USER"] = "banker"
os.environ["CRM_API_PASSWORD"] = "test-pass"
os.environ["CRM_JWT_SECRET"] = "test-jwt-secret-at-least-32-bytes-long"

from api.config import clear_settings_cache  # noqa: E402
from api.deps import reset_db_state  # noqa: E402
from api.main import create_app  # noqa: E402
from database import get_session, init_db  # noqa: E402
from intel_terminal.db.models import Article, DailyNewspaper  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "api.sqlite3"
    monkeypatch.setenv("CRM_DB_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("CRM_API_USER", "banker")
    monkeypatch.setenv("CRM_API_PASSWORD", "test-pass")
    monkeypatch.setenv("CRM_JWT_SECRET", "test-jwt-secret-at-least-32-bytes-long")
    clear_settings_cache()
    reset_db_state()
    init_db(f"sqlite:///{db_path}")

    # Seed news + newspaper for read endpoints.
    with get_session(f"sqlite:///{db_path}") as session:
        session.add(
            Article(
                url_hash="abc123",
                url="https://example.com/a1",
                title="Fed holds rates steady",
                source="TestWire",
                published_at=datetime.utcnow(),
                fetched_at=datetime.utcnow(),
                body_text="Markets reacted calmly.",
                category="Economy",
                relevance_score=0.9,
                region="global",
            )
        )
        session.add(
            DailyNewspaper(
                report_date=date.today(),
                market_regime="Neutral",
                content_json='{"headline":"Quiet session"}',
                provider="test",
                model="test",
            )
        )

    app = create_app()
    with TestClient(app) as c:
        yield c
    clear_settings_cache()
    reset_db_state()


def _auth_headers(client: TestClient) -> dict[str, str]:
    resp = client.post("/auth/login", json={"username": "banker", "password": "test-pass"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["db_ok"] is True
    assert body["database"] == "sqlite"


def test_login_and_me(client: TestClient):
    bad = client.post("/auth/login", json={"username": "banker", "password": "wrong"})
    assert bad.status_code == 401

    headers = _auth_headers(client)
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "banker"


def test_clients_crud(client: TestClient):
    headers = _auth_headers(client)
    created = client.post("/clients", headers=headers, json={"name": "Ada Client", "email": "ada@example.com"})
    assert created.status_code == 201
    client_id = created.json()["id"]

    listed = client.get("/clients", headers=headers, params={"q": "Ada"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    patched = client.patch(
        f"/clients/{client_id}",
        headers=headers,
        json={"phone_number": "+1-555-0100"},
    )
    assert patched.status_code == 200
    assert patched.json()["phone_number"] == "+1-555-0100"

    deleted = client.delete(f"/clients/{client_id}", headers=headers)
    assert deleted.status_code == 200


def test_portfolio_crud(client: TestClient):
    headers = _auth_headers(client)
    c = client.post("/clients", headers=headers, json={"name": "Portfolio Person"}).json()
    inv = client.post(
        "/investments",
        headers=headers,
        json={
            "client_id": c["id"],
            "asset_type": "Stock",
            "ticker_identifier": "AAPL",
            "quantity": 10,
            "purchase_price": 100,
        },
    )
    assert inv.status_code == 201

    income = client.post(
        "/incomes",
        headers=headers,
        json={"client_id": c["id"], "income_type": "Salary", "amount": 5000},
    )
    assert income.status_code == 201

    reminder = client.post(
        "/reminders",
        headers=headers,
        json={
            "title": "Call client",
            "reminder_date": date.today().isoformat(),
            "client_id": c["id"],
        },
    )
    assert reminder.status_code == 201

    inv_list = client.get("/investments", headers=headers, params={"client_id": c["id"]})
    assert inv_list.json()["total"] >= 1


def test_news_and_newspaper(client: TestClient):
    headers = _auth_headers(client)
    articles = client.get("/news/articles", headers=headers)
    assert articles.status_code == 200
    assert articles.json()["total"] >= 1
    article_id = articles.json()["items"][0]["id"]

    detail = client.get(f"/news/articles/{article_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["title"]

    bm = client.post("/news/bookmarks", headers=headers, json={"article_id": article_id})
    assert bm.status_code == 201
    bookmarks = client.get("/news/bookmarks", headers=headers)
    assert bookmarks.json()["total"] >= 1

    today = client.get("/newspaper/today", headers=headers)
    assert today.status_code == 200
    assert today.json()["market_regime"] == "Neutral"


def test_x_feeds_get_and_refresh(client: TestClient, monkeypatch):
    headers = _auth_headers(client)

    empty = client.get("/news/x-feeds", headers=headers)
    assert empty.status_code == 200
    body = empty.json()
    assert body["items"] == []
    assert body["fetched_at"] is None
    assert "KobeissiLetter" in body["profiles"]

    sample = [
        {
            "headline": "BREAKING: Markets rally on soft CPI print.",
            "source": "X @KobeissiLetter",
            "date": "2026-07-24T00:00:00",
            "link": "https://x.com/KobeissiLetter/status/1",
            "handle": "KobeissiLetter",
            "tags": ["equities"],
        },
        {
            "headline": "AI capex still the center of the selloff.",
            "source": "X @citrini",
            "date": "2026-07-23T12:00:00",
            "link": "https://x.com/citrini/status/2",
            "handle": "citrini",
            "tags": ["equities"],
        },
    ]

    monkeypatch.setattr(
        "api.routers.news.scrape_x_analyst_feeds",
        lambda profiles=None, limit_per_profile=12: sample,
    )
    refreshed = client.post("/news/x-feeds/refresh", headers=headers)
    assert refreshed.status_code == 200, refreshed.text
    payload = refreshed.json()
    assert payload["count"] == 2
    assert payload["items"][0]["handle"] == "KobeissiLetter"
    assert payload["fetched_at"]

    cached = client.get("/news/x-feeds", headers=headers)
    assert cached.status_code == 200
    assert len(cached.json()["items"]) == 2
    assert cached.json()["fetched_at"]
    assert cached.json()["items"][1]["link"].endswith("/status/2")


def test_protected_routes_require_auth(client: TestClient):
    assert client.get("/clients").status_code == 401
    assert client.get("/news/articles").status_code == 401
    assert client.get("/news/x-feeds").status_code == 401
    assert client.post("/news/x-feeds/refresh").status_code == 401
