"""Users, password hashing (argon2) and signed-cookie sessions.

The session is a cookie holding the user id signed with ``SECRET_KEY`` (itsdangerous); the user is
reloaded from the database on every request, so deleting a user ends their sessions. HTML pages can
use the same :func:`current_user` dependency; it raises 401 when nobody is logged in.
"""

import logging
from typing import Annotated

import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel

from rfp.api.deps import Conn
from rfp.config import Settings
from rfp.services.errors import ConflictError, InvalidInputError

log = logging.getLogger(__name__)

SESSION_COOKIE = "rfp_session"
SESSION_MAX_AGE_S = 7 * 24 * 3600
MIN_PASSWORD_LENGTH = 8

_hasher = PasswordHasher()
# Verified against when the user does not exist, so that unknown and wrong users take the same time.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


class User(BaseModel):
    id: int
    username: str
    is_admin: bool = False


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_user(conn: psycopg.Connection, username: str, password: str, is_admin: bool = False) -> User:
    username = username.strip()
    if not username:
        raise InvalidInputError("Username must not be empty.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise InvalidInputError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    row = conn.execute(
        """
        INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, %s)
        ON CONFLICT (username) DO NOTHING RETURNING id
        """,
        (username, hash_password(password), is_admin),
    ).fetchone()
    if row is None:
        raise ConflictError(f"User '{username}' already exists.")
    return User(id=row[0], username=username, is_admin=is_admin)


def authenticate(conn: psycopg.Connection, username: str, password: str) -> User | None:
    row = conn.execute(
        "SELECT id, username, is_admin, password_hash FROM users WHERE username = %s", (username.strip(),)
    ).fetchone()
    if row is None:
        verify_password(_DUMMY_HASH, password)
        return None
    if not verify_password(row[3], password):
        return None
    return User(id=row[0], username=row[1], is_admin=row[2])


def get_user(conn: psycopg.Connection, user_id: int) -> User | None:
    row = conn.execute("SELECT id, username, is_admin FROM users WHERE id = %s", (user_id,)).fetchone()
    return User(id=row[0], username=row[1], is_admin=row[2]) if row else None


def bootstrap_admin(conn: psycopg.Connection, settings: Settings) -> bool:
    """Create the first administrator from ADMIN_USERNAME/ADMIN_PASSWORD when there are no users."""
    if not settings.admin_username or not settings.admin_password:
        return False
    if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return False
    try:
        create_user(conn, settings.admin_username, settings.admin_password.get_secret_value(), is_admin=True)
    except ConflictError:  # another process created it in the meantime
        return False
    log.info("Created the first administrator '%s'", settings.admin_username)
    return True


def _serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt="rfp-session")


def make_session_token(secret_key: str, user_id: int) -> str:
    return _serializer(secret_key).dumps({"uid": user_id})


def read_session_token(secret_key: str, token: str) -> int | None:
    try:
        payload = _serializer(secret_key).loads(token, max_age=SESSION_MAX_AGE_S)
    except BadSignature:
        return None
    uid = payload.get("uid") if isinstance(payload, dict) else None
    return uid if isinstance(uid, int) else None


def current_user(request: Request, conn: Conn) -> User:
    """The logged-in user, or 401."""
    token = request.cookies.get(SESSION_COOKIE)
    user_id = read_session_token(request.app.state.secret_key, token) if token else None
    user = get_user(conn, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


def require_admin(user: Annotated[User, Depends(current_user)]) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator rights required")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
