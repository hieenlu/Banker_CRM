"""Portfolio view / price refresh / news refresh API checks."""

from __future__ import annotations

import os
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("CRM_API_USER", "banker")
os.environ.setdefault("CRM_API_PASSWORD", "test-pass")
os.environ.setdefault("CRM_JWT_SECRET", "test-jwt-secret-at-least-32-bytes-long")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("CRM_DB_URL", url)
    monkeypatch.setenv("CRM_API_USER", "banker")
    monkeypatch.setenv("CRM_API_PASSWORD", "test-pass")
    monkeypatch.setenv("CRM_JWT_SECRET", "test-jwt-secret-at-least-32-bytes-long")
    monkeypatch.setenv("CRM_STORAGE_BACKEND", "local")
    monkeypatch.setenv("CRM_LOCAL_STORAGE_PATH", str(tmp_path / "files"))

    from api.config import clear_settings_cache
    from api.deps import reset_db_state
    from api.main import create_app
    from database import init_db
    from models import Client, Investment

    clear_settings_cache()
    reset_db_state()
    init_db(url)
    engine = create_engine(
        url, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Session = sessionmaker(bind=engine)
    with Session() as session:
        c = Client(name="Test Client")
        session.add(c)
        session.flush()
        session.add(
            Investment(
                client_id=c.id,
                asset_type="VN_Stock",
                ticker_name="VNM",
                ticker_identifier="VNM",
                quantity=100,
                unit=100,
                purchase_price=70.0,
                currency="VND",
                is_done=False,
            )
        )
        session.add(
            Investment(
                client_id=c.id,
                asset_type="Bond",
                ticker_name="TCB Bond",
                ticker_identifier="TCB-BOND",
                quantity=1,
                unit=1,
                principal=100_000_000,
                purchase_price=0,
                currency="VND",
                expected_coupon=5_000_000,
                is_done=False,
            )
        )
        session.add(
            Investment(
                client_id=c.id,
                asset_type="US_Stock",
                ticker_name="AAPL",
                ticker_identifier="AAPL",
                quantity=10,
                unit=10,
                purchase_price=150.0,
                currency="USD",
                is_done=False,
            )
        )
        session.commit()

    app = create_app()
    with TestClient(app) as tc:
        yield tc
    clear_settings_cache()
    reset_db_state()


def _token(client: TestClient) -> str:
    r = client.post("/auth/login", json={"username": "banker", "password": "test-pass"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_portfolio_view_groups_by_asset_type(client: TestClient):
    token = _token(client)
    r = client.get(
        "/portfolio/view",
        params={"display_currency": "VND", "is_done": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["display_currency"] == "VND"
    assert "totals" in data
    names = []
    for g in data["groups"]:
        for s in g["subgroups"]:
            names.append(s["name"])
            assert s["columns"]
            assert s["rows"]
    assert "VN_Stock" in names
    assert "Bond" in names
    assert "US_Stock" in names


def test_refresh_prices_endpoint(client: TestClient, monkeypatch):
    token = _token(client)

    def fake_fetch(tickers, **kwargs):
        return {t: 80.0 for t in tickers}

    monkeypatch.setattr("fetch_prices.fetch_latest_prices", fake_fetch)
    r = client.post(
        "/investments/refresh-prices",
        params={"is_done": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["requested"] >= 1
    assert body["updated"] >= 1

    view = client.get(
        "/portfolio/view",
        params={"is_done": False},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    # After refresh, VN stock should have a current price and non-zero PnL path
    vn = next(
        s
        for g in view["groups"]
        for s in g["subgroups"]
        if s["name"] == "VN_Stock"
    )
    assert vn["rows"][0]["Current Price"] == 80.0


def test_news_refresh_endpoint(client: TestClient, monkeypatch):
    token = _token(client)

    class FakeResult:
        status = "ok"
        articles_fetched = 3
        articles_new = 1
        articles_deduped = 2
        articles_classified = 3
        errors: list[str] = []

    monkeypatch.setattr(
        "api.routers.news.run_ingest_pipeline",
        lambda *a, **k: FakeResult(),
    )
    r = client.post(
        "/news/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["fetched"] == 3
    assert r.json()["new_count"] == 1
