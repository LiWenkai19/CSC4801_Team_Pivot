"""Shared fixtures for ``tests/advanced/``.

The application reads configuration at import time, so this file fixes the
process environment *before* any ``app`` import (including imports inside
fixtures): a harmless database URL, the test application name, and non-secure
cookies for the in-process HTTP client.

Database fixtures connect lazily.  A mode that only needs pure Python (for
example a Z3 formal mode) must still collect and run without PostgreSQL: only
tests that request ``engine``, ``client``, ``account``, ``db`` or
``clean_tables`` need a server.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
ADVANCED = Path(__file__).resolve().parent

for entry in (str(BACKEND), str(ADVANCED)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

# Must be set before `app.core.config` is imported for the first time.
os.environ["APP_NAME"] = "Advanced test suite"
os.environ["COOKIE_SECURE"] = "false"
# Placeholder only: get_db is overridden, but importing app.db.session must not
# point at a developer database either.
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://unused@127.0.0.1:1/advanced_not_a_database"
)


@pytest.fixture(scope="session")
def engine():
    """Create one throwaway database per session, migrate it, then drop it.

    The server comes from ``ADVANCED_PG_URL`` (started by ``run.py`` or supplied
    by CI).  A missing URL fails only when a test actually asks for this
    fixture, so database-free modes keep working without PostgreSQL.
    """

    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from sqlmodel import create_engine

    from support.pg import validate_loopback_url

    source_url = os.environ.get("ADVANCED_PG_URL")
    if not source_url:
        pytest.fail(
            "ADVANCED_PG_URL is not set; run this mode through "
            "python tests/advanced/run.py",
            pytrace=False,
        )
    try:
        validate_loopback_url(source_url)
    except ValueError as exc:
        pytest.fail(str(exc), pytrace=False)

    from alembic import command
    from alembic.config import Config

    source = make_url(source_url)
    name = f"advanced_{uuid.uuid4().hex[:12]}"
    admin = create_engine(
        source.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    database_engine = create_engine(
        source.set(database=name), pool_size=8, max_overflow=4
    )
    previous: str | None = None
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))

        from app.core.config import settings

        previous = settings.DATABASE_URL
        settings.DATABASE_URL = source.set(database=name).render_as_string(
            hide_password=False
        )
        command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
        yield database_engine
    finally:
        if previous is not None:
            from app.core.config import settings

            settings.DATABASE_URL = previous
        database_engine.dispose()
        try:
            with admin.connect() as connection:
                connection.execute(
                    text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
                )
        finally:
            admin.dispose()


@pytest.fixture
def clean_tables(engine):
    """TRUNCATE every application table; opt in explicitly.

    This fixture is deliberately **not** autouse: most tests should build only
    the rows they need, and pure-Python modes must not require a database.  The
    returned callable can also be used mid-test to reset state.
    """

    from sqlalchemy import text
    from sqlmodel import SQLModel

    # Importing the models registers every table in SQLModel.metadata.
    from app.employer import model as _employer_model  # noqa: F401
    from app.users import model as _users_model  # noqa: F401

    names = ", ".join(
        f'"{table.name}"' for table in SQLModel.metadata.sorted_tables
    )
    if not names:  # pragma: no cover - models are always registered above
        raise RuntimeError("SQLModel.metadata contains no tables")

    def truncate() -> None:
        with engine.begin() as connection:
            connection.execute(
                text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE")
            )

    truncate()
    return truncate


@pytest.fixture
def db(engine):
    """A plain SQLModel session for direct persistence assertions."""

    from sqlmodel import Session

    with Session(engine) as session:
        yield session


@pytest.fixture
def client(engine):
    """Real FastAPI application with only ``get_db`` redirected to the test DB.

    The cookie jar is cleared after every response so a test that creates two
    accounts can authenticate each request solely through the explicit
    ``Cookie`` header (see the ``account`` fixture).
    """

    from fastapi.testclient import TestClient
    from sqlmodel import Session

    from app.db.session import get_db
    from app.main import app

    def test_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as test_client:
            test_client.event_hooks["response"].append(
                lambda response: test_client.cookies.clear()
            )
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def account(client):
    """Register a real account and complete its profile.

    Returns ``(headers, user_id)`` where *headers* contains the session Cookie
    and the CSRF token, for example::

        headers, candidate_id = account("candidate", skills=["python"])
        client.get("/users/me", headers=headers)

    Registration and profile completion go through the real HTTP API, so the
    fixture exercises the same paths as a browser.  Passwords and session
    tokens never appear in assertion messages printed by this fixture.
    """

    def create(role="candidate", skills=None, name=None):
        if role not in {"candidate", "employer"}:
            raise ValueError("role must be 'candidate' or 'employer'")
        response = client.post(
            "/users/register",
            json={
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "advanced-local-only",
                "role": role,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        headers = {
            "Cookie": "session=" + response.cookies["session"],
            "X-CSRF-Token": response.cookies["csrf_token"],
        }
        payload = (
            {
                "display_name": name or "Advanced Candidate",
                "skills": list(skills or []),
            }
            if role == "candidate"
            else {"company_name": name or "Advanced Company"}
        )
        saved = client.post(
            f"/users/{role}/profile", headers=headers, json=payload
        )
        assert saved.status_code == 201, saved.text
        return headers, uuid.UUID(body["user"]["id"])

    return create


@pytest.fixture
def evidence():
    """Write JSON evidence to ``$ADVANCED_OUT/<mode>/<name>.json``.

    ``run.py`` sets ``ADVANCED_OUT`` and ``ADVANCED_MODE``.  A direct pytest
    invocation without those variables falls back to a directory under the
    system temporary directory; artefacts never go inside the checkout.
    """

    def save(name, data):
        base = os.environ.get("ADVANCED_OUT")
        mode = os.environ.get("ADVANCED_MODE", "adhoc")
        if base:
            folder = Path(base) / mode
        else:
            folder = (
                Path(tempfile.gettempdir())
                / "csc4801-advanced-evidence"
                / mode
            )
        folder.mkdir(parents=True, exist_ok=True)
        safe = "".join(
            character if character.isalnum() or character in "-_." else "_"
            for character in str(name)
        ) or "evidence"
        (folder / f"{safe}.json").write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )

    return save


@pytest.fixture
def utc_future():
    """Return ``(days=1, minutes=0) -> aware UTC datetime``.

    Slot and booking tests need a timestamp that is strictly in the future for
    the application's real clock; the offset is applied to "now" at call time.
    """

    def when(days=1, minutes=0):
        return datetime.now(timezone.utc) + timedelta(
            days=days, minutes=minutes
        )

    return when
