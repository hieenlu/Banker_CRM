"""Filesystem storage backend for local development and tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class LocalStorage:
    backend_name = "local"
    bucket = "local"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        path = (self.root / key.strip("/")).resolve()
        if path != self.root and self.root not in path.parents:
            raise ValueError("Invalid object key")
        return path

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        del content_type
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=".upload-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as temporary:
                temporary.write(data)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, path)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise

    def get_bytes(self, key: str) -> bytes:
        return self.path_for(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self.path_for(key)
        path.unlink(missing_ok=True)
        parent = path.parent
        while parent != self.root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

    def exists(self, key: str) -> bool:
        return self.path_for(key).is_file()

    def signed_get_url(
        self,
        key: str,
        *,
        expires_seconds: int,
        download_name: str | None = None,
    ) -> None:
        del key, expires_seconds, download_name
        return None
