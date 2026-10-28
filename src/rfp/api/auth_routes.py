"""Login, logout and the current user."""

from fastapi import APIRouter, HTTPException, Request, Response, status

from rfp.api.deps import Conn, SettingsDep
from rfp.api.schemas import LoginRequest
from rfp.audit import log_action
from rfp.auth import SESSION_COOKIE, SESSION_MAX_AGE_S, CurrentUser, User, authenticate, make_session_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", summary="Log in with a username and password")
def login(
    body: LoginRequest, request: Request, response: Response, conn: Conn, settings: SettingsDep
) -> User:
    """Sets the signed session cookie; the other endpoints require it."""
    user = authenticate(conn, body.username, body.password)
    if user is None:
        log_action(conn, None, "login.failed", "user", None, {"username": body.username[:100]})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")
    response.set_cookie(
        SESSION_COOKIE,
        make_session_token(request.app.state.secret_key, user.id),
        max_age=SESSION_MAX_AGE_S,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    log_action(conn, user.username, "login", "user", user.id)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="End the session")
def logout(response: Response, conn: Conn, user: CurrentUser) -> None:
    response.delete_cookie(SESSION_COOKIE)
    log_action(conn, user.username, "logout", "user", user.id)


@router.get("/me", summary="The logged-in user")
def me(user: CurrentUser) -> User:
    return user
