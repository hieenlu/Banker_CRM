"""
Phase 1 — migrate CRM + intel tables from SQLite → Postgres.

Usage:
  # 1) Create empty schema on Postgres
  python -m scripts.create_postgres_schema --db-url "$CRM_DB_URL"

  # 2) Copy data (IDs preserved)
  python -m scripts.migrate_sqlite_to_postgres \\
      --source sqlite:///banker_crm.sqlite3 \\
      --target "$CRM_DB_URL"

  # 3) Verify counts
  python -m scripts.migrate_sqlite_to_postgres --verify-only \\
      --source sqlite:///banker_crm.sqlite3 \\
      --target "$CRM_DB_URL"

Env:
  CRM_DB_URL=postgresql://USER:PASS@HOST/DB?sslmode=require
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, Table, create_engine, func, inspect, select, text
from sqlalchemy.engine import Engine

# Allow running as `python -m scripts...` from repo root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import init_db, is_postgres_url, is_sqlite_url, normalize_db_url  # noqa: E402
from models import Base  # noqa: E402


# Parent → child order (FK-safe). Intel models share Base.
TABLE_ORDER: tuple[str, ...] = (
    "clients",
    "stored_files",
    "investments",
    "incomes",
    "reminders",
    "news_cache",
    "intel_articles",
    "intel_article_summaries",
    "intel_article_bookmarks",
    "intel_daily_newspapers",
    "intel_pipeline_runs",
)


@dataclass
class TableCount:
    table: str
    source: int
    target: int

    @property
    def ok(self) -> bool:
        return self.source == self.target


def _ensure_intel_metadata() -> None:
    """Import intel models so they register on shared Base.metadata."""
    import intel_terminal.db.models  # noqa: F401


def _engine(url: str) -> Engine:
    return create_engine(normalize_db_url(url), pool_pre_ping=True)


def create_schema(db_url: str) -> None:
    """Create all CRM + intel tables on the target database."""
    init_db(db_url)
    print(f"Schema ready on {normalize_db_url(db_url).split('@')[-1]}")


def _reflect_table(engine: Engine, name: str) -> Table | None:
    meta = MetaData()
    inspector = inspect(engine)
    if name not in inspector.get_table_names():
        return None
    return Table(name, meta, autoload_with=engine)


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return value
    return value


def _row_to_dict(row_mapping: Any) -> dict[str, Any]:
    return {k: _serialize_value(v) for k, v in dict(row_mapping).items()}


def count_table(engine: Engine, table_name: str) -> int:
    table = _reflect_table(engine, table_name)
    if table is None:
        return 0
    with engine.connect() as conn:
        return int(conn.execute(select(func.count()).select_from(table)).scalar_one())


def verify_counts(source_url: str, target_url: str) -> list[TableCount]:
    src = _engine(source_url)
    dst = _engine(target_url)
    _ensure_intel_metadata()
    results: list[TableCount] = []
    for name in TABLE_ORDER:
        results.append(
            TableCount(
                table=name,
                source=count_table(src, name),
                target=count_table(dst, name),
            )
        )
    return results


def _reset_postgres_sequence(engine: Engine, table_name: str, pk_col: str = "id") -> None:
    """Align SERIAL/IDENTITY sequence with max(id) after explicit ID inserts."""
    if not is_postgres_url(str(engine.url)):
        return
    with engine.begin() as conn:
        seq = conn.execute(
            text("SELECT pg_get_serial_sequence(:t, :c)"),
            {"t": table_name, "c": pk_col},
        ).scalar()
        if not seq:
            return
        conn.execute(
            text(
                f"SELECT setval(:seq, COALESCE((SELECT MAX({pk_col}) FROM {table_name}), 1), true)"
            ),
            {"seq": seq},
        )


def migrate(
    source_url: str,
    target_url: str,
    *,
    truncate_target: bool = False,
    batch_size: int = 500,
) -> list[TableCount]:
    """
    Copy all known tables from source → target, preserving primary keys.
    """
    if is_sqlite_url(source_url) is False and "sqlite" not in source_url:
        # Allow sqlite file path shorthand
        pass

    src_engine = _engine(source_url)
    dst_url = normalize_db_url(target_url)
    dst_engine = _engine(dst_url)

    _ensure_intel_metadata()
    # Ensure destination has schema
    Base.metadata.create_all(bind=dst_engine)
    try:
        from intel_terminal.db.session import init_intel_tables

        init_intel_tables(dst_engine)
    except ImportError:
        pass

    if truncate_target and is_postgres_url(dst_url):
        # Child → parent truncate
        with dst_engine.begin() as conn:
            for name in reversed(TABLE_ORDER):
                if inspect(dst_engine).has_table(name):
                    conn.execute(text(f'TRUNCATE TABLE "{name}" RESTART IDENTITY CASCADE'))

    for name in TABLE_ORDER:
        src_table = _reflect_table(src_engine, name)
        dst_table = _reflect_table(dst_engine, name)
        if src_table is None:
            print(f"skip {name}: missing on source")
            continue
        if dst_table is None:
            print(f"skip {name}: missing on target (run create_schema first)")
            continue

        with src_engine.connect() as sconn:
            rows = list(sconn.execute(select(src_table)).mappings())
        if not rows:
            print(f"{name}: 0 rows")
            continue

        payloads = [_row_to_dict(r) for r in rows]
        # Insert in batches
        with dst_engine.begin() as dconn:
            for i in range(0, len(payloads), batch_size):
                chunk = payloads[i : i + batch_size]
                dconn.execute(dst_table.insert(), chunk)
        _reset_postgres_sequence(dst_engine, name)
        print(f"{name}: copied {len(payloads)} rows")

    return verify_counts(source_url, target_url)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SQLite → Postgres migration (Phase 1)")
    parser.add_argument(
        "--source",
        default=f"sqlite:///{ROOT / 'banker_crm.sqlite3'}",
        help="Source DB URL (default: local banker_crm.sqlite3)",
    )
    parser.add_argument(
        "--target",
        default="",
        help="Target Postgres URL (or set CRM_DB_URL)",
    )
    parser.add_argument(
        "--truncate-target",
        action="store_true",
        help="TRUNCATE target tables before copy (Postgres only)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only compare row counts",
    )
    parser.add_argument(
        "--create-schema-only",
        action="store_true",
        help="Only create empty schema on target",
    )
    args = parser.parse_args(argv)

    import os

    target = args.target or os.environ.get("CRM_DB_URL", "").strip()
    if not target:
        print("ERROR: pass --target or set CRM_DB_URL", file=sys.stderr)
        return 2

    if args.create_schema_only:
        create_schema(target)
        return 0

    if args.verify_only:
        counts = verify_counts(args.source, target)
        bad = 0
        for c in counts:
            mark = "OK" if c.ok else "MISMATCH"
            if not c.ok:
                bad += 1
            print(f"{c.table:28s} source={c.source:6d} target={c.target:6d}  {mark}")
        return 1 if bad else 0

    print(f"Migrating\n  source: {args.source}\n  target: {normalize_db_url(target).split('@')[-1]}")
    counts = migrate(args.source, target, truncate_target=args.truncate_target)
    print("\nVerification:")
    bad = 0
    for c in counts:
        mark = "OK" if c.ok else "MISMATCH"
        if not c.ok:
            bad += 1
        print(f"{c.table:28s} source={c.source:6d} target={c.target:6d}  {mark}")
    if bad:
        print(f"\n{bad} table(s) mismatched", file=sys.stderr)
        return 1
    print("\nMigration complete — all counts match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
