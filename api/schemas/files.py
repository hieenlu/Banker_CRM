"""Stored-file API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from api.schemas.common import ORMModel


class StoredFileOut(ORMModel):
    id: int
    kind: str
    backend: str
    status: str
    content_type: str
    size_bytes: int
    sha256: str
    client_id: int | None = None
    original_filename: str | None = None
    label: str | None = None
    period_yyyymm: str | None = None
    source_url: str | None = None
    created_at: datetime
    synced_at: datetime | None = None
    download_url: str | None = None
    download_expires_at: datetime | None = None

    @classmethod
    def from_orm_row(
        cls,
        row,
        *,
        download_url: str | None = None,
        download_expires_at: datetime | None = None,
    ) -> "StoredFileOut":
        return cls(
            id=row.id,
            kind=row.kind,
            backend=row.backend,
            status=row.status,
            content_type=row.content_type,
            size_bytes=row.size_bytes,
            sha256=row.sha256,
            client_id=row.client_id,
            original_filename=row.original_filename,
            label=row.label,
            period_yyyymm=row.period_yyyymm,
            source_url=row.source_url,
            created_at=row.created_at,
            synced_at=row.synced_at,
            download_url=download_url,
            download_expires_at=download_expires_at,
        )


class TechcombankSyncResult(BaseModel):
    found: int
    synced: int
    skipped: int
    errors: list[str]
