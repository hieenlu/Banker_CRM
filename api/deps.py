"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from sqlalchemy.orm import Session

from api.auth import AuthError, decode_access_token
from api.config import ApiSettings, get_settings
from database import init_db, session_factory

_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)
_bearer = HTTPBearer(auto_error=False)
_initialized_urls: set[str] = set()


def reset_db_state() -> None:
    """Test helper — clear cached init flags."""
    _initialized_urls.clear()
    get_settings.cache_clear()


def get_db() -> Generator[Session, None, None]:
    settings = get_settings()
    if settings.db_url not in _initialized_urls:
        init_db(settings.db_url)
        _initialized_urls.add(settings.db_url)
    factory = session_factory(settings.db_url)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_current_user(
    settings: Annotated[ApiSettings, Depends(get_settings)],
    oauth_token: Annotated[str | None, Depends(_oauth2)] = None,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> dict:
    token = oauth_token or (bearer.credentials if bearer else None)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(settings, token)
    except AuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return {"username": str(payload["sub"]), "claims": payload}


DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]
SettingsDep = Annotated[ApiSettings, Depends(get_settings)]
