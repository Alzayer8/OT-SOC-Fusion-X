from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re
import secrets
import unicodedata
from functools import lru_cache

PASSWORD_SCHEME = "otsoc-scrypt"
PASSWORD_SCHEME_VERSION = 1
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SCRYPT_SALT_BYTES = 16
SCRYPT_MAXMEM = 128 * 1024 * 1024
MIN_PASSWORD_CHARACTERS = 12
MAX_PASSWORD_CHARACTERS = 128
MAX_PASSWORD_BYTES = 512
OPAQUE_TOKEN_BYTES = 32
OPAQUE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")


class PasswordPolicyError(ValueError):
    pass


class IdentityValidationError(ValueError):
    pass


def normalize_username(value: str) -> str:
    normalized = value.strip().casefold()
    if USERNAME_PATTERN.fullmatch(normalized) is None:
        raise IdentityValidationError(
            "Username must contain 3-64 lowercase letters, digits, dots, underscores, or hyphens."
        )
    return normalized


def normalize_display_name(value: str) -> str:
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise IdentityValidationError("Display name contains unsupported control characters.")
    normalized = " ".join(value.strip().split())
    if not 1 <= len(normalized) <= 120:
        raise IdentityValidationError("Display name must contain 1-120 characters.")
    return normalized


def validate_password(password: str) -> None:
    if not MIN_PASSWORD_CHARACTERS <= len(password) <= MAX_PASSWORD_CHARACTERS:
        raise PasswordPolicyError(
            f"Password must contain {MIN_PASSWORD_CHARACTERS}-{MAX_PASSWORD_CHARACTERS} characters."
        )
    try:
        encoded = password.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise PasswordPolicyError("Password contains unsupported Unicode data.") from exc
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise PasswordPolicyError("Password exceeds the encoded byte limit.")
    if any(unicodedata.category(character) == "Cc" for character in password):
        raise PasswordPolicyError("Password contains unsupported control characters.")


def hash_password(password: str) -> str:
    validate_password(password)
    salt = secrets.token_bytes(SCRYPT_SALT_BYTES)
    derived = _derive(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_DKLEN)
    return "$".join(
        (
            PASSWORD_SCHEME,
            str(PASSWORD_SCHEME_VERSION),
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            str(SCRYPT_DKLEN),
            _encode(salt),
            _encode(derived),
        )
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        scheme, version, n, r, p, dklen, encoded_salt, encoded_expected = encoded_hash.split("$")
        if scheme != PASSWORD_SCHEME or int(version) != PASSWORD_SCHEME_VERSION:
            return False
        parameters = (int(n), int(r), int(p), int(dklen))
        if parameters != (SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_DKLEN):
            return False
        salt = _decode(encoded_salt)
        expected = _decode(encoded_expected)
        if len(salt) != SCRYPT_SALT_BYTES or len(expected) != SCRYPT_DKLEN:
            return False
        candidate = _derive(password, salt, *parameters)
    except (UnicodeError, ValueError, binascii.Error):
        return False
    return hmac.compare_digest(candidate, expected)


def verify_password_or_dummy(password: str, encoded_hash: str | None) -> bool:
    if encoded_hash is not None and _supported_hash_shape(encoded_hash):
        return verify_password(password, encoded_hash)
    verify_password(password, _dummy_hash())
    return False


def new_opaque_token() -> str:
    token = secrets.token_urlsafe(OPAQUE_TOKEN_BYTES)
    if OPAQUE_TOKEN_PATTERN.fullmatch(token) is None:  # pragma: no cover - invariant guard
        raise RuntimeError("The generated authentication token has an unexpected shape.")
    return token


def keyed_token_digest(secret: str, token: str) -> str:
    if len(secret.encode("utf-8")) < 32:
        raise ValueError("The authentication session secret is too short.")
    return hmac.new(secret.encode("utf-8"), token.encode("ascii"), hashlib.sha256).hexdigest()


def safe_token_shape(token: str | None) -> bool:
    return token is not None and OPAQUE_TOKEN_PATTERN.fullmatch(token) is not None


def _derive(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        maxmem=SCRYPT_MAXMEM,
        dklen=dklen,
    )


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    if not value or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise ValueError("Invalid base64url value.")
    padded = value + "=" * (-len(value) % 4)
    return base64.b64decode(padded, altchars=b"-_", validate=True)


def _supported_hash_shape(encoded_hash: str) -> bool:
    parts = encoded_hash.split("$")
    if len(parts) != 8:
        return False
    return parts[:6] == [
        PASSWORD_SCHEME,
        str(PASSWORD_SCHEME_VERSION),
        str(SCRYPT_N),
        str(SCRYPT_R),
        str(SCRYPT_P),
        str(SCRYPT_DKLEN),
    ]


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return hash_password(secrets.token_urlsafe(32))
