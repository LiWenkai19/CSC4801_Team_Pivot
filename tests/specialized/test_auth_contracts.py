"""Defensive contracts with synthetic identities, actual routes and isolated PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
import hashlib
import uuid

import pytest
from sqlalchemy import event, text


def signup(client, role="candidate", email=None):
    credentials = {
        "email": email or uuid.uuid4().hex + "@example.com",
        "password": "isolated-audit-password",
    }
    response = client.post("/users/register", json=credentials | {"role": role})
    assert response.status_code == 200, response.text
    headers = {
        "Cookie": "session=" + response.cookies["session"],
        "X-CSRF-Token": response.cookies["csrf_token"],
    }
    return credentials, response, headers


@pytest.mark.parametrize("role", ["candidate", "employer"])
@pytest.mark.parametrize("remember", [False, True])
def test_session_lifecycle_hashes_cookies_and_independent_logout(
    client, engine, role, remember
):
    from app.users.security import verify_password
    from app.core.config import settings

    credentials, registered, first = signup(client, role)
    logged = client.post("/users/login", json=credentials | {"remember_me": remember})
    assert logged.status_code == 200
    assert set(logged.json()) == {"user"}
    assert set(logged.json()["user"]) == {"id", "email", "role", "profile_completed"}
    assert not logged.json()["user"]["profile_completed"]
    cookies = logged.headers.get_list("set-cookie")
    sess = next(x for x in cookies if x.startswith("session="))
    csrf = next(x for x in cookies if x.startswith("csrf_token="))
    assert "HttpOnly" in sess and "HttpOnly" not in csrf
    assert "SameSite=lax" in sess and "Path=/" in sess
    assert ("Max-Age=" in sess) is remember
    if remember:
        assert f"Max-Age={settings.SESSION_REMEMBER_DAYS * 86400}" in sess
    token = logged.cookies["session"]
    assert token != registered.cookies["session"]
    with engine.connect() as c:
        user = c.execute(text('SELECT hashed_password FROM "user"')).scalar_one()
        assert user.startswith("$argon2") and user != credentials["password"]
        assert verify_password(credentials["password"], user)
        row = (
            c.execute(
                text(
                    "SELECT token_hash, csrf_token, expires_at, created_at FROM user_session WHERE token_hash=:h"
                ),
                {"h": hashlib.sha256(token.encode()).hexdigest()},
            )
            .mappings()
            .one()
        )
        assert (
            row["token_hash"] != token
            and row["csrf_token"] == logged.cookies["csrf_token"]
        )
        seconds = (row["expires_at"] - row["created_at"]).total_seconds()
        expected = (
            settings.SESSION_REMEMBER_DAYS * 86400
            if remember
            else settings.SESSION_TTL_MINUTES * 60
        )
        assert abs(seconds - expected) < 2
    headers = {
        "Cookie": "session=" + token,
        "X-CSRF-Token": logged.cookies["csrf_token"],
    }
    assert client.get("/users/me", headers=headers).json() == logged.json()["user"]
    gone = client.post("/users/logout", headers=headers)
    assert gone.status_code == 204 and gone.content == b""
    assert all("Max-Age=0" in x for x in gone.headers.get_list("set-cookie"))
    assert client.get("/users/me", headers=headers).status_code == 401
    assert client.get("/users/me", headers=first).status_code == 200


@pytest.mark.parametrize("offset,expected", [(-1, 200), (0, 401), (1, 401)])
def test_expiry_exact_boundary(client, engine, monkeypatch, offset, expected):
    from app.users import service

    _, registered, headers = signup(client)
    cutoff = datetime(2031, 6, 1, tzinfo=timezone.utc)
    with engine.begin() as c:
        c.execute(text("UPDATE user_session SET expires_at=:t"), {"t": cutoff})
    monkeypatch.setattr(
        service, "utc_now", lambda: cutoff + timedelta(microseconds=offset)
    )
    response = client.get("/users/me", headers=headers)
    assert response.status_code == expected
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM user_session")).scalar_one() == (
            1 if expected == 200 else 0
        )


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_profile_completion_recomputed_and_duplicate_identity_atomic(
    client, engine, role, snapshot
):
    credentials, registered, headers = signup(client, role)
    before = snapshot()
    duplicate = client.post("/users/register", json=credentials | {"role": role})
    assert duplicate.status_code == 400 and snapshot() == before
    payload = (
        {"display_name": "Normal candidate"}
        if role == "candidate"
        else {"company_name": "Normal employer"}
    )
    assert (
        client.post(f"/users/{role}/profile", headers=headers, json=payload).status_code
        == 201
    )
    assert client.get("/users/me", headers=headers).json()["profile_completed"] is True
    with engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM "user"')).scalar_one() == 1


@pytest.mark.parametrize(
    "path",
    [
        "/users/me",
        "/candidate/profile",
        "/candidate/jobs",
        "/candidate/applications",
        "/employer/company",
        "/employer/jobs",
        "/employer/interview-slots",
    ],
)
def test_missing_session_is_401_without_business_changes(client, path, snapshot):
    before = snapshot()
    assert client.get(path).status_code == 401
    assert snapshot() == before


@pytest.mark.parametrize(
    "role,path",
    [
        ("candidate", "/employer/company"),
        ("candidate", "/employer/jobs"),
        ("candidate", "/employer/interview-slots"),
        ("employer", "/candidate/profile"),
        ("employer", "/candidate/jobs"),
        ("employer", "/candidate/applications"),
    ],
)
def test_opposite_normal_role_is_403(client, account, snapshot, role, path):
    identity = account(role)
    before = snapshot()
    assert client.get(path, headers=identity["headers"]).status_code == 403
    assert snapshot() == before


@pytest.mark.parametrize(
    "role,method,path,body",
    [
        ("candidate", "PATCH", "/candidate/profile", {"display_name": "Changed"}),
        ("employer", "PATCH", "/employer/company", {"company_name": "Changed"}),
        (
            "employer",
            "POST",
            "/employer/jobs",
            {"title": "Job", "description": "Normal", "required_skills": []},
        ),
        (
            "employer",
            "POST",
            "/employer/interview-slots",
            {"starts_at": "2032-06-01T00:00:00Z"},
        ),
        ("candidate", "POST", "/users/logout", None),
    ],
)
def test_existing_csrf_guard_rejects_missing_header(
    client, account, snapshot, role, method, path, body
):
    identity = account(role)
    before = snapshot()
    response = client.request(
        method, path, headers={"Cookie": identity["headers"]["Cookie"]}, json=body
    )
    assert response.status_code == 403 and snapshot() == before


@pytest.mark.parametrize("case", ["wrong-password", "unknown-email"])
def test_invalid_login_has_no_session_side_effects(client, engine, snapshot, case):
    credentials, _, _ = signup(client)
    if case == "wrong-password":
        credentials["password"] = "another-normal-password"
    else:
        credentials["email"] = "not-registered@example.com"
    before = snapshot()
    with engine.connect() as c:
        n = c.execute(text("SELECT count(*) FROM user_session")).scalar_one()
    response = client.post("/users/login", json=credentials)
    assert response.status_code == 401 and not response.headers.get_list("set-cookie")
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM user_session")).scalar_one() == n
    assert snapshot() == before


@pytest.mark.parametrize(
    "role,path",
    [
        ("candidate", "/candidate/jobs/"),
        ("candidate", "/candidate/applications/"),
        ("employer", "/employer/jobs/"),
    ],
)
def test_authenticated_missing_object_is_404(client, account, role, path):
    actor = account(role)
    assert (
        client.get(path + str(uuid.uuid4()), headers=actor["headers"]).status_code
        == 404
    )


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_concurrent_same_email_registration_returns_business_rejection(
    client, engine, evidence, role
):
    gate = Barrier(2)

    def synchronize(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith('INSERT INTO "user"'):
            gate.wait(timeout=8)

    event.listen(engine, "before_cursor_execute", synchronize)
    try:
        payload = {
            "email": "same-registration@example.com",
            "password": "normal-password",
            "role": role,
        }
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(
                pool.map(
                    lambda _: client.post("/users/register", json=payload), range(2)
                )
            )
    finally:
        event.remove(engine, "before_cursor_execute", synchronize)
    with engine.connect() as c:
        users = c.execute(text('SELECT count(*) FROM "user"')).scalar_one()
        sessions = c.execute(text("SELECT count(*) FROM user_session")).scalar_one()
    codes = sorted(x.status_code for x in responses)
    evidence(
        "registration-result",
        {
            "role": role,
            "status_codes": codes,
            "user_count": users,
            "session_count": sessions,
            "synchronization": "both requests reached INSERT after duplicate-email check",
            "bodies": [
                x.json() if x.status_code != 500 else "Internal Server Error"
                for x in responses
            ],
        },
    )
    assert users == 1 and sessions == 1
    assert codes in ([200, 400], [200, 409]), codes
