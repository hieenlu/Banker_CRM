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
from api.schemas.portfolio_view import PortfolioViewOut, PriceRefreshOut
from api.services.portfolio_view import build_portfolio_view, price_map_from_investments
from api.services.pricing import refresh_investment_prices
from database import load_app_settings
from models import Client, Income, Investment, Reminder

investments_router = APIRouter(prefix="/investments", tags=["investments"])
incomes_router = APIRouter(prefix="/incomes", tags=["incomes"])
reminders_router = APIRouter(prefix="/reminders", tags=["reminders"])
portfolio_view_router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _require_client(session, client_id: int) -> Client:
    row = session.get(Client, client_id)
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    return row


def _usd_vnd_rate() -> float:
    settings = load_app_settings()
    try:
        return float(settings.get("usd_vnd_rate") or 25500.0)
    except Exception:
        return 25500.0


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


@investments_router.post("/refresh-prices", response_model=PriceRefreshOut)
def refresh_prices(
    session: DbSession,
    _user: CurrentUser,
    client_id: int | None = None,
    is_done: bool | None = Query(False),
) -> PriceRefreshOut:
    """Fetch live prices (vnstock / yfinance / …) and store on open investments."""
    stmt = select(Investment)
    if client_id is not None:
        stmt = stmt.where(Investment.client_id == client_id)
    if is_done is not None:
        stmt = stmt.where(Investment.is_done.is_(is_done))
    rows = list(session.execute(stmt).scalars().all())
    try:
        result = refresh_investment_prices(rows)
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Price refresh unavailable on server (missing module: {exc.name}). Redeploy API image.",
        ) from exc
    except Exception as exc:  # pragma: no cover - passthrough with clearer client message
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Price refresh failed: {exc}",
        ) from exc
    session.flush()
    return PriceRefreshOut(**result)


@portfolio_view_router.get("/view", response_model=PortfolioViewOut)
def portfolio_view(
    session: DbSession,
    _user: CurrentUser,
    client_id: int | None = None,
    is_done: bool | None = Query(None),
    display_currency: str = Query("VND", pattern="^(VND|USD)$"),
    live: bool = False,
) -> PortfolioViewOut:
    """
    Streamlit-parity portfolio: grouped tables + PnL using utils formulas.
    Set live=true to fetch market prices before valuing (slower).
    Omit is_done to include all; default callers pass false for open only.
    """
    stmt = select(Investment)
    if client_id is not None:
        _require_client(session, client_id)
        stmt = stmt.where(Investment.client_id == client_id)
    if is_done is not None:
        stmt = stmt.where(Investment.is_done.is_(is_done))
    rows = list(session.execute(stmt.order_by(Investment.id.asc())).scalars().all())

    if live:
        refresh_investment_prices(rows)
        session.flush()

    price_map = price_map_from_investments(rows)
    client_ids = {r.client_id for r in rows}
    names: dict[int, str] = {}
    if client_ids:
        for c in session.execute(select(Client).where(Client.id.in_(client_ids))).scalars():
            names[c.id] = c.name

    view = build_portfolio_view(
        rows,
        price_map=price_map,
        usd_vnd_rate=_usd_vnd_rate(),
        display_currency=display_currency,
        client_names=names,
    )
    return PortfolioViewOut(**view)


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
