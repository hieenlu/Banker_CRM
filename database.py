from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from models import Base


def default_db_path() -> Path:
    # Store the SQLite DB alongside the code files.
    return Path(__file__).resolve().parent / "banker_crm.sqlite3"


def app_settings_path() -> Path:
    return Path(__file__).resolve().parent / "crm_settings.json"


def load_app_settings() -> dict[str, Any]:
    p = app_settings_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_app_settings(data: dict[str, Any]) -> None:
    p = app_settings_path()
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def save_usd_vnd_rate(rate: float) -> None:
    data = load_app_settings()
    data["usd_vnd_rate"] = float(rate)
    save_app_settings(data)


def make_engine(db_url: str):
    # check_same_thread=False helps Streamlit; sqlite file is local.
    return create_engine(db_url, connect_args={"check_same_thread": False})


def init_db(db_url: str) -> None:
    engine = make_engine(db_url)
    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations(engine)
    try:
        from intel_terminal.db.session import init_intel_tables

        init_intel_tables(engine)
    except ImportError:
        pass


def _run_lightweight_migrations(engine) -> None:
    # Keep existing local SQLite files compatible without requiring Alembic.
    inspector = inspect(engine)
    if "clients" in inspector.get_table_names():
        existing_clients = {c["name"] for c in inspector.get_columns("clients")}
        with engine.begin() as conn:
            if "home_insurance_amount_covered" not in existing_clients:
                conn.execute(text("ALTER TABLE clients ADD COLUMN home_insurance_amount_covered NUMERIC(20, 6)"))
            if "home_insurance_expiry_date" not in existing_clients:
                conn.execute(text("ALTER TABLE clients ADD COLUMN home_insurance_expiry_date DATE"))
            if "home_insurance_insured_premium" not in existing_clients:
                conn.execute(text("ALTER TABLE clients ADD COLUMN home_insurance_insured_premium NUMERIC(20, 6)"))
            if "salary_amount" not in existing_clients:
                conn.execute(text("ALTER TABLE clients ADD COLUMN salary_amount NUMERIC(20, 6)"))
            if "salary_concurrent" not in existing_clients:
                conn.execute(text("ALTER TABLE clients ADD COLUMN salary_concurrent BOOLEAN NOT NULL DEFAULT 0"))
            if "salary_note" not in existing_clients:
                conn.execute(text("ALTER TABLE clients ADD COLUMN salary_note TEXT"))
            if "dividends_amount" not in existing_clients:
                conn.execute(text("ALTER TABLE clients ADD COLUMN dividends_amount NUMERIC(20, 6)"))
            if "dividends_concurrent" not in existing_clients:
                conn.execute(text("ALTER TABLE clients ADD COLUMN dividends_concurrent BOOLEAN NOT NULL DEFAULT 0"))
            if "dividends_note" not in existing_clients:
                conn.execute(text("ALTER TABLE clients ADD COLUMN dividends_note TEXT"))
            if "others_income_amount" not in existing_clients:
                conn.execute(text("ALTER TABLE clients ADD COLUMN others_income_amount NUMERIC(20, 6)"))
            if "others_income_concurrent" not in existing_clients:
                conn.execute(text("ALTER TABLE clients ADD COLUMN others_income_concurrent BOOLEAN NOT NULL DEFAULT 0"))
            if "others_income_note" not in existing_clients:
                conn.execute(text("ALTER TABLE clients ADD COLUMN others_income_note TEXT"))

    if "investments" not in inspector.get_table_names():
        return

    if "incomes" in inspector.get_table_names():
        existing_incomes = {c["name"] for c in inspector.get_columns("incomes")}
        with engine.begin() as conn:
            if "income_mode" not in existing_incomes:
                conn.execute(text("ALTER TABLE incomes ADD COLUMN income_mode VARCHAR(20) NOT NULL DEFAULT 'Actual'"))
            if "is_done" not in existing_incomes:
                conn.execute(text("ALTER TABLE incomes ADD COLUMN is_done BOOLEAN NOT NULL DEFAULT 0"))

    existing = {c["name"] for c in inspector.get_columns("investments")}
    with engine.begin() as conn:
        if "ticker_name" not in existing:
            conn.execute(text("ALTER TABLE investments ADD COLUMN ticker_name VARCHAR(200)"))
        if "currency" not in existing:
            conn.execute(text("ALTER TABLE investments ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'USD'"))
        if "principal" not in existing:
            conn.execute(text("ALTER TABLE investments ADD COLUMN principal NUMERIC(20, 6)"))
        if "unit" not in existing:
            conn.execute(text("ALTER TABLE investments ADD COLUMN unit FLOAT"))
        if "interest_rate" not in existing:
            conn.execute(text("ALTER TABLE investments ADD COLUMN interest_rate FLOAT"))
        if "principal_payment" not in existing:
            conn.execute(text("ALTER TABLE investments ADD COLUMN principal_payment FLOAT"))
        if "ytm" not in existing:
            conn.execute(text("ALTER TABLE investments ADD COLUMN ytm FLOAT"))
        if "current_price" not in existing:
            conn.execute(text("ALTER TABLE investments ADD COLUMN current_price FLOAT"))
        if "received_coupon" not in existing:
            conn.execute(text("ALTER TABLE investments ADD COLUMN received_coupon FLOAT"))
        if "expected_coupon" not in existing:
            conn.execute(text("ALTER TABLE investments ADD COLUMN expected_coupon FLOAT"))
        if "is_done" not in existing:
            conn.execute(text("ALTER TABLE investments ADD COLUMN is_done BOOLEAN NOT NULL DEFAULT 0"))


def session_factory(db_url: str) -> sessionmaker[Session]:
    engine = make_engine(db_url)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@contextmanager
def get_session(db_url: str) -> Iterator[Session]:
    SessionLocal = session_factory(db_url)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

