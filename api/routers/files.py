"""Client attachments, Techcombank report mirrors, and export ZIPs."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import desc, func, select
from starlette.concurrency import run_in_threadpool

from api.config import get_settings
from api.deps import CurrentUser, DbSession
from api.schemas.common import Message, Page, paginate
from api.schemas.files import StoredFileOut, TechcombankSyncResult
from models import Client, StoredFile
from storage.export import build_client_export_zip
from storage.keys import client_attachment_key, safe_filename
from storage.service import get_storage, get_storage_for_row
from storage.techcombank import sync_techcombank_reports
from storage.validation import content_matches_type

router = APIRouter(tags=["files"])
logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _download_metadata(request: Request, row: StoredFile) -> tuple[str, datetime | None]:
    settings = get_settings()
    storage = get_storage_for_row(settings, row)
    filename = row.original_filename or f"file-{row.id}"
    if storage.backend_name == "s3":
        url = storage.signed_get_url(
            row.object_key,
            expires_seconds=settings.signed_url_ttl_seconds,
            download_name=filename,
        )
        expires = _utcnow() + timedelta(seconds=settings.signed_url_ttl_seconds)
        return str(url), expires
    return str(request.url_for("download_file", file_id=row.id)), None


def _file_out(request: Request, row: StoredFile) -> StoredFileOut:
    url, expires = _download_metadata(request, row)
    return StoredFileOut.from_orm_row(
        row,
        download_url=url,
        download_expires_at=expires,
    )


@router.get("/clients/{client_id}/attachments", response_model=Page[StoredFileOut])
def list_attachments(
    client_id: int,
    request: Request,
    session: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page[StoredFileOut]:
    if session.get(Client, client_id) is None:
        raise HTTPException(status_code=404, detail="Client not found")
    filters = (
        StoredFile.client_id == client_id,
        StoredFile.kind == "client_attachment",
        StoredFile.status == "ready",
    )
    total = int(
        session.execute(select(func.count()).select_from(StoredFile).where(*filters)).scalar_one()
        or 0
    )
    page, page_size, pages = paginate(total, page, page_size)
    rows = list(
        session.execute(
            select(StoredFile)
            .where(*filters)
            .order_by(desc(StoredFile.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return Page(
        items=[_file_out(request, row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.post(
    "/clients/{client_id}/attachments",
    response_model=StoredFileOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    client_id: int,
    request: Request,
    session: DbSession,
    _user: CurrentUser,
    file: UploadFile = File(...),
    label: str | None = Form(default=None, max_length=250),
) -> StoredFileOut:
    if session.get(Client, client_id) is None:
        raise HTTPException(status_code=404, detail="Client not found")
    settings = get_settings()
    content_type = (file.content_type or "application/octet-stream").split(";")[0].strip()
    if content_type not in settings.allowed_upload_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {content_type}",
        )
    data = await file.read(settings.max_upload_bytes + 1)
    if not data:
        raise HTTPException(status_code=400, detail="File is empty")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_upload_bytes} byte limit",
        )
    if not content_matches_type(data, content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File content does not match its declared content type",
        )

    filename = safe_filename(file.filename or "attachment")
    digest = hashlib.sha256(data).hexdigest()
    storage = get_storage(settings)
    row = StoredFile(
        kind="client_attachment",
        backend=storage.backend_name,
        bucket=storage.bucket,
        object_key=f"pending/{client_id}/{uuid4().hex}",
        status="pending",
        content_type=content_type,
        size_bytes=len(data),
        sha256=digest,
        client_id=client_id,
        original_filename=filename,
        label=label.strip() if label and label.strip() else None,
        created_at=_utcnow(),
        synced_at=_utcnow(),
    )
    session.add(row)
    session.flush()
    row.object_key = client_attachment_key(
        settings.s3_prefix,
        client_id,
        row.id,
        filename,
    )
    # Persist the pending record before the external write so interrupted
    # uploads remain discoverable and are never exposed as ready.
    session.commit()
    try:
        await run_in_threadpool(storage.put_bytes, row.object_key, data, content_type)
        row.status = "ready"
        session.flush()
    except Exception as exc:
        logger.exception("Attachment storage upload failed")
        try:
            storage.delete(row.object_key)
        except Exception:
            logger.exception("Attachment upload compensation failed")
        session.delete(row)
        session.commit()
        raise HTTPException(status_code=502, detail="Storage upload failed") from exc
    return _file_out(request, row)


@router.get(
    "/clients/{client_id}/attachments/{file_id}",
    response_model=StoredFileOut,
)
def get_attachment(
    client_id: int,
    file_id: int,
    request: Request,
    session: DbSession,
    _user: CurrentUser,
) -> StoredFileOut:
    row = session.execute(
        select(StoredFile).where(
            StoredFile.id == file_id,
            StoredFile.client_id == client_id,
            StoredFile.kind == "client_attachment",
            StoredFile.status == "ready",
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return _file_out(request, row)


@router.delete(
    "/clients/{client_id}/attachments/{file_id}",
    response_model=Message,
)
def delete_attachment(
    client_id: int,
    file_id: int,
    session: DbSession,
    _user: CurrentUser,
) -> Message:
    row = session.execute(
        select(StoredFile).where(
            StoredFile.id == file_id,
            StoredFile.client_id == client_id,
            StoredFile.kind == "client_attachment",
            StoredFile.status == "ready",
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    row.status = "deleting"
    session.commit()
    try:
        get_storage_for_row(get_settings(), row).delete(row.object_key)
    except Exception as exc:
        logger.exception("Attachment storage deletion failed")
        raise HTTPException(status_code=502, detail="Storage deletion failed") from exc
    session.delete(row)
    session.flush()
    return Message(detail="Attachment deleted")


@router.get("/clients/{client_id}/export.zip")
def export_client(
    client_id: int,
    session: DbSession,
    _user: CurrentUser,
) -> Response:
    try:
        data = build_client_export_zip(
            session,
            lambda row: get_storage_for_row(get_settings(), row),
            client_id,
            max_bytes=get_settings().max_export_bytes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    filename = f"client-{client_id}-export.zip"
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/files/techcombank/reports", response_model=Page[StoredFileOut])
def list_techcombank_reports(
    request: Request,
    session: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[StoredFileOut]:
    filters = (
        StoredFile.kind == "techcombank_report",
        StoredFile.status == "ready",
    )
    total = int(
        session.execute(select(func.count()).select_from(StoredFile).where(*filters)).scalar_one()
        or 0
    )
    page, page_size, pages = paginate(total, page, page_size)
    rows = list(
        session.execute(
            select(StoredFile)
            .where(*filters)
            .order_by(desc(StoredFile.period_yyyymm))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return Page(
        items=[_file_out(request, row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.post("/files/techcombank/sync", response_model=TechcombankSyncResult)
def sync_reports(
    session: DbSession,
    _user: CurrentUser,
    limit: int = Query(8, ge=1, le=36),
) -> TechcombankSyncResult:
    result = sync_techcombank_reports(
        session,
        get_storage(get_settings()),
        get_settings(),
        limit=limit,
    )
    return TechcombankSyncResult(**result)


@router.get(
    "/files/techcombank/reports/{period_yyyymm}",
    response_model=StoredFileOut,
)
def get_techcombank_report(
    period_yyyymm: str,
    request: Request,
    session: DbSession,
    _user: CurrentUser,
) -> StoredFileOut:
    row = session.execute(
        select(StoredFile).where(
            StoredFile.kind == "techcombank_report",
            StoredFile.period_yyyymm == period_yyyymm,
            StoredFile.status == "ready",
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return _file_out(request, row)


@router.get("/files/{file_id}/download", name="download_file")
def download_file(
    file_id: int,
    session: DbSession,
    _user: CurrentUser,
):
    row = session.get(StoredFile, file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found")
    if row.status != "ready":
        raise HTTPException(status_code=409, detail="File is not ready")
    settings = get_settings()
    storage = get_storage_for_row(settings, row)
    filename = row.original_filename or f"file-{row.id}"
    if storage.backend_name == "s3":
        url = storage.signed_get_url(
            row.object_key,
            expires_seconds=settings.signed_url_ttl_seconds,
            download_name=filename,
        )
        return RedirectResponse(str(url), status_code=307)
    try:
        data = storage.get_bytes(row.object_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Stored object not found") from exc
    return Response(
        content=data,
        media_type=row.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename(filename)}"',
            "Cache-Control": "private, no-store",
        },
    )
