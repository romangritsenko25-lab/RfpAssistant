import pytest

from rfp.auth import create_user, hash_password, make_session_token, read_session_token, verify_password
from rfp.services.errors import ConflictError, InvalidInputError
from tests.conftest import ADMIN_PASSWORD, ADMIN_USER

pytestmark = pytest.mark.db


def test_password_hash_roundtrip():
    hashed = hash_password("correct horse")
    assert hashed.startswith("$argon2")
    assert verify_password(hashed, "correct horse")
    assert not verify_password(hashed, "wrong")
    assert not verify_password("garbage", "x")


def test_session_token_rejects_tampering_and_other_keys():
    token = make_session_token("key", 7)
    assert read_session_token("key", token) == 7
    assert read_session_token("other", token) is None
    assert read_session_token("key", token + "x") is None


def test_create_user_validates(db_conn):
    create_user(db_conn, "anna", "long-enough-pass")
    with pytest.raises(ConflictError):
        create_user(db_conn, "anna", "long-enough-pass")
    with pytest.raises(InvalidInputError):
        create_user(db_conn, "bob", "short")


def test_endpoints_require_login(client):
    for method, url in [
        ("get", "/api/jobs"),
        ("get", "/api/jobs/1"),
        ("get", "/api/documents"),
        ("get", "/api/logs/actions"),
        ("get", "/api/auth/me"),
        ("post", "/api/documents/reindex"),
    ]:
        assert getattr(client, method)(url).status_code == 401, url
    assert client.get("/health").status_code == 200


def test_login_me_logout(client):
    wrong = client.post("/api/auth/login", json={"username": ADMIN_USER, "password": "nope-nope"})
    assert wrong.status_code == 401
    ghost = client.post("/api/auth/login", json={"username": "ghost", "password": "nope-nope"})
    assert ghost.status_code == 401

    ok = client.post("/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["username"] == ADMIN_USER and ok.json()["is_admin"] is True
    assert "httponly" in ok.headers["set-cookie"].lower()
    assert client.get("/api/auth/me").json()["username"] == ADMIN_USER

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_forged_cookie_is_rejected(client):
    client.cookies.set("rfp_session", make_session_token("another-key", 1))
    assert client.get("/api/auth/me").status_code == 401


def test_non_admin_cannot_read_logs(client, db_conn):
    create_user(db_conn, "anna", "long-enough-pass")
    client.post("/api/auth/login", json={"username": "anna", "password": "long-enough-pass"})
    assert client.get("/api/jobs").status_code == 200
    assert client.get("/api/logs/actions").status_code == 403
