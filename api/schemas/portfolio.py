"""Investment / income / reminder schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from api.schemas.common import ORMModel


def _num(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


class InvestmentBase(BaseModel):
    client_id: int
    asset_type: str = "Stock"
    ticker_name: str | None = None
    ticker_identifier: str | None = None
    quantity: float = 0.0
    unit: float | None = None
    principal: float | None = None
    purchase_price: float = 0.0
    currency: str = "USD"
    purchase_date: date | None = None
    tenor: str | None = None
    interest_rate: float | None = None
    principal_payment: float | None = None
    ytm: float | None = None
    current_price: float | None = None
    received_coupon: float | None = None
    expected_coupon: float | None = None
    maturity_date: date | None = None
    is_done: bool = False
    notes: str | None = None


class InvestmentCreate(InvestmentBase):
    pass


class InvestmentUpdate(BaseModel):
    client_id: int | None = None
    asset_type: str | None = None
    ticker_name: str | None = None
    ticker_identifier: str | None = None
    quantity: float | None = None
    unit: float | None = None
    principal: float | None = None
    purchase_price: float | None = None
    currency: str | None = None
    purchase_date: date | None = None
    tenor: str | None = None
    interest_rate: float | None = None
    principal_payment: float | None = None
    ytm: float | None = None
    current_price: float | None = None
    received_coupon: float | None = None
    expected_coupon: float | None = None
    maturity_date: date | None = None
    is_done: bool | None = None
    notes: str | None = None


class InvestmentOut(ORMModel):
    id: int
    client_id: int
    asset_type: str
    ticker_name: str | None = None
    ticker_identifier: str | None = None
    quantity: float = 0.0
    unit: float | None = None
    principal: float | None = None
    purchase_price: float = 0.0
    currency: str = "USD"
    purchase_date: date | None = None
    tenor: str | None = None
    interest_rate: float | None = None
    principal_payment: float | None = None
    ytm: float | None = None
    current_price: float | None = None
    received_coupon: float | None = None
    expected_coupon: float | None = None
    maturity_date: date | None = None
    is_done: bool = False
    notes: str | None = None

    @classmethod
    def from_orm_row(cls, row) -> "InvestmentOut":
        return cls(
            id=row.id,
            client_id=row.client_id,
            asset_type=row.asset_type,
            ticker_name=row.ticker_name,
            ticker_identifier=row.ticker_identifier,
            quantity=float(row.quantity or 0),
            unit=_num(row.unit),
            principal=_num(row.principal),
            purchase_price=float(row.purchase_price or 0),
            currency=row.currency or "USD",
            purchase_date=row.purchase_date,
            tenor=row.tenor,
            interest_rate=_num(row.interest_rate),
            principal_payment=_num(row.principal_payment),
            ytm=_num(row.ytm),
            current_price=_num(row.current_price),
            received_coupon=_num(row.received_coupon),
            expected_coupon=_num(row.expected_coupon),
            maturity_date=row.maturity_date,
            is_done=bool(row.is_done),
            notes=row.notes,
        )


class IncomeBase(BaseModel):
    client_id: int
    income_type: str = Field(..., min_length=1, max_length=50)
    income_mode: str = "Actual"
    amount: float = 0.0
    concurrent: bool = False
    is_done: bool = False
    note: str | None = None


class IncomeCreate(IncomeBase):
    pass


class IncomeUpdate(BaseModel):
    client_id: int | None = None
    income_type: str | None = None
    income_mode: str | None = None
    amount: float | None = None
    concurrent: bool | None = None
    is_done: bool | None = None
    note: str | None = None


class IncomeOut(ORMModel):
    id: int
    client_id: int
    income_type: str
    income_mode: str
    amount: float
    concurrent: bool
    is_done: bool
    note: str | None = None

    @classmethod
    def from_orm_row(cls, row) -> "IncomeOut":
        return cls(
            id=row.id,
            client_id=row.client_id,
            income_type=row.income_type,
            income_mode=row.income_mode,
            amount=float(row.amount or 0),
            concurrent=bool(row.concurrent),
            is_done=bool(row.is_done),
            note=row.note,
        )


class ReminderBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=250)
    reminder_date: date
    reminder_type: str = "manual"
    client_id: int | None = None
    investment_id: int | None = None
    notes: str | None = None


class ReminderCreate(ReminderBase):
    pass


class ReminderUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=250)
    reminder_date: date | None = None
    reminder_type: str | None = None
    client_id: int | None = None
    investment_id: int | None = None
    notes: str | None = None
    sent_at: datetime | None = None


class ReminderOut(ORMModel):
    id: int
    title: str
    reminder_date: date
    reminder_type: str
    client_id: int | None = None
    investment_id: int | None = None
    notes: str | None = None
    created_at: datetime
    sent_at: datetime | None = None

    @classmethod
    def from_orm_row(cls, row) -> "ReminderOut":
        return cls(
            id=row.id,
            title=row.title,
            reminder_date=row.reminder_date,
            reminder_type=row.reminder_type,
            client_id=row.client_id,
            investment_id=row.investment_id,
            notes=row.notes,
            created_at=row.created_at,
            sent_at=row.sent_at,
        )
