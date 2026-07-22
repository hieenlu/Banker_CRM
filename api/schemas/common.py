"""Shared API schemas."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    db_ok: bool


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    pages: int


def paginate(total: int, page: int, page_size: int) -> tuple[int, int, int]:
    """Return (page, page_size, pages) clamped to valid ranges."""
    size = max(1, min(int(page_size), 200))
    pages = max(1, (int(total) + size - 1) // size) if total else 1
    current = min(max(int(page), 1), pages)
    return current, size, pages


class Message(BaseModel):
    detail: str = Field(..., examples=["ok"])
