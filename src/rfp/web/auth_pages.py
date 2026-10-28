"""Login and logout pages."""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import Response

from rfp.api.deps import Conn, SettingsDep
from rfp.audit import log_action
from rfp.auth import (
    SESSION_COOKIE,
    SESSION_MAX_AGE_S,
    authenticate,
    current_user,
    make_session_token,
)
from rfp.web.common import WebUser, redirect, render, safe_next

router = APIRouter(include_in_schema=False)


@router.get("/")
def index() -> Response:
    return redirect("/jobs")


@router.get("/login")
def login_page(request: Request, conn: Conn, next: str | None = None) -> Response:
    try:
        current_user(request, conn)
    except HTTPException:
        return render(request, "login.html", next=safe_next(next), error=None, username="")
    return redirect(safe_next(next))


@router.post("/login")
def login(
    request: Request,
    conn: Conn,
    settings: SettingsDep,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str | None, Form()] = None,
) -> Response:
    user = authenticate(conn, username, password)
    if user is None:
        log_action(conn, None, "login.failed", "user", None, {"username": username[:100]})
        return render(
            request,
            "login.html",
            status_code=401,
            next=safe_next(next),
            error="Неверный логин или пароль.",
            username=username,
        )
    response = redirect(safe_next(next))
    response.set_cookie(
        SESSION_COOKIE,
        make_session_token(request.app.state.secret_key, user.id),
        max_age=SESSION_MAX_AGE_S,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    log_action(conn, user.username, "login", "user", user.id)
    return response


@router.post("/logout")
def logout(conn: Conn, user: WebUser) -> Response:
    response = redirect("/login")
    response.delete_cookie(SESSION_COOKIE)
    log_action(conn, user.username, "logout", "user", user.id)
    return response
