"""Storage backend factory."""

from __future__ import annotations

from api.config import ApiSettings
from storage.base import ObjectStorage
from storage.local import LocalStorage
from storage.s3 import S3Storage


def get_storage(settings: ApiSettings) -> ObjectStorage:
    backend = settings.storage_backend.lower()
    if backend == "local":
        return LocalStorage(settings.local_storage_path)
    if backend == "s3":
        return S3Storage(
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url or None,
            access_key_id=settings.s3_access_key_id or None,
            secret_access_key=settings.s3_secret_access_key or None,
        )
    raise ValueError("CRM_STORAGE_BACKEND must be 'local' or 's3'")


def get_storage_for_row(settings: ApiSettings, row) -> ObjectStorage:
    """Resolve a stored object's recorded backend/bucket using current credentials."""
    if row.backend == "local":
        return LocalStorage(settings.local_storage_path)
    if row.backend == "s3":
        return S3Storage(
            bucket=row.bucket,
            region=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url or None,
            access_key_id=settings.s3_access_key_id or None,
            secret_access_key=settings.s3_secret_access_key or None,
        )
    raise ValueError(f"Unsupported stored backend: {row.backend}")
