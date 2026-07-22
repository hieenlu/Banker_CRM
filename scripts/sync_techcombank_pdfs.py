"""Mirror Techcombank reports into local/R2/S3 storage."""

from __future__ import annotations

import argparse
import json

from api.config import get_settings
from database import get_session, init_db
from storage.service import get_storage
from storage.techcombank import sync_techcombank_reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args(argv)
    limit = max(1, min(args.limit, 36))

    settings = get_settings()
    init_db(settings.db_url)
    storage = get_storage(settings)
    with get_session(settings.db_url) as session:
        result = sync_techcombank_reports(
            session,
            storage,
            settings,
            limit=limit,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] and result["synced"] == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
