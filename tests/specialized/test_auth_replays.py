from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import hashlib

import pytest
from sqlalchemy import event, text
import test_auth_contracts as original


@pytest.mark.parametrize(
    "roles", [("candidate", "candidate"), ("candidate", "employer")]
)
def test_duplicate_registration_new_database_with_driver_evidence(
    client, engine, evidence, roles
):
    gate = Barrier(2)
    errors = []

    def sync(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith('INSERT INTO "user"'):
            gate.wait(timeout=8)

    def capture(context):
        err = context.original_exception
        errors.append(
            {
                "type": type(err).__name__,
                "constraint": getattr(
                    getattr(err, "diag", None), "constraint_name", None
                ),
                "sqlstate": getattr(err, "sqlstate", None),
            }
        )

    event.listen(engine, "before_cursor_execute", sync)
    event.listen(engine, "handle_error", capture)
    try:

        def request(role):
            return client.post(
                "/users/register",
                json={
                    "email": "registration-replay@example.com",
                    "password": "synthetic-only",
                    "role": role,
                },
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(request, roles))
    finally:
        event.remove(engine, "before_cursor_execute", sync)
        event.remove(engine, "handle_error", capture)
    with engine.connect() as c:
        user_count = c.execute(text('SELECT count(*) FROM "user"')).scalar_one()
        session_count = c.execute(
            text("SELECT count(*) FROM user_session")
        ).scalar_one()
    codes = sorted(r.status_code for r in responses)
    evidence(
        "driver-evidence",
        {
            "codes": codes,
            "driver_errors": errors,
            "user_count": user_count,
            "session_count": session_count,
            "synchronization": "both INSERT attempts after separate successful absence checks",
        },
    )
    assert user_count == session_count == 1
    assert codes in ([200, 400], [200, 409]), codes


def test_different_email_concurrent_registration_control(client, engine):
    gate = Barrier(2)

    def sync(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith('INSERT INTO "user"'):
            gate.wait(timeout=8)

    event.listen(engine, "before_cursor_execute", sync)
    try:

        def register(i):
            return client.post(
                "/users/register",
                json={
                    "email": f"separate-{i}@example.com",
                    "password": "synthetic-only",
                    "role": "candidate",
                },
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(register, range(2)))
    finally:
        event.remove(engine, "before_cursor_execute", sync)
    assert [r.status_code for r in responses] == [200, 200]
    with engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM "user"')).scalar_one() == 2


def test_sequential_same_email_different_role_control(client, engine):
    credentials, _, _ = original.signup(client)
    response = client.post("/users/register", json=credentials | {"role": "employer"})
    assert response.status_code == 400
    with engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM "user"')).scalar_one() == 1


def test_secure_cookie_configuration_contract(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "COOKIE_SECURE", True)
    _, response, _ = original.signup(client)
    assert all("Secure" in x for x in response.headers.get_list("set-cookie"))


def test_revoking_all_sessions_preserves_account_and_profile(client, engine):
    from sqlmodel import Session
    from app.users.service import revoke_all_sessions
    import uuid

    credentials, first, headers = original.signup(client)
    second = client.post("/users/login", json=credentials)
    with Session(engine) as s:
        revoke_all_sessions(s, uuid.UUID(first.json()["user"]["id"]))
    assert client.get("/users/me", headers=headers).status_code == 401
    assert (
        client.get(
            "/users/me", headers={"Cookie": "session=" + second.cookies["session"]}
        ).status_code
        == 401
    )
    assert client.post("/users/login", json=credentials).status_code == 200


def test_deleting_incomplete_account_cascades_sessions(client, engine):
    _, response, headers = original.signup(client)
    with engine.begin() as c:
        c.execute(
            text('DELETE FROM "user" WHERE id=:id'),
            {"id": response.json()["user"]["id"]},
        )
    assert client.get("/users/me", headers=headers).status_code == 401
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM user_session")).scalar_one() == 0


def test_ordinary_unicode_password_round_trip(client):
    credentials = {"email": "unicode-password@example.com", "password": "密码 café 🌏"}
    assert (
        client.post(
            "/users/register", json=credentials | {"role": "candidate"}
        ).status_code
        == 200
    )
    assert client.post("/users/login", json=credentials).status_code == 200
