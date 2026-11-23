"""Focused replay and environment control for the initial date-boundary failure."""

from datetime import timedelta
import traceback
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session

PATH = "/employer/interview-slots"


@pytest.mark.parametrize(
    "start",
    ["9999-12-31T15:29:59.999999Z", "9999-12-31T15:30:00Z", "9999-12-31T16:00:00Z"],
)
def test_minimal_create_then_list_boundary_replay(
    client, account, snapshot, evidence, start
):
    owner = account()
    before = client.get(PATH, headers=owner["headers"])
    assert before.status_code == 200 and before.json() == []
    created = client.post(PATH, headers=owner["headers"], json={"starts_at": start})
    assert created.status_code == 201, created.text
    listed = client.get(PATH, headers=owner["headers"])
    evidence(
        "minimal-replay",
        {
            "input": start,
            "initial_list": before.status_code,
            "create_status": created.status_code,
            "create": created.json(),
            "list_status": listed.status_code,
            "list": listed.text,
            "state": snapshot(),
        },
    )
    assert listed.status_code == 200, (
        "Successfully accepted slot must remain readable: " + listed.text
    )


def test_driver_exception_and_utc_session_control(client, account, engine, evidence):
    from app.main import app
    from app.interview import service
    from app.users.model import User

    owner = account()
    created = client.post(
        PATH, headers=owner["headers"], json={"starts_at": "9999-12-31T15:30:00Z"}
    )
    assert created.status_code == 201
    with engine.connect() as connection:
        default_zone = connection.execute(text("SHOW TimeZone")).scalar_one()
        raw = (
            connection.execute(
                text("SELECT starts_at::text,ends_at::text FROM interview_slot")
            )
            .mappings()
            .all()
        )
        raw = [dict(row) for row in raw]
    try:
        with TestClient(app, raise_server_exceptions=True) as diagnostic:
            diagnostic.get(PATH, headers=owner["headers"])
    except Exception as error:
        caught = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        }
    else:
        caught = None
    with engine.connect() as connection:
        connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        with Session(bind=connection) as session:
            user = session.get(User, uuid.UUID(owner["id"]))
            controlled = service.list_slots(session, user)
            controlled = [slot.model_dump(mode="json") for slot in controlled]
    evidence(
        "root-cause",
        {
            "default_timezone": default_zone,
            "raw_database_text": raw,
            "exception": caught,
            "utc_session_control": controlled,
        },
    )
    assert default_zone == "Asia/Shanghai"
    assert caught is not None and "10000" in caught["message"], caught
    assert controlled == [{**created.json(), "is_booked": False}]
