"""Single shared password gate. One password, one signed session cookie — no
accounts, no server-side session store, matching the rest of this app's
single-user design."""

import hashlib
import hmac
import secrets

from app.config import settings

COOKIE_NAME = "session"
_TOKEN_VALUE = "authenticated"


def _sign(value: str) -> str:
    return hmac.new(settings.session_secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def make_session_token() -> str:
    return f"{_TOKEN_VALUE}.{_sign(_TOKEN_VALUE)}"


def is_valid_session_token(token: str | None) -> bool:
    # Fail closed: an unset session_secret signs with a predictable empty key, which
    # would let anyone forge a valid cookie without ever knowing the password.
    if not settings.session_secret or not token or "." not in token:
        return False
    value, signature = token.rsplit(".", 1)
    if value != _TOKEN_VALUE:
        return False
    return hmac.compare_digest(signature, _sign(value))


def check_password(password: str) -> bool:
    # Fail closed: an unset auth_password would otherwise let an empty password through,
    # since compare_digest("", "") is True.
    if not settings.auth_password:
        return False
    return secrets.compare_digest(password, settings.auth_password)
