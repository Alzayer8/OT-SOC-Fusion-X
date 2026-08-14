from __future__ import annotations

import argparse
import getpass
import sys
import uuid

from pydantic import SecretStr

from app.auth.models import Role
from app.auth.security import IdentityValidationError, PasswordPolicyError
from app.auth.service import AuthConflictError, create_local_user
from app.core.config import get_settings
from app.db.session import session_scope
from app.incidents import models as incident_models
from app.lab import models as lab_models

# Register every v1.1 foreign-key target in the shared SQLAlchemy metadata for CLI use.
_MODEL_REGISTRATION = (incident_models, lab_models)


def main() -> int:
    parser = build_parser()
    arguments = parser.parse_args()
    password = _read_password(password_stdin=arguments.password_stdin)
    try:
        with session_scope(get_settings()) as session:
            user = create_local_user(
                session,
                username=arguments.username,
                display_name=arguments.display_name,
                role=Role(arguments.role),
                password=SecretStr(password),
                request_id=f"bootstrap-{uuid.uuid4().hex}",
                actor_user_id=None,
            )
    except (AuthConflictError, IdentityValidationError, PasswordPolicyError) as exc:
        print(f"Local user was not created: {exc}", file=sys.stderr)
        return 2
    print(f"Created local user {user.username} with role {user.role}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a local OT-SOC Fusion X user without exposing a password in argv."
    )
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role", required=True, choices=[role.value for role in Role])
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read one password line from standard input instead of prompting securely.",
    )
    return parser


def _read_password(*, password_stdin: bool) -> str:
    if password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
        if not password:
            raise SystemExit("A non-empty password line is required on standard input.")
        return password
    first = getpass.getpass("Password: ")
    second = getpass.getpass("Confirm password: ")
    if first != second:
        raise SystemExit("Passwords did not match.")
    return first


if __name__ == "__main__":
    raise SystemExit(main())
