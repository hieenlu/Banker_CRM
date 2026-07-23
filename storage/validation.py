"""Conservative content checks for accepted upload types."""

from __future__ import annotations

from zipfile import BadZipFile, ZipFile
import io


def content_matches_type(data: bytes, content_type: str) -> bool:
    if content_type == "application/pdf":
        return data.startswith(b"%PDF-")
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "text/plain":
        if b"\x00" in data:
            return False
        try:
            data.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
    if content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        try:
            with ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
                return "[Content_Types].xml" in names and any(
                    name.startswith("xl/") for name in names
                )
        except (BadZipFile, OSError):
            return False
    return False
