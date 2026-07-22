"""Client schemas."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from api.schemas.common import ORMModel


def _num(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


class ClientBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    birthday: date | None = None
    address: str | None = None
    phone_number: str | None = None
    email: str | None = None
    notes: str | None = None
    home_insurance_amount_covered: float | None = None
    home_insurance_expiry_date: date | None = None
    home_insurance_insured_premium: float | None = None
    salary_amount: float | None = None
    salary_concurrent: bool = False
    salary_note: str | None = None
    dividends_amount: float | None = None
    dividends_concurrent: bool = False
    dividends_note: str | None = None
    others_income_amount: float | None = None
    others_income_concurrent: bool = False
    others_income_note: str | None = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    birthday: date | None = None
    address: str | None = None
    phone_number: str | None = None
    email: str | None = None
    notes: str | None = None
    home_insurance_amount_covered: float | None = None
    home_insurance_expiry_date: date | None = None
    home_insurance_insured_premium: float | None = None
    salary_amount: float | None = None
    salary_concurrent: bool | None = None
    salary_note: str | None = None
    dividends_amount: float | None = None
    dividends_concurrent: bool | None = None
    dividends_note: str | None = None
    others_income_amount: float | None = None
    others_income_concurrent: bool | None = None
    others_income_note: str | None = None


class ClientOut(ORMModel):
    id: int
    name: str
    birthday: date | None = None
    address: str | None = None
    phone_number: str | None = None
    email: str | None = None
    notes: str | None = None
    home_insurance_amount_covered: float | None = None
    home_insurance_expiry_date: date | None = None
    home_insurance_insured_premium: float | None = None
    salary_amount: float | None = None
    salary_concurrent: bool = False
    salary_note: str | None = None
    dividends_amount: float | None = None
    dividends_concurrent: bool = False
    dividends_note: str | None = None
    others_income_amount: float | None = None
    others_income_concurrent: bool = False
    others_income_note: str | None = None

    @classmethod
    def from_orm_row(cls, row) -> "ClientOut":
        return cls(
            id=row.id,
            name=row.name,
            birthday=row.birthday,
            address=row.address,
            phone_number=row.phone_number,
            email=row.email,
            notes=row.notes,
            home_insurance_amount_covered=_num(row.home_insurance_amount_covered),
            home_insurance_expiry_date=row.home_insurance_expiry_date,
            home_insurance_insured_premium=_num(row.home_insurance_insured_premium),
            salary_amount=_num(row.salary_amount),
            salary_concurrent=bool(row.salary_concurrent),
            salary_note=row.salary_note,
            dividends_amount=_num(row.dividends_amount),
            dividends_concurrent=bool(row.dividends_concurrent),
            dividends_note=row.dividends_note,
            others_income_amount=_num(row.others_income_amount),
            others_income_concurrent=bool(row.others_income_concurrent),
            others_income_note=row.others_income_note,
        )
