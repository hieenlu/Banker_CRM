"""Mirror Techcombank monthly PDFs into configured object storage."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.config import ApiSettings
from models import StoredFile
from scraper import NEWS_TIMEOUT_SECS, USER_AGENT, scrape_techcombank_monthly_reports
from storage.base import ObjectStorage
from storage.keys import techcombank_report_key

logger = logging.getLogger(__name__)


def _validate_report_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        host == "techcombank.com" or host.endswith(".techcombank.com")
    ):
        raise ValueError("Report URL must be HTTPS on techcombank.com")


def _download_report(url: str, *, max_bytes: int) -> bytes:
    """Download with bounded memory and validate every redirect before following it."""
    current = url
    for _ in range(4):
        _validate_report_url(current)
        response = requests.get(
            current,
            headers={"User-Agent": USER_AGENT},
            timeout=max(NEWS_TIMEOUT_SECS, 30),
            stream=True,
            allow_redirects=False,
        )
        if 300 <= response.status_code < 400:
            location = response.headers.get("location", "")
            response.close()
            if not location:
                raise ValueError("Report redirect did not include a location")
            current = urljoin(current, location)
            continue
        response.raise_for_status()
        _validate_report_url(getattr(response, "url", current))
        declared = response.headers.get("content-length")
        if declared and int(declared) > max_bytes:
            response.close()
            raise ValueError(f"PDF exceeds {max_bytes} byte limit")
        chunks: list[bytes] = []
        size = 0
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError(f"PDF exceeds {max_bytes} byte limit")
                chunks.append(chunk)
        finally:
            response.close()
        data = b"".join(chunks)
        if not data.startswith(b"%PDF-"):
            raise ValueError("Downloaded report is not a PDF")
        return data
    raise ValueError("Too many report redirects")


def sync_techcombank_reports(
    session: Session,
    storage: ObjectStorage,
    settings: ApiSettings,
    *,
    limit: int = 8,
) -> dict[str, object]:
    reports = scrape_techcombank_monthly_reports(limit=limit)
    synced = 0
    skipped = 0
    errors: list[str] = []

    for report in reports:
        period = str(report.get("yyyymm") or "").strip()
        source_url = str(report.get("url") or "").strip()
        if len(period) != 6 or not period.isdigit() or not source_url:
            errors.append(f"Invalid report record: {period or 'unknown'}")
            continue

        row: StoredFile | None = None
        created = False
        try:
            data = _download_report(source_url, max_bytes=settings.max_upload_bytes)
            digest = hashlib.sha256(data).hexdigest()
            key = techcombank_report_key(settings.s3_prefix, period)
            row = session.execute(
                select(StoredFile).where(
                    StoredFile.kind == "techcombank_report",
                    StoredFile.period_yyyymm == period,
                )
            ).scalar_one_or_none()
            if (
                row
                and row.status == "ready"
                and row.sha256 == digest
                and row.backend == storage.backend_name
                and row.bucket == storage.bucket
                and row.object_key == key
                and storage.exists(key)
            ):
                skipped += 1
                continue

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if row is None:
                row = StoredFile(
                    kind="techcombank_report",
                    backend=storage.backend_name,
                    bucket=storage.bucket,
                    object_key=key,
                    status="pending",
                    content_type="application/pdf",
                    size_bytes=len(data),
                    sha256=digest,
                    period_yyyymm=period,
                    source_url=source_url,
                    original_filename=f"techcombank-{period}.pdf",
                    created_at=now,
                    synced_at=now,
                )
                session.add(row)
                created = True
            else:
                row.status = "pending"
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                row = session.execute(
                    select(StoredFile).where(
                        StoredFile.kind == "techcombank_report",
                        StoredFile.period_yyyymm == period,
                    )
                ).scalar_one_or_none()
                if row is None:
                    raise
                created = False
                row.status = "pending"
                session.commit()

            storage.put_bytes(key, data, "application/pdf")
            row.backend = storage.backend_name
            row.bucket = storage.bucket
            row.object_key = key
            row.status = "ready"
            row.content_type = "application/pdf"
            row.size_bytes = len(data)
            row.sha256 = digest
            row.source_url = source_url
            row.original_filename = f"techcombank-{period}.pdf"
            row.synced_at = now
            session.commit()
            synced += 1
        except Exception as exc:
            logger.exception("Techcombank report sync failed for %s", period)
            session.rollback()
            if row is not None:
                try:
                    if created:
                        try:
                            storage.delete(
                                techcombank_report_key(settings.s3_prefix, period)
                            )
                        except Exception:
                            pass
                        session.delete(row)
                    else:
                        row.status = "ready"
                    session.commit()
                except Exception:
                    session.rollback()
            errors.append(f"{period}: sync failed ({type(exc).__name__})")

    return {
        "found": len(reports),
        "synced": synced,
        "skipped": skipped,
        "errors": errors,
    }
