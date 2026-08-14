from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, SecretStr, model_validator

from app.auth.models import Role

LoginPassword = Annotated[SecretStr, Field(min_length=1, max_length=128)]
NewPassword = Annotated[SecretStr, Field(min_length=12, max_length=128)]


class StrictAuthModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=False,
        allow_inf_nan=False,
    )


class LoginRequest(StrictAuthModel):
    username: str = Field(min_length=1, max_length=64)
    password: LoginPassword


class UserCreateRequest(StrictAuthModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=120)
    role: Role
    password: NewPassword


class UserPatchRequest(StrictAuthModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Role | None = None
    active: bool | None = None
    expected_version: int = Field(ge=1)

    @model_validator(mode="after")
    def require_change(self) -> UserPatchRequest:
        if self.display_name is None and self.role is None and self.active is None:
            raise ValueError("At least one local-user field must be changed.")
        return self


class PasswordResetRequest(StrictAuthModel):
    password: NewPassword
    expected_version: int = Field(ge=1)


class UserResponse(StrictAuthModel):
    user_id: uuid.UUID
    username: str
    display_name: str
    role: Role
    active: bool
    version: int
    created_at: AwareDatetime
    updated_at: AwareDatetime
    password_changed_at: AwareDatetime


class SessionResponse(StrictAuthModel):
    authenticated: Literal[True] = True
    user: UserResponse
    expires_at: AwareDatetime
    csrf_token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class UserListResponse(StrictAuthModel):
    items: tuple[UserResponse, ...]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class AssignableUserResponse(StrictAuthModel):
    user_id: uuid.UUID
    username: str
    display_name: str
    role: Literal[Role.ADMIN, Role.SOC_ANALYST]


class AssignableUserListResponse(StrictAuthModel):
    items: tuple[AssignableUserResponse, ...]


class UserMutationResponse(StrictAuthModel):
    user: UserResponse
    operation: Literal["created", "updated", "password_reset"]
