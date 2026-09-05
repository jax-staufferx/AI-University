"""Accounts are login credentials only — every account sees the same shared topics/data.
This app is still fundamentally single-dataset; accounts exist so more than one person can
have their own username/password rather than one shared password for everyone.

Sessions are a signed cookie (HMAC, no server-side session store) encoding the username."""

import hashlib
import hmac
import secrets

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Account

COOKIE_NAME = "session"

_PBKDF2_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    salt, _, digest_hex = stored_hash.partition("$")
    if not salt or not digest_hex:
        return False
    expected = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS)
    return hmac.compare_digest(expected.hex(), digest_hex)


def _sign(value: str) -> str:
    return hmac.new(settings.session_secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def make_session_token(username: str) -> str:
    return f"{username}.{_sign(username)}"


def verify_session_token(token: str | None) -> str | None:
    """Returns the logged-in username if the cookie is valid, else None.

    Fails closed: an unset session_secret signs with a predictable empty key, which would
    let anyone forge a valid cookie without ever knowing a password.
    """
    if not settings.session_secret or not token or "." not in token:
        return None
    username, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(username)):
        return None
    return username


def get_account_by_username(db: Session, username: str) -> Account | None:
    return db.query(Account).filter(Account.username.ilike(username)).first()


def create_account(db: Session, username: str, password: str) -> Account:
    account = Account(username=username, password_hash=hash_password(password))
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def authenticate(db: Session, username: str, password: str) -> Account | None:
    account = get_account_by_username(db, username)
    if account is None or not verify_password(password, account.password_hash):
        return None
    return account
