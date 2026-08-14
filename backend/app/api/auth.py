from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    AuthenticatedPrincipal,
    AuthPrincipal,
    CsrfProtectedPrincipal,
    require_mutation_permission,
    require_permission,
)
from app.auth.models import Permission, Role
from app.auth.schemas import (
    AssignableUserListResponse,
    LoginRequest,
    PasswordResetRequest,
    SessionResponse,
    UserCreateRequest,
    UserListResponse,
    UserMutationResponse,
    UserPatchRequest,
)
from app.auth.security import IdentityValidationError, PasswordPolicyError
from app.auth.service import (
    AuthConflictError,
    AuthNoChangeError,
    AuthNotFoundError,
    AuthVersionConflictError,
    FinalAdministratorError,
    assignable_user_response,
    authenticate_and_create_session,
    clear_auth_cookies,
    create_local_user,
    csrf_token_for_session,
    list_assignable_users,
    list_local_users,
    reset_local_user_password,
    revoke_session,
    set_auth_cookies,
    set_replacement_csrf_cookie,
    update_local_user,
    user_response,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db_session

router = APIRouter(prefix="/api/v1")
DatabaseSession = Annotated[Session, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
AdminReadPrincipal = Annotated[AuthPrincipal, Depends(require_permission(Permission.MANAGE_USERS))]
AdminMutationPrincipal = Annotated[
    AuthPrincipal, Depends(require_mutation_permission(Permission.MANAGE_USERS))
]
AssignmentPrincipal = Annotated[
    AuthPrincipal, Depends(require_permission(Permission.ASSIGN_INCIDENT))
]


@router.post(
    "/auth/login",
    tags=["authentication"],
    response_model=SessionResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Invalid local credentials."}},
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: DatabaseSession,
    settings: SettingsDependency,
) -> SessionResponse | JSONResponse:
    attempt = authenticate_and_create_session(
        session,
        settings,
        username=payload.username,
        password=payload.password,
        request_id=_request_id(request),
    )
    if attempt.issued is None:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": {
                    "code": "authentication_failed",
                    "message": "Invalid username or password.",
                    "request_id": _request_id(request),
                }
            },
        )
    set_auth_cookies(response, attempt.issued, settings)
    return SessionResponse(
        user=user_response(attempt.issued.user),
        expires_at=attempt.issued.auth_session.expires_at,
        csrf_token=attempt.issued.raw_csrf_token,
    )


@router.get("/auth/session", tags=["authentication"], response_model=SessionResponse)
def read_session(
    request: Request,
    response: Response,
    principal: AuthenticatedPrincipal,
    settings: SettingsDependency,
) -> SessionResponse:
    csrf_token, replaced = csrf_token_for_session(
        principal.session,
        settings,
        request.cookies.get(settings.auth_csrf_cookie_name),
    )
    if replaced:
        set_replacement_csrf_cookie(response, csrf_token, principal.session, settings)
    return SessionResponse(
        user=user_response(principal.user),
        expires_at=principal.session.expires_at,
        csrf_token=csrf_token,
    )


@router.post(
    "/auth/logout",
    tags=["authentication"],
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    request: Request,
    principal: CsrfProtectedPrincipal,
    session: DatabaseSession,
    settings: SettingsDependency,
) -> Response:
    revoke_session(
        session,
        principal.session,
        actor_user=principal.user,
        request_id=_request_id(request),
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response, settings)
    return response


@router.get("/users", tags=["local-users"], response_model=UserListResponse)
def read_users(
    session: DatabaseSession,
    principal: AdminReadPrincipal,
    role: Role | None = None,
    active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> UserListResponse:
    del principal
    users, total = list_local_users(
        session,
        role=role,
        active=active,
        limit=limit,
        offset=offset,
    )
    return UserListResponse(
        items=tuple(user_response(user) for user in users),
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/users",
    tags=["local-users"],
    response_model=UserMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreateRequest,
    request: Request,
    session: DatabaseSession,
    principal: AdminMutationPrincipal,
) -> UserMutationResponse:
    try:
        user = create_local_user(
            session,
            username=payload.username,
            display_name=payload.display_name,
            role=payload.role,
            password=payload.password,
            request_id=_request_id(request),
            actor_user_id=principal.user_id,
        )
    except AuthConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (IdentityValidationError, PasswordPolicyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return UserMutationResponse(user=user_response(user), operation="created")


@router.patch(
    "/users/{user_id}",
    tags=["local-users"],
    response_model=UserMutationResponse,
)
def patch_user(
    user_id: uuid.UUID,
    payload: UserPatchRequest,
    request: Request,
    session: DatabaseSession,
    principal: AdminMutationPrincipal,
) -> UserMutationResponse:
    try:
        user = update_local_user(
            session,
            user_id,
            display_name=payload.display_name,
            role=payload.role,
            active=payload.active,
            expected_version=payload.expected_version,
            actor_user_id=principal.user_id,
            request_id=_request_id(request),
        )
    except AuthNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AuthVersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FinalAdministratorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (AuthNoChangeError, IdentityValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return UserMutationResponse(user=user_response(user), operation="updated")


@router.post(
    "/users/{user_id}/password-reset",
    tags=["local-users"],
    response_model=UserMutationResponse,
)
def reset_user_password(
    user_id: uuid.UUID,
    payload: PasswordResetRequest,
    request: Request,
    session: DatabaseSession,
    principal: AdminMutationPrincipal,
) -> UserMutationResponse:
    try:
        user = reset_local_user_password(
            session,
            user_id,
            password=payload.password,
            expected_version=payload.expected_version,
            actor_user_id=principal.user_id,
            request_id=_request_id(request),
        )
    except AuthNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AuthVersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return UserMutationResponse(user=user_response(user), operation="password_reset")


@router.get(
    "/incident-assignees",
    tags=["local-users"],
    response_model=AssignableUserListResponse,
)
def read_incident_assignees(
    session: DatabaseSession,
    principal: AssignmentPrincipal,
) -> AssignableUserListResponse:
    del principal
    users = list_assignable_users(session)
    return AssignableUserListResponse(items=tuple(assignable_user_response(user) for user in users))


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unavailable")
