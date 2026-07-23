from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    BigInteger,
    CheckConstraint,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    home_insurance_amount_covered: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    home_insurance_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    home_insurance_insured_premium: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    salary_amount: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    salary_concurrent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    salary_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    dividends_amount: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    dividends_concurrent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dividends_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    others_income_amount: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    others_income_concurrent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    others_income_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    investments: Mapped[list["Investment"]] = relationship(
        back_populates="client", cascade="all, delete-orphan", lazy="selectin"
    )
    incomes: Mapped[list["Income"]] = relationship(
        back_populates="client", cascade="all, delete-orphan", lazy="selectin"
    )
    attachments: Mapped[list["StoredFile"]] = relationship(
        back_populates="client", cascade="all, delete-orphan", lazy="selectin"
    )


class Investment(Base):
    __tablename__ = "investments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)

    asset_type: Mapped[str] = mapped_column(String(50), nullable=False, default="Stock")
    ticker_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ticker_identifier: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unit: Mapped[float | None] = mapped_column(Float, nullable=True)
    principal: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    purchase_price: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    tenor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    interest_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    principal_payment: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytm: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    received_coupon: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_coupon: Mapped[float | None] = mapped_column(Float, nullable=True)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    is_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    client: Mapped["Client"] = relationship(back_populates="investments")


class Income(Base):
    __tablename__ = "incomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    income_type: Mapped[str] = mapped_column(String(50), nullable=False)
    income_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="Actual")
    amount: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False, default=0.0)
    concurrent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    client: Mapped["Client"] = relationship(back_populates="incomes")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False, index=True)

    # Optional relationships
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    investment_id: Mapped[int | None] = mapped_column(
        ForeignKey("investments.id", ondelete="SET NULL"), nullable=True
    )

    # What day we want to notify on (date-only)
    reminder_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # 'manual', 'birthday', 'maturity'
    reminder_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NewsCache(Base):
    __tablename__ = "news_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keywords_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    keywords_text: Mapped[str] = mapped_column(String(500), nullable=False)

    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    results_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string


class StoredFile(Base):
    """Metadata for an object stored locally, in Cloudflare R2, or in AWS S3."""

    __tablename__ = "stored_files"
    __table_args__ = (
        UniqueConstraint(
            "backend", "bucket", "object_key", name="uq_stored_files_object_identity"
        ),
        UniqueConstraint("kind", "period_yyyymm", name="uq_stored_files_kind_period"),
        Index("ix_stored_files_client_created", "client_id", "created_at"),
        CheckConstraint("size_bytes >= 0", name="ck_stored_files_size_nonnegative"),
        CheckConstraint(
            "status IN ('pending', 'ready', 'deleting')",
            name="ck_stored_files_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    backend: Mapped[str] = mapped_column(String(20), nullable=False)
    bucket: Mapped[str] = mapped_column(String(200), nullable=False)
    object_key: Mapped[str] = mapped_column(String(700), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready", index=True)
    content_type: Mapped[str] = mapped_column(String(200), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=True, index=True
    )
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    label: Mapped[str | None] = mapped_column(String(250), nullable=True)

    period_yyyymm: Mapped[str | None] = mapped_column(String(6), nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    client: Mapped["Client"] = relationship(back_populates="attachments")

