"""Clients CRUD."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from api.deps import CurrentUser, DbSession
from api.schemas.clients import ClientCreate, ClientOut, ClientUpdate
from api.schemas.common import Message, Page, paginate
from models import Client

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=Page[ClientOut])
def list_clients(
    session: DbSession,
    _user: CurrentUser,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> Page[ClientOut]:
    filters = []
    if q and q.strip():
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                Client.name.ilike(term),
                Client.email.ilike(term),
                Client.phone_number.ilike(term),
            )
        )
    count_q = select(func.count()).select_from(Client)
    if filters:
        count_q = count_q.where(*filters)
    total = int(session.execute(count_q).scalar_one() or 0)
    page, page_size, pages = paginate(total, page, page_size)
    stmt = select(Client).order_by(Client.name.asc())
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = list(session.execute(stmt).scalars().all())
    return Page(
        items=[ClientOut.from_orm_row(r) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(body: ClientCreate, session: DbSession, _user: CurrentUser) -> ClientOut:
    row = Client(**body.model_dump())
    session.add(row)
    session.flush()
    return ClientOut.from_orm_row(row)


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: int, session: DbSession, _user: CurrentUser) -> ClientOut:
    row = session.get(Client, client_id)
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    return ClientOut.from_orm_row(row)


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    body: ClientUpdate,
    session: DbSession,
    _user: CurrentUser,
) -> ClientOut:
    row = session.get(Client, client_id)
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    session.flush()
    return ClientOut.from_orm_row(row)


@router.delete("/{client_id}", response_model=Message)
def delete_client(client_id: int, session: DbSession, _user: CurrentUser) -> Message:
    row = session.get(Client, client_id)
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    session.delete(row)
    session.flush()
    return Message(detail="Client deleted")
