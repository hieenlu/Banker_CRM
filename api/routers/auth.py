"""Auth routes: /auth/login, /auth/me."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from api.auth import create_access_token
from api.config import ApiSettings
from api.deps import CurrentUser, SettingsDep
from api.schemas.auth import LoginRequest, MeResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_token(settings: ApiSettings, username: str, password: str) -> TokenResponse:
    # compare_digest requires equal-length bytes; pad via hmac-style gate.
    user_ok = secrets.compare_digest(
        username.encode("utf-8"),
        settings.api_user.encode("utf-8"),
    ) if len(username) == len(settings.api_user) else False
    pass_ok = secrets.compare_digest(
        password.encode("utf-8"),
        settings.api_password.encode("utf-8"),
    ) if len(password) == len(settings.api_password) else False
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(settings, subject=username)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
def login_json(body: LoginRequest, settings: SettingsDep) -> TokenResponse:
    """JSON login for web/mobile clients."""
    return _issue_token(settings, body.username, body.password)


@router.post("/token", response_model=TokenResponse, include_in_schema=False)
def login_form(
    settings: SettingsDep,
    form: OAuth2PasswordRequestForm = Depends(),
) -> TokenResponse:
    """OAuth2 password form (Swagger Authorize)."""
    return _issue_token(settings, form.username, form.password)


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser) -> MeResponse:
    return MeResponse(username=user["username"], authenticated=True)
