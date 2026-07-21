"""Phase 1 Postgres helpers + sqlite→sqlite migration smoke test."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import is_postgres_url, is_sqlite_url, normalize_db_url
from models import Base, Client, Investment
from scripts.migrate_sqlite_to_postgres import TABLE_ORDER, migrate, verify_counts


def test_normalize_postgres_url_adds_psycopg():
    url = normalize_db_url("postgresql://user:pass@host/db?sslmode=require")
    assert url.startswith("postgresql+psycopg://")
    assert "sslmode=require" in url


def test_normalize_postgres_short_scheme():
    url = normalize_db_url("postgres://user:pass@host/db")
    assert url.startswith("postgresql+psycopg://")


def test_url_dialect_helpers():
    assert is_sqlite_url("sqlite:///tmp/x.db")
    assert is_postgres_url("postgresql://x")
    assert is_postgres_url("postgresql+psycopg://x")
    assert not is_postgres_url("sqlite:///x")


def test_migrate_sqlite_to_sqlite_preserves_rows(tmp_path: Path):
    src_path = tmp_path / "source.sqlite3"
    dst_path = tmp_path / "target.sqlite3"
    src_url = f"sqlite:///{src_path}"
    dst_url = f"sqlite:///{dst_path}"

    src_engine = create_engine(src_url)
    Base.metadata.create_all(src_engine)
    import intel_terminal.db.models  # noqa: F401

    Base.metadata.create_all(src_engine)
    SessionLocal = sessionmaker(bind=src_engine)
    with SessionLocal() as session:
        c = Client(name="Ada", email="ada@example.com", birthday=date(1990, 1, 1))
        session.add(c)
        session.flush()
        session.add(
            Investment(
                client_id=c.id,
                asset_type="Stock",
                ticker_identifier="AAPL",
                quantity=10,
                purchase_price=100,
                currency="USD",
            )
        )
        session.commit()

    counts = migrate(src_url, dst_url)
    by_name = {c.table: c for c in counts}
    assert by_name["clients"].source == 1
    assert by_name["clients"].ok
    assert by_name["investments"].source == 1
    assert by_name["investments"].ok

    # All known tables present in verify list
    assert [c.table for c in counts] == list(TABLE_ORDER)
    assert all(c.ok for c in verify_counts(src_url, dst_url))
