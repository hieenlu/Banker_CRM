"""Investments, incomes, and reminders CRUD."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from api.deps import CurrentUser, DbSession
from api.schemas.common import Message, Page, paginate
from api.schemas.portfolio import (
    IncomeCreate,
    IncomeOut,
    IncomeUpdate,
    InvestmentCreate,
    InvestmentOut,
    InvestmentUpdate,
    ReminderCreate,
    ReminderOut,
    ReminderUpdate,
)
from models import Client, Income, Investment, Reminder

investments_router = APIRouter(prefix="/investments", tags=["investments"])
incomes_router = APIRouter(prefix="/incomes", tags=["incomes"])
reminders_router = APIRouter(prefix="/reminders", tags=["reminders"])


def _require_client(session, client_id: int) -> Client:
    row = session.get(Client, client_id)
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    return row


@investments_router.get("", response_model=Page[InvestmentOut])
def list_investments(
    session: DbSession,
    _user: CurrentUser,
    client_id: int | None = None,
    is_done: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[InvestmentOut]:
    filters = []
    if client_id is not None:
        filters.append(Investment.client_id == client_id)
    if is_done is not None:
        filters.append(Investment.is_done.is_(is_done))
    count_q = select(func.count()).select_from(Investment)
    if filters:
        count_q = count_q.where(*filters)
    total = int(session.execute(count_q).scalar_one() or 0)
    page, page_size, pages = paginate(total, page, page_size)
    stmt = select(Investment).order_by(Investment.id.desc())
    if filters:
        stmt = stmt.where(*filters)
    rows = list(session.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all())
    return Page(
        items=[InvestmentOut.from_orm_row(r) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@investments_router.post("", response_model=InvestmentOut, status_code=status.HTTP_201_CREATED)
def create_investment(
    body: InvestmentCreate, session: DbSession, _user: CurrentUser
) -> InvestmentOut:
    _require_client(session, body.client_id)
    row = Investment(**body.model_dump())
    session.add(row)
    session.flush()
    return InvestmentOut.from_orm_row(row)


@investments_router.get("/{investment_id}", response_model=InvestmentOut)
def get_investment(investment_id: int, session: DbSession, _user: CurrentUser) -> InvestmentOut:
    row = session.get(Investment, investment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Investment not found")
    return InvestmentOut.from_orm_row(row)


@investments_router.patch("/{investment_id}", response_model=InvestmentOut)
def update_investment(
    investment_id: int,
    body: InvestmentUpdate,
    session: DbSession,
    _user: CurrentUser,
) -> InvestmentOut:
    row = session.get(Investment, investment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Investment not found")
    data = body.model_dump(exclude_unset=True)
    if "client_id" in data and data["client_id"] is not None:
        _require_client(session, data["client_id"])
    for key, value in data.items():
        setattr(row, key, value)
    session.flush()
    return InvestmentOut.from_orm_row(row)


@investments_router.delete("/{investment_id}", response_model=Message)
def delete_investment(investment_id: int, session: DbSession, _user: CurrentUser) -> Message:
    row = session.get(Investment, investment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Investment not found")
    session.delete(row)
    session.flush()
    return Message(detail="Investment deleted")


@incomes_router.get("", response_model=Page[IncomeOut])
def list_incomes(
    session: DbSession,
    _user: CurrentUser,
    client_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[IncomeOut]:
    filters = []
    if client_id is not None:
        filters.append(Income.client_id == client_id)
    count_q = select(func.count()).select_from(Income)
    if filters:
        count_q = count_q.where(*filters)
    total = int(session.execute(count_q).scalar_one() or 0)
    page, page_size, pages = paginate(total, page, page_size)
    stmt = select(Income).order_by(Income.id.desc())
    if filters:
        stmt = stmt.where(*filters)
    rows = list(session.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all())
    return Page(
        items=[IncomeOut.from_orm_row(r) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@incomes_router.post("", response_model=IncomeOut, status_code=status.HTTP_201_CREATED)
def create_income(body: IncomeCreate, session: DbSession, _user: CurrentUser) -> IncomeOut:
    _require_client(session, body.client_id)
    row = Income(**body.model_dump())
    session.add(row)
    session.flush()
    return IncomeOut.from_orm_row(row)


@incomes_router.get("/{income_id}", response_model=IncomeOut)
def get_income(income_id: int, session: DbSession, _user: CurrentUser) -> IncomeOut:
    row = session.get(Income, income_id)
    if not row:
        raise HTTPException(status_code=404, detail="Income not found")
    return IncomeOut.from_orm_row(row)


@incomes_router.patch("/{income_id}", response_model=IncomeOut)
def update_income(
    income_id: int, body: IncomeUpdate, session: DbSession, _user: CurrentUser
) -> IncomeOut:
    row = session.get(Income, income_id)
    if not row:
        raise HTTPException(status_code=404, detail="Income not found")
    data = body.model_dump(exclude_unset=True)
    if "client_id" in data and data["client_id"] is not None:
        _require_client(session, data["client_id"])
    for key, value in data.items():
        setattr(row, key, value)
    session.flush()
    return IncomeOut.from_orm_row(row)


@incomes_router.delete("/{income_id}", response_model=Message)
def delete_income(income_id: int, session: DbSession, _user: CurrentUser) -> Message:
    row = session.get(Income, income_id)
    if not row:
        raise HTTPException(status_code=404, detail="Income not found")
    session.delete(row)
    session.flush()
    return Message(detail="Income deleted")


@reminders_router.get("", response_model=Page[ReminderOut])
def list_reminders(
    session: DbSession,
    _user: CurrentUser,
    client_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[ReminderOut]:
    filters = []
    if client_id is not None:
        filters.append(Reminder.client_id == client_id)
    if from_date is not None:
        filters.append(Reminder.reminder_date >= from_date)
    if to_date is not None:
        filters.append(Reminder.reminder_date <= to_date)
    count_q = select(func.count()).select_from(Reminder)
    if filters:
        count_q = count_q.where(*filters)
    total = int(session.execute(count_q).scalar_one() or 0)
    page, page_size, pages = paginate(total, page, page_size)
    stmt = select(Reminder).order_by(Reminder.reminder_date.asc(), Reminder.id.asc())
    if filters:
        stmt = stmt.where(*filters)
    rows = list(session.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all())
    return Page(
        items=[ReminderOut.from_orm_row(r) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@reminders_router.post("", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
def create_reminder(body: ReminderCreate, session: DbSession, _user: CurrentUser) -> ReminderOut:
    if body.client_id is not None:
        _require_client(session, body.client_id)
    row = Reminder(**body.model_dump())
    session.add(row)
    session.flush()
    return ReminderOut.from_orm_row(row)


@reminders_router.get("/{reminder_id}", response_model=ReminderOut)
def get_reminder(reminder_id: int, session: DbSession, _user: CurrentUser) -> ReminderOut:
    row = session.get(Reminder, reminder_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return ReminderOut.from_orm_row(row)


@reminders_router.patch("/{reminder_id}", response_model=ReminderOut)
def update_reminder(
    reminder_id: int, body: ReminderUpdate, session: DbSession, _user: CurrentUser
) -> ReminderOut:
    row = session.get(Reminder, reminder_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reminder not found")
    data = body.model_dump(exclude_unset=True)
    if data.get("client_id") is not None:
        _require_client(session, data["client_id"])
    for key, value in data.items():
        setattr(row, key, value)
    session.flush()
    return ReminderOut.from_orm_row(row)


@reminders_router.delete("/{reminder_id}", response_model=Message)
def delete_reminder(reminder_id: int, session: DbSession, _user: CurrentUser) -> Message:
    row = session.get(Reminder, reminder_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reminder not found")
    session.delete(row)
    session.flush()
    return Message(detail="Reminder deleted")
