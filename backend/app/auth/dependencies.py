from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import ROLE_PERMISSIONS, AuthSession, LocalUser, Permission, Role
from app.auth.security import keyed_token_digest, safe_token_shape
from app.core.config import Settings, get_settings
from app.db.session import get_db_session

_LAST_SEEN_WRITE_INTERVAL = timedelta(minutes=5)
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_DOCUMENTED_SESSION_COOKIE = APIKeyCookie(
    name="otsoc_session",
    scheme_name="OTSOCSessionCookie",
    description="Opaque HttpOnly local session cookie. The configured runtime name may differ.",
    auto_error=False,
)


@dataclass(frozen=True)
class AuthPrincipal:
    user: LocalUser
    session: AuthSession
    role: Role
    permissions: frozenset[Permission]

    @property
    def actor_id(self) -> str:
        return self.user.username

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.user_id

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions


def require_authenticated(
    request: Request,
    documented_cookie: Annotated[str | None, Security(_DOCUMENTED_SESSION_COOKIE)],
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthPrincipal:
    del documented_cookie
    raw_token = request.cookies.get(settings.auth_session_cookie_name)
    if not safe_token_shape(raw_token):
        raise _authentication_required()
    assert raw_token is not None
    digest = keyed_token_digest(settings.auth_session_secret.get_secret_value(), raw_token)
    row = session.execute(
        select(AuthSession, LocalUser)
        .join(LocalUser, LocalUser.user_id == AuthSession.user_id)
        .where(AuthSession.token_digest == digest)
    ).one_or_none()
    if row is None:
        raise _authentication_required()
    auth_session, user = row
    now = datetime.now(UTC)
    if auth_session.revoked_at is not None or auth_session.expires_at <= now or not user.active:
        raise _authentication_required()
    try:
        role = Role(user.role)
    except ValueError as exc:
        raise _authentication_required() from exc
    if now - auth_session.last_seen_at >= _LAST_SEEN_WRITE_INTERVAL:
        auth_session.last_seen_at = now
    return AuthPrincipal(
        user=user,
        session=auth_session,
        role=role,
        permissions=ROLE_PERMISSIONS[role],
    )


def require_csrf_protection(
    request: Request,
    principal: Annotated[AuthPrincipal, Depends(require_authenticated)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthPrincipal:
    if request.method.upper() not in _UNSAFE_METHODS:
        return principal
    origin = request.headers.get("Origin")
    allowed_origins = frozenset(value.rstrip("/") for value in settings.cors_origin_strings)
    if origin is None or origin.rstrip("/") not in allowed_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The request origin is not approved for local session mutation.",
        )
    header_token = request.headers.get("X-CSRF-Token")
    cookie_token = request.cookies.get(settings.auth_csrf_cookie_name)
    if (
        not safe_token_shape(header_token)
        or not safe_token_shape(cookie_token)
        or not hmac.compare_digest(header_token or "", cookie_token or "")
    ):
        raise _csrf_rejected()
    assert header_token is not None
    presented_digest = keyed_token_digest(
        settings.auth_session_secret.get_secret_value(), header_token
    )
    if not hmac.compare_digest(presented_digest, principal.session.csrf_digest):
        raise _csrf_rejected()
    return principal


def require_permission(permission: Permission) -> Callable[..., AuthPrincipal]:
    def dependency(
        principal: Annotated[AuthPrincipal, Depends(require_authenticated)],
    ) -> AuthPrincipal:
        if not principal.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The authenticated local user does not have the required permission.",
            )
        return principal

    dependency.__name__ = f"require_{permission.name.casefold()}"
    return dependency


def require_mutation_permission(permission: Permission) -> Callable[..., AuthPrincipal]:
    def dependency(
        principal: Annotated[AuthPrincipal, Depends(require_csrf_protection)],
    ) -> AuthPrincipal:
        if not principal.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The authenticated local user does not have the required permission.",
            )
        return principal

    dependency.__name__ = f"require_csrf_{permission.name.casefold()}"
    return dependency


AuthenticatedPrincipal = Annotated[AuthPrincipal, Depends(require_authenticated)]
CsrfProtectedPrincipal = Annotated[AuthPrincipal, Depends(require_csrf_protection)]
CurrentPrincipal = AuthenticatedPrincipal


def _authentication_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication is required.",
    )


def _csrf_rejected() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="The CSRF validation failed.",
    )
