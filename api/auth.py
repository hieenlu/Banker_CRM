"""JWT helpers for single-tenant API auth."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from api.config import ApiSettings


class AuthError(Exception):
    def __init__(self, detail: str, *, status_code: int = 401) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def create_access_token(
    settings: ApiSettings,
    *,
    subject: str,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
        "typ": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(settings: ApiSettings, token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Invalid token") from exc
    if payload.get("typ") != "access" or not payload.get("sub"):
        raise AuthError("Invalid token payload")
    return payload
