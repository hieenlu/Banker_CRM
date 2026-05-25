"""Import clients, investments, and incomes from a multi-sheet Excel workbook."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from models import Client, Income, Investment

CLIENT_COLUMNS = [
    "client_key",
    "name",
    "birthday",
    "address",
    "phone_number",
    "email",
    "notes",
    "home_insurance_amount_covered",
    "home_insurance_expiry_date",
    "home_insurance_insured_premium",
]

INVESTMENT_COLUMNS = [
    "client_key",
    "asset_type",
    "ticker_name",
    "ticker_identifier",
    "quantity",
    "unit",
    "principal",
    "purchase_price",
    "purchase_date",
    "tenor",
    "interest_rate",
    "principal_payment",
    "ytm",
    "current_price",
    "expected_coupon",
    "received_coupon",
    "maturity_date",
    "notes",
    "is_done",
]

INCOME_COLUMNS = [
    "client_key",
    "income_type",
    "income_mode",
    "amount",
    "concurrent",
    "note",
    "is_done",
]

OBLIGATION_COLUMNS = [
    "client_key",
    "obligation_type",
    "amount",
    "amount_covered",
    "expiry_date",
    "insured_premium",
    "concurrent",
    "income_mode",
    "note",
    "is_done",
]

OBLIGATION_TYPES_ALLOWED = ["Home Insurance", "Other Obligations"]

ASSET_TYPES_ALLOWED = [
    "VN_Stock",
    "US_Stock",
    "Commodity",
    "Real Estate",
    "Bond",
    "Debt",
    "Term Deposit",
    "CD",
    "Crypto",
    "Cash",
]

INCOME_TYPES_ALLOWED = ["Salary", "Dividends", "Other Incomes", "Other Obligations", "Others"]


@dataclass
class ImportResult:
    clients_created: int = 0
    investments_created: int = 0
    incomes_created: int = 0
    obligations_created: int = 0
    home_insurance_set: int = 0
    clients_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _cell_str(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _parse_bool(value: Any, default: bool = False) -> bool:
    s = _cell_str(value).lower()
    if not s:
        return default
    return s in {"1", "true", "yes", "y", "x", "on"}


def _parse_float(value: Any) -> float | None:
    s = _cell_str(value)
    if not s:
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = _cell_str(value)
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return pd.to_datetime(s, dayfirst=True).date()
    except Exception:
        return None


def _normalize_asset_type(raw: str) -> str:
    s = raw.strip()
    low = s.lower()
    if low in {"certificate of deposit", "cd"}:
        return "CD"
    if low == "stock":
        return "VN_Stock"
    if low == "vn_stock":
        return "VN_Stock"
    if low == "us_stock":
        return "US_Stock"
    if low == "real estate":
        return "Real Estate"
    if low == "term deposit":
        return "Term Deposit"
    if low in {a.lower() for a in ASSET_TYPES_ALLOWED}:
        for a in ASSET_TYPES_ALLOWED:
            if a.lower() == low:
                return a
    return s


def _default_currency(asset_type: str) -> str:
    k = asset_type.lower()
    return "USD" if k in {"us_stock", "crypto"} else "VND"


def _read_sheet(xls: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    if sheet_name not in xls.sheet_names:
        return pd.DataFrame()
    df = pd.read_excel(xls, sheet_name=sheet_name, dtype=object)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def _example_clients_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "client_key": "CLIENT001",
                "name": "Nguyen Van A",
                "birthday": "1985-06-15",
                "address": "123 Le Loi, HCMC",
                "phone_number": "+84901234567",
                "email": "nguyen.a@example.com",
                "notes": "Sample client — replace or delete this row",
                "home_insurance_amount_covered": "",
                "home_insurance_expiry_date": "",
                "home_insurance_insured_premium": "",
            },
        ]
    )


def _example_investments_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "client_key": "CLIENT001",
                "asset_type": "VN_Stock",
                "ticker_name": "",
                "ticker_identifier": "VNM",
                "quantity": 100,
                "unit": "",
                "principal": "",
                "purchase_price": 75000,
                "purchase_date": "",
                "tenor": "",
                "interest_rate": "",
                "principal_payment": "",
                "ytm": "",
                "current_price": "",
                "expected_coupon": "",
                "received_coupon": "",
                "maturity_date": "",
                "notes": "Example VN stock",
                "is_done": "no",
            },
            {
                "client_key": "CLIENT001",
                "asset_type": "Debt",
                "ticker_name": "",
                "ticker_identifier": "Home loan",
                "quantity": 1,
                "unit": "",
                "principal": 2000000000,
                "purchase_price": 0,
                "purchase_date": "",
                "tenor": "",
                "interest_rate": 8.5,
                "principal_payment": 15000000,
                "ytm": "",
                "current_price": "",
                "expected_coupon": "",
                "received_coupon": "",
                "maturity_date": "",
                "notes": "",
                "is_done": "no",
            },
        ]
    )


def _example_incomes_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "client_key": "CLIENT001",
                "income_type": "Salary",
                "income_mode": "Actual",
                "amount": 50000000,
                "concurrent": "yes",
                "note": "Monthly salary",
                "is_done": "no",
            },
            {
                "client_key": "CLIENT001",
                "income_type": "Dividends",
                "income_mode": "Actual",
                "amount": 2000000,
                "concurrent": "yes",
                "note": "",
                "is_done": "no",
            },
        ]
    )


def _example_obligations_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "client_key": "CLIENT001",
                "obligation_type": "Home Insurance",
                "amount": "",
                "amount_covered": 5000000000,
                "expiry_date": "2026-12-31",
                "insured_premium": 15000000,
                "concurrent": "",
                "income_mode": "",
                "note": "Annual home policy",
                "is_done": "",
            },
            {
                "client_key": "CLIENT001",
                "obligation_type": "Other Obligations",
                "amount": 5000000,
                "amount_covered": "",
                "expiry_date": "",
                "insured_premium": "",
                "concurrent": "yes",
                "income_mode": "Actual",
                "note": "School fees (monthly)",
                "is_done": "no",
            },
        ]
    )


def _instructions_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Topic": [
                "Overview",
                "client_key",
                "Dates",
                "Yes/No fields",
                "Asset types",
                "Income types",
                "Obligation types",
                "Obligations sheet",
                "Sheets",
            ],
            "Details": [
                "Fill Clients first. Use the same client_key on other sheets to link rows to one person.",
                "Required unique ID per client in this file (e.g. CLIENT001). Not stored in the database.",
                "Use YYYY-MM-DD (e.g. 2025-12-31) or DD/MM/YYYY.",
                "concurrent, is_done: yes/no, true/false, or 1/0.",
                ", ".join(ASSET_TYPES_ALLOWED),
                ", ".join(INCOME_TYPES_ALLOWED) + ' ("Others" → Other Incomes). Do not put obligations here.',
                ", ".join(OBLIGATION_TYPES_ALLOWED),
                "Home Insurance: fill amount_covered, expiry_date, insured_premium. "
                "Other Obligations: fill amount + concurrent (monthly cashflow obligation).",
                "Clients (required), Investments, Incomes, Obligations (all optional except Clients).",
            ],
        }
    )


def build_import_template_bytes() -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        _instructions_df().to_excel(writer, sheet_name="Instructions", index=False)
        _example_clients_df().to_excel(writer, sheet_name="Clients", index=False)
        _example_investments_df().to_excel(writer, sheet_name="Investments", index=False)
        _example_incomes_df().to_excel(writer, sheet_name="Incomes", index=False)
        _example_obligations_df().to_excel(writer, sheet_name="Obligations", index=False)
    buf.seek(0)
    return buf.getvalue()


def import_clients_workbook(
    file_bytes: bytes,
    session: Session,
    *,
    skip_existing_names: bool = True,
) -> ImportResult:
    result = ImportResult()
    try:
        xls = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception as e:
        result.errors.append(f"Could not read Excel file: {e}")
        return result

    df_clients = _read_sheet(xls, "Clients")
    df_investments = _read_sheet(xls, "Investments")
    df_incomes = _read_sheet(xls, "Incomes")
    df_obligations = _read_sheet(xls, "Obligations")

    if df_clients.empty:
        result.errors.append("Clients sheet is empty or missing.")
        return result

    from sqlalchemy import select

    existing_names = {
        (row or "").strip().lower()
        for row in session.execute(select(Client.name)).scalars().all()
    }

    client_key_to_id: dict[str, int] = {}

    for row_idx, row in df_clients.iterrows():
        line = int(row_idx) + 2
        client_key = _cell_str(row.get("client_key"))
        name = _cell_str(row.get("name"))
        if not client_key:
            result.errors.append(f"Clients row {line}: client_key is required.")
            continue
        if not name:
            result.errors.append(f"Clients row {line}: name is required.")
            continue
        if client_key in client_key_to_id:
            result.errors.append(f"Clients row {line}: duplicate client_key '{client_key}'.")
            continue

        name_key = name.lower()
        if skip_existing_names and name_key in existing_names:
            result.warnings.append(f"Clients row {line}: skipped '{name}' (name already exists).")
            result.clients_skipped += 1
            continue

        c = Client(
            name=name,
            birthday=_parse_date(row.get("birthday")),
            address=_cell_str(row.get("address")) or None,
            phone_number=_cell_str(row.get("phone_number")) or None,
            email=_cell_str(row.get("email")) or None,
            notes=_cell_str(row.get("notes")) or None,
            home_insurance_amount_covered=_parse_float(row.get("home_insurance_amount_covered")),
            home_insurance_expiry_date=_parse_date(row.get("home_insurance_expiry_date")),
            home_insurance_insured_premium=_parse_float(row.get("home_insurance_insured_premium")),
        )
        session.add(c)
        session.flush()
        client_key_to_id[client_key] = c.id
        existing_names.add(name_key)
        result.clients_created += 1

    for row_idx, row in df_investments.iterrows():
        line = int(row_idx) + 2
        client_key = _cell_str(row.get("client_key"))
        asset_raw = _cell_str(row.get("asset_type"))
        if not client_key and not asset_raw:
            continue
        if not client_key:
            result.errors.append(f"Investments row {line}: client_key is required.")
            continue
        if client_key not in client_key_to_id:
            result.errors.append(f"Investments row {line}: unknown client_key '{client_key}'.")
            continue
        if not asset_raw:
            result.errors.append(f"Investments row {line}: asset_type is required.")
            continue

        asset_type = _normalize_asset_type(asset_raw)
        if asset_type not in ASSET_TYPES_ALLOWED and asset_type.lower() not in {a.lower() for a in ASSET_TYPES_ALLOWED}:
            result.warnings.append(
                f"Investments row {line}: asset_type '{asset_raw}' may not be recognized; importing as-is."
            )

        asset_kind = asset_type.lower()
        is_bond = asset_kind == "bond"
        is_stock = asset_kind in {"stock", "vn_stock", "us_stock", "commodity", "crypto"}
        is_real_estate = asset_kind == "real estate"
        is_debt = asset_kind == "debt"

        qty = _parse_float(row.get("quantity")) or 0.0
        unit_val = _parse_float(row.get("unit"))
        principal = _parse_float(row.get("principal"))
        purchase_price = _parse_float(row.get("purchase_price")) or 0.0

        inv = Investment(
            client_id=client_key_to_id[client_key],
            asset_type=asset_type,
            currency=_default_currency(asset_type),
            ticker_name=_cell_str(row.get("ticker_name")) or None,
            ticker_identifier=_cell_str(row.get("ticker_identifier")) or None,
            quantity=qty,
            unit=unit_val if is_bond and unit_val is not None else (qty if is_stock else None),
            principal=principal,
            purchase_price=purchase_price,
            purchase_date=_parse_date(row.get("purchase_date")),
            tenor=_cell_str(row.get("tenor")) or None,
            interest_rate=_parse_float(row.get("interest_rate")),
            principal_payment=_parse_float(row.get("principal_payment")) if is_debt else None,
            ytm=_parse_float(row.get("ytm")) if is_bond else None,
            current_price=_parse_float(row.get("current_price"))
            if (is_bond or is_real_estate)
            else None,
            expected_coupon=_parse_float(row.get("expected_coupon")) if is_bond else None,
            received_coupon=_parse_float(row.get("received_coupon")) if is_bond else None,
            maturity_date=_parse_date(row.get("maturity_date")),
            is_done=_parse_bool(row.get("is_done")),
            notes=_cell_str(row.get("notes")) or None,
        )
        session.add(inv)
        result.investments_created += 1

    for row_idx, row in df_incomes.iterrows():
        line = int(row_idx) + 2
        client_key = _cell_str(row.get("client_key"))
        income_type_raw = _cell_str(row.get("income_type"))
        if not client_key and not income_type_raw:
            continue
        if not client_key:
            result.errors.append(f"Incomes row {line}: client_key is required.")
            continue
        if client_key not in client_key_to_id:
            result.errors.append(f"Incomes row {line}: unknown client_key '{client_key}'.")
            continue
        if not income_type_raw:
            result.errors.append(f"Incomes row {line}: income_type is required.")
            continue

        income_type = income_type_raw
        if income_type == "Others":
            income_type = "Other Incomes"

        amount = _parse_float(row.get("amount"))
        if amount is None:
            result.errors.append(f"Incomes row {line}: amount is required.")
            continue

        mode = _cell_str(row.get("income_mode")) or "Actual"
        if mode not in {"Actual", "Forecast"}:
            result.warnings.append(f"Incomes row {line}: invalid income_mode '{mode}', using Actual.")
            mode = "Actual"

        inc = Income(
            client_id=client_key_to_id[client_key],
            income_type=income_type,
            income_mode=mode,
            amount=float(amount),
            concurrent=_parse_bool(row.get("concurrent")),
            is_done=_parse_bool(row.get("is_done")),
            note=_cell_str(row.get("note")) or None,
        )
        session.add(inc)
        result.incomes_created += 1

    for row_idx, row in df_obligations.iterrows():
        line = int(row_idx) + 2
        client_key = _cell_str(row.get("client_key"))
        obligation_type_raw = _cell_str(row.get("obligation_type"))
        if not client_key and not obligation_type_raw:
            continue
        if not client_key:
            result.errors.append(f"Obligations row {line}: client_key is required.")
            continue
        if client_key not in client_key_to_id:
            result.errors.append(f"Obligations row {line}: unknown client_key '{client_key}'.")
            continue
        if not obligation_type_raw:
            result.errors.append(f"Obligations row {line}: obligation_type is required.")
            continue

        obligation_type = obligation_type_raw.strip()
        obligation_low = obligation_type.lower()

        if obligation_low == "home insurance":
            client = session.get(Client, client_key_to_id[client_key])
            if not client:
                result.errors.append(f"Obligations row {line}: client not found.")
                continue
            covered = _parse_float(row.get("amount_covered"))
            expiry = _parse_date(row.get("expiry_date"))
            premium = _parse_float(row.get("insured_premium"))
            if covered is None and expiry is None and premium is None:
                result.errors.append(
                    f"Obligations row {line}: Home Insurance needs at least one of "
                    "amount_covered, expiry_date, insured_premium."
                )
                continue
            if covered is not None:
                client.home_insurance_amount_covered = covered
            if expiry is not None:
                client.home_insurance_expiry_date = expiry
            if premium is not None:
                client.home_insurance_insured_premium = premium
            note = _cell_str(row.get("note"))
            if note:
                client.notes = f"{client.notes}\n{note}".strip() if client.notes else note
            result.home_insurance_set += 1
            result.obligations_created += 1
            continue

        if obligation_low in {"other obligations", "other obligation"}:
            amount = _parse_float(row.get("amount"))
            if amount is None:
                amount = _parse_float(row.get("amount_covered"))
            if amount is None:
                result.errors.append(f"Obligations row {line}: amount is required for Other Obligations.")
                continue
            mode = _cell_str(row.get("income_mode")) or "Actual"
            if mode not in {"Actual", "Forecast"}:
                result.warnings.append(f"Obligations row {line}: invalid income_mode '{mode}', using Actual.")
                mode = "Actual"
            inc = Income(
                client_id=client_key_to_id[client_key],
                income_type="Other Obligations",
                income_mode=mode,
                amount=float(amount),
                concurrent=_parse_bool(row.get("concurrent")),
                is_done=_parse_bool(row.get("is_done")),
                note=_cell_str(row.get("note")) or None,
            )
            session.add(inc)
            result.incomes_created += 1
            result.obligations_created += 1
            continue

        result.errors.append(
            f"Obligations row {line}: unknown obligation_type '{obligation_type_raw}'. "
            f"Use: {', '.join(OBLIGATION_TYPES_ALLOWED)}."
        )

    if result.errors:
        session.rollback()
    elif (
        result.clients_created > 0
        or result.investments_created > 0
        or result.incomes_created > 0
        or result.obligations_created > 0
    ):
        session.commit()
    elif result.clients_skipped > 0:
        result.warnings.append("No new clients were created (all names already exist).")
    else:
        session.rollback()
        result.warnings.append("Nothing to import.")

    return result
