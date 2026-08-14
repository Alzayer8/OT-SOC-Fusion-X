from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import Response
from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.audit import append_soc_audit_event
from app.auth.models import (
    AuthSession,
    LocalUser,
    Role,
    SocAuditAction,
    SocAuditResult,
)
from app.auth.schemas import AssignableUserResponse, UserResponse
from app.auth.security import (
    IdentityValidationError,
    hash_password,
    keyed_token_digest,
    new_opaque_token,
    normalize_display_name,
    normalize_username,
    safe_token_shape,
    verify_password_or_dummy,
)
from app.core.config import Settings


class AuthServiceError(ValueError):
    pass


class AuthNotFoundError(AuthServiceError):
    pass


class AuthConflictError(AuthServiceError):
    pass


class AuthVersionConflictError(AuthServiceError):
    pass


class FinalAdministratorError(AuthServiceError):
    pass


class AuthNoChangeError(AuthServiceError):
    pass


@dataclass(frozen=True)
class IssuedSession:
    user: LocalUser
    auth_session: AuthSession
    raw_session_token: str = field(repr=False)
    raw_csrf_token: str = field(repr=False)


@dataclass(frozen=True)
class LoginAttempt:
    issued: IssuedSession | None

    @property
    def accepted(self) -> bool:
        return self.issued is not None


def authenticate_and_create_session(
    session: Session,
    settings: Settings,
    *,
    username: str,
    password: SecretStr,
    request_id: str,
    now: datetime | None = None,
) -> LoginAttempt:
    occurred_at = now or datetime.now(UTC)
    try:
        normalized_username = normalize_username(username)
    except IdentityValidationError:
        normalized_username = None
    user = (
        session.scalar(select(LocalUser).where(LocalUser.username == normalized_username))
        if normalized_username is not None
        else None
    )
    password_valid = verify_password_or_dummy(
        password.get_secret_value(), user.password_hash if user is not None else None
    )
    if user is None or not password_valid or not user.active:
        append_soc_audit_event(
            session,
            action=SocAuditAction.LOGIN_FAILED,
            result=SocAuditResult.DENIED,
            request_id=request_id,
            subject_user_id=user.user_id if user is not None else None,
            subject_label=normalized_username,
            safe_reason="Invalid local credentials or inactive account.",
            details={"reason_code": "INVALID_CREDENTIALS"},
            occurred_at=occurred_at,
        )
        return LoginAttempt(issued=None)

    raw_session_token = new_opaque_token()
    raw_csrf_token = new_opaque_token()
    secret = settings.auth_session_secret.get_secret_value()
    expires_at = occurred_at + timedelta(minutes=settings.auth_session_ttl_minutes)
    auth_session = AuthSession(
        session_id=uuid.uuid4(),
        user_id=user.user_id,
        token_digest=keyed_token_digest(secret, raw_session_token),
        csrf_digest=keyed_token_digest(secret, raw_csrf_token),
        created_at=occurred_at,
        expires_at=expires_at,
        last_seen_at=occurred_at,
        revoked_at=None,
    )
    session.add(auth_session)
    append_soc_audit_event(
        session,
        action=SocAuditAction.LOGIN_SUCCEEDED,
        result=SocAuditResult.ACCEPTED,
        request_id=request_id,
        actor_user_id=user.user_id,
        subject_user_id=user.user_id,
        subject_label=user.username,
        details={"role": user.role},
        occurred_at=occurred_at,
    )
    return LoginAttempt(
        issued=IssuedSession(
            user=user,
            auth_session=auth_session,
            raw_session_token=raw_session_token,
            raw_csrf_token=raw_csrf_token,
        )
    )


def csrf_token_for_session(
    auth_session: AuthSession,
    settings: Settings,
    presented_cookie: str | None,
) -> tuple[str, bool]:
    secret = settings.auth_session_secret.get_secret_value()
    if safe_token_shape(presented_cookie):
        assert presented_cookie is not None
        digest = keyed_token_digest(secret, presented_cookie)
        if hmac.compare_digest(digest, auth_session.csrf_digest):
            return presented_cookie, False
    replacement = new_opaque_token()
    auth_session.csrf_digest = keyed_token_digest(secret, replacement)
    return replacement, True


def revoke_session(
    session: Session,
    auth_session: AuthSession,
    *,
    actor_user: LocalUser,
    request_id: str,
    now: datetime | None = None,
) -> None:
    occurred_at = now or datetime.now(UTC)
    if auth_session.revoked_at is None:
        auth_session.revoked_at = occurred_at
    append_soc_audit_event(
        session,
        action=SocAuditAction.LOGOUT,
        result=SocAuditResult.ACCEPTED,
        request_id=request_id,
        actor_user_id=actor_user.user_id,
        subject_user_id=actor_user.user_id,
        subject_label=actor_user.username,
        details={},
        occurred_at=occurred_at,
    )


def create_local_user(
    session: Session,
    *,
    username: str,
    display_name: str,
    role: Role,
    password: SecretStr,
    request_id: str,
    actor_user_id: uuid.UUID | None,
    now: datetime | None = None,
) -> LocalUser:
    occurred_at = now or datetime.now(UTC)
    normalized_username = normalize_username(username)
    normalized_display_name = normalize_display_name(display_name)
    if session.scalar(select(LocalUser.user_id).where(LocalUser.username == normalized_username)):
        raise AuthConflictError("The local username already exists.")
    user = LocalUser(
        user_id=uuid.uuid4(),
        username=normalized_username,
        display_name=normalized_display_name,
        role=role.value,
        password_hash=hash_password(password.get_secret_value()),
        active=True,
        version=1,
        created_at=occurred_at,
        updated_at=occurred_at,
        password_changed_at=occurred_at,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise AuthConflictError("The local username already exists.") from exc
    append_soc_audit_event(
        session,
        action=SocAuditAction.LOCAL_USER_CREATED,
        result=SocAuditResult.ACCEPTED,
        request_id=request_id,
        actor_user_id=actor_user_id,
        subject_user_id=user.user_id,
        subject_label=user.username,
        details={"role": role.value, "active": True},
        occurred_at=occurred_at,
    )
    return user


def list_local_users(
    session: Session,
    *,
    role: Role | None,
    active: bool | None,
    limit: int,
    offset: int,
) -> tuple[tuple[LocalUser, ...], int]:
    filters = []
    if role is not None:
        filters.append(LocalUser.role == role.value)
    if active is not None:
        filters.append(LocalUser.active.is_(active))
    statement = select(LocalUser).where(*filters)
    count_statement = select(func.count()).select_from(LocalUser).where(*filters)
    users = session.scalars(
        statement.order_by(LocalUser.username, LocalUser.user_id).offset(offset).limit(limit)
    ).all()
    total = int(session.scalar(count_statement) or 0)
    return tuple(users), total


def list_assignable_users(session: Session) -> tuple[LocalUser, ...]:
    return tuple(
        session.scalars(
            select(LocalUser)
            .where(
                LocalUser.active.is_(True),
                LocalUser.role.in_((Role.ADMIN.value, Role.SOC_ANALYST.value)),
            )
            .order_by(LocalUser.display_name, LocalUser.username, LocalUser.user_id)
            .limit(100)
        ).all()
    )


def update_local_user(
    session: Session,
    user_id: uuid.UUID,
    *,
    display_name: str | None,
    role: Role | None,
    active: bool | None,
    expected_version: int,
    actor_user_id: uuid.UUID,
    request_id: str,
    now: datetime | None = None,
) -> LocalUser:
    occurred_at = now or datetime.now(UTC)
    active_admins = session.scalars(
        select(LocalUser)
        .where(LocalUser.active.is_(True), LocalUser.role == Role.ADMIN.value)
        .order_by(LocalUser.user_id)
        .with_for_update()
    ).all()
    target = session.scalar(select(LocalUser).where(LocalUser.user_id == user_id).with_for_update())
    if target is None:
        raise AuthNotFoundError("The local user was not found.")
    if target.version != expected_version:
        raise AuthVersionConflictError("The local-user version is stale.")
    next_display_name = (
        normalize_display_name(display_name) if display_name is not None else target.display_name
    )
    next_role = role.value if role is not None else target.role
    next_active = active if active is not None else target.active
    removes_active_admin = (
        target.active
        and target.role == Role.ADMIN.value
        and (not next_active or next_role != Role.ADMIN.value)
    )
    if removes_active_admin and len(active_admins) <= 1:
        raise FinalAdministratorError(
            "The final active administrator cannot be disabled or demoted."
        )
    changes = {
        "display_name": target.display_name != next_display_name,
        "role": target.role != next_role,
        "active": target.active != next_active,
    }
    changed_fields = sorted(field for field, changed in changes.items() if changed)
    if not changed_fields:
        raise AuthNoChangeError("The local-user update does not change any values.")
    target.display_name = next_display_name
    target.role = next_role
    target.active = next_active
    target.version += 1
    target.updated_at = occurred_at
    if not next_active:
        _revoke_user_sessions(session, target.user_id, occurred_at)
    append_soc_audit_event(
        session,
        action=SocAuditAction.LOCAL_USER_UPDATED,
        result=SocAuditResult.ACCEPTED,
        request_id=request_id,
        actor_user_id=actor_user_id,
        subject_user_id=target.user_id,
        subject_label=target.username,
        details={
            "changed_fields": changed_fields,
            "role": target.role,
            "active": target.active,
            "version": target.version,
        },
        occurred_at=occurred_at,
    )
    return target


def reset_local_user_password(
    session: Session,
    user_id: uuid.UUID,
    *,
    password: SecretStr,
    expected_version: int,
    actor_user_id: uuid.UUID,
    request_id: str,
    now: datetime | None = None,
) -> LocalUser:
    occurred_at = now or datetime.now(UTC)
    target = session.scalar(select(LocalUser).where(LocalUser.user_id == user_id).with_for_update())
    if target is None:
        raise AuthNotFoundError("The local user was not found.")
    if target.version != expected_version:
        raise AuthVersionConflictError("The local-user version is stale.")
    target.password_hash = hash_password(password.get_secret_value())
    target.password_changed_at = occurred_at
    target.updated_at = occurred_at
    target.version += 1
    revoked_count = _revoke_user_sessions(session, target.user_id, occurred_at)
    append_soc_audit_event(
        session,
        action=SocAuditAction.LOCAL_USER_PASSWORD_RESET,
        result=SocAuditResult.ACCEPTED,
        request_id=request_id,
        actor_user_id=actor_user_id,
        subject_user_id=target.user_id,
        subject_label=target.username,
        details={"revoked_sessions": revoked_count, "version": target.version},
        occurred_at=occurred_at,
    )
    return target


def user_response(user: LocalUser) -> UserResponse:
    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        role=Role(user.role),
        active=user.active,
        version=user.version,
        created_at=user.created_at,
        updated_at=user.updated_at,
        password_changed_at=user.password_changed_at,
    )


def assignable_user_response(user: LocalUser) -> AssignableUserResponse:
    role = Role(user.role)
    if role not in {Role.ADMIN, Role.SOC_ANALYST}:
        raise AuthServiceError("The local user is not assignable.")
    return AssignableUserResponse(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        role=role,
    )


def set_auth_cookies(response: Response, issued: IssuedSession, settings: Settings) -> None:
    max_age = max(0, int((issued.auth_session.expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=issued.raw_session_token,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/",
    )
    _set_csrf_cookie(response, issued.raw_csrf_token, max_age=max_age, settings=settings)


def set_replacement_csrf_cookie(
    response: Response,
    csrf_token: str,
    auth_session: AuthSession,
    settings: Settings,
) -> None:
    max_age = max(0, int((auth_session.expires_at - datetime.now(UTC)).total_seconds()))
    _set_csrf_cookie(response, csrf_token, max_age=max_age, settings=settings)


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    for name, httponly in (
        (settings.auth_session_cookie_name, True),
        (settings.auth_csrf_cookie_name, False),
    ):
        response.set_cookie(
            key=name,
            value="",
            max_age=0,
            expires=0,
            httponly=httponly,
            secure=settings.auth_cookie_secure,
            samesite="strict",
            path="/",
        )


def _set_csrf_cookie(
    response: Response,
    csrf_token: str,
    *,
    max_age: int,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=settings.auth_csrf_cookie_name,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/",
    )


def _revoke_user_sessions(session: Session, user_id: uuid.UUID, revoked_at: datetime) -> int:
    result = cast(
        CursorResult[Any],
        session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        ),
    )
    return int(result.rowcount or 0)
