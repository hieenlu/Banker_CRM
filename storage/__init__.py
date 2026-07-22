"""S3-compatible and local object storage."""

from storage.base import ObjectStorage
from storage.service import get_storage

__all__ = ["ObjectStorage", "get_storage"]
