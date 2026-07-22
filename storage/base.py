"""Storage backend contract."""

from __future__ import annotations

from typing import Protocol


class ObjectStorage(Protocol):
    backend_name: str
    bucket: str

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None: ...

    def get_bytes(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...

    def signed_get_url(
        self,
        key: str,
        *,
        expires_seconds: int,
        download_name: str | None = None,
    ) -> str | None: ...
