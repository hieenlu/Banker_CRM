"""Build a portable client JSON + attachment ZIP export."""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from datetime import date, datetime, timezone
from decimal import Decimal
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Client, Income, Investment, Reminder, StoredFile
from storage.base import ObjectStorage
from storage.keys import safe_filename


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _columns(row) -> dict:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def build_client_export_zip(
    session: Session,
    storage_for_row: Callable[[StoredFile], ObjectStorage],
    client_id: int,
    *,
    max_bytes: int,
) -> bytes:
    client = session.get(Client, client_id)
    if client is None:
        raise LookupError("Client not found")

    investments = list(
        session.execute(
            select(Investment).where(Investment.client_id == client_id).order_by(Investment.id)
        )
        .scalars()
        .all()
    )
    incomes = list(
        session.execute(select(Income).where(Income.client_id == client_id).order_by(Income.id))
        .scalars()
        .all()
    )
    reminders = list(
        session.execute(
            select(Reminder).where(Reminder.client_id == client_id).order_by(Reminder.id)
        )
        .scalars()
        .all()
    )
    attachments = list(
        session.execute(
            select(StoredFile)
            .where(
                StoredFile.client_id == client_id,
                StoredFile.kind == "client_attachment",
            )
            .order_by(StoredFile.id)
        )
        .scalars()
        .all()
    )
    total_attachment_bytes = sum(row.size_bytes for row in attachments)
    if total_attachment_bytes > max_bytes:
        raise ValueError(f"Export exceeds {max_bytes} byte attachment limit")

    payload = {
        "exported_at": datetime.now(timezone.utc),
        "client": _columns(client),
        "investments": [_columns(row) for row in investments],
        "incomes": [_columns(row) for row in incomes],
        "reminders": [_columns(row) for row in reminders],
        "attachments": [
            {
                "id": row.id,
                "original_filename": row.original_filename,
                "label": row.label,
                "content_type": row.content_type,
                "size_bytes": row.size_bytes,
                "sha256": row.sha256,
                "created_at": row.created_at,
            }
            for row in attachments
        ],
    }

    output = io.BytesIO()
    used_names: set[str] = set()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "client.json",
            json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        )
        for row in attachments:
            base = safe_filename(row.original_filename or f"attachment-{row.id}")
            name = f"attachments/{row.id}-{base}"
            if name in used_names:
                name = f"attachments/{row.id}-{row.sha256[:8]}-{base}"
            used_names.add(name)
            archive.writestr(name, storage_for_row(row).get_bytes(row.object_key))
    return output.getvalue()
