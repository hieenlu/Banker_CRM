"""Portfolio view response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PortfolioTotals(BaseModel):
    principal: float = 0.0
    current_value: float = 0.0
    pnl: float = 0.0
    pnl_pct: float | None = None


class PortfolioSubgroup(BaseModel):
    name: str
    columns: list[str]
    rows: list[dict[str, Any]]
    unrealized_pnl: float = 0.0
    native_currency: str = "VND"


class PortfolioGroup(BaseModel):
    name: str
    subgroups: list[PortfolioSubgroup]


class PortfolioViewOut(BaseModel):
    display_currency: str = "VND"
    usd_vnd_rate: float = 25500.0
    totals: PortfolioTotals
    groups: list[PortfolioGroup]


class PriceRefreshOut(BaseModel):
    requested: int
    resolved: int
    updated: int
    prices: dict[str, float] = Field(default_factory=dict)
    missing: list[str] = Field(default_factory=list)


class NewsRefreshOut(BaseModel):
    status: str
    fetched: int = 0
    new_count: int = 0
    deduped: int = 0
    classified: int = 0
    errors: list[str] = Field(default_factory=list)
