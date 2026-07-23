"""Safe, stable object-key builders."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def safe_filename(value: str, *, fallback: str = "file", max_length: int = 100) -> str:
    raw = Path(value or "").name
    normalized = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", normalized).strip(".-_").lower()
    cleaned = re.sub(r"-+", "-", cleaned)
    if not cleaned:
        cleaned = fallback
    if len(cleaned) <= max_length:
        return cleaned
    suffix = Path(cleaned).suffix[:15]
    stem_limit = max(1, max_length - len(suffix))
    return f"{Path(cleaned).stem[:stem_limit]}{suffix}"


def normalize_prefix(prefix: str) -> str:
    return "/".join(part for part in (prefix or "").strip("/").split("/") if part)


def client_attachment_key(
    prefix: str,
    client_id: int,
    file_id: int,
    filename: str,
) -> str:
    parts = [normalize_prefix(prefix), "clients", str(client_id), f"{file_id}-{safe_filename(filename)}"]
    return "/".join(part for part in parts if part)


def techcombank_report_key(prefix: str, period_yyyymm: str) -> str:
    if not re.fullmatch(r"\d{6}", period_yyyymm or ""):
        raise ValueError("period_yyyymm must be YYYYMM")
    parts = [normalize_prefix(prefix), "techcombank", f"{period_yyyymm}.pdf"]
    return "/".join(part for part in parts if part)
