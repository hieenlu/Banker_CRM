"""Create CRM + intel schema on a Postgres (or any) database URL."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    from database import init_db, normalize_db_url

    parser = argparse.ArgumentParser(description="Create Postgres schema for Banker CRM + Intel")
    parser.add_argument("--db-url", default="", help="Database URL (default: CRM_DB_URL)")
    args = parser.parse_args(argv)
    db_url = args.db_url or os.environ.get("CRM_DB_URL", "").strip()
    if not db_url:
        print("ERROR: pass --db-url or set CRM_DB_URL", file=sys.stderr)
        return 2
    init_db(db_url)
    print(f"Created schema on {normalize_db_url(db_url).split('@')[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
