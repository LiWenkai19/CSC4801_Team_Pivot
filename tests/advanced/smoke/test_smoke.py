"""P0 smoke checks: the disposable database and a real HTTP session work.

These are intentionally the only tests in the advanced skeleton.  They prove
that the shared fixtures connect through the real migration chain and the real
FastAPI application; later modes add the actual advanced techniques.
"""

from sqlalchemy import text


def test_database_has_user_table(engine):
    """The session database is reachable and the migration created ``user``."""

    with engine.connect() as connection:
        present = connection.execute(
            text("""SELECT to_regclass('public."user"')""")
        ).scalar()
    assert present is not None, "alembic upgrade head did not create the user table"


def test_account_can_read_own_profile(client, account, clean_tables, evidence):
    """A candidate registered through the API can authenticate with its headers."""

    headers, user_id = account(
        "candidate", skills=["Python", " SQL "], name="Smoke Candidate"
    )
    response = client.get("/users/me", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(user_id)
    assert body["role"] == "candidate"
    assert body["profile_completed"] is True
    evidence(
        "smoke-account",
        {
            "user_id": str(user_id),
            "status_code": response.status_code,
            "role": body["role"],
            "profile_completed": body["profile_completed"],
        },
    )
