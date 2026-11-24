"""Focused replay and environment control for the initial date-boundary failure."""

from datetime import datetime
import traceback
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session

PATH = "/employer/interview-slots"


@pytest.mark.parametrize(
    "start",
    [
        "3000-12-31T15:30:00Z",
        "3000-12-31T23:30:00+08:00",
        "3001-01-01T00:00:00+08:00",
        "9999-12-31T15:30:00Z",
        "9999-12-31T23:59:59Z",
    ],
)
def test_create_rejects_future_times_outside_supported_range(
    client, account, snapshot, evidence, start
):
    """拒绝结束时间跨入 3001 年的时段，并确认没有写入。"""
    owner = account()
    before = snapshot()
    created = client.post(PATH, headers=owner["headers"], json={"starts_at": start})
    listed = client.get(PATH, headers=owner["headers"])
    after = snapshot()
    evidence(
        "minimal-replay",
        {
            "input": start,
            "create_status": created.status_code,
            "create": created.text,
            "list_status": listed.status_code,
            "list": listed.text,
            "state_unchanged": after == before,
        },
    )
    assert created.status_code == 422, created.text
    assert created.json()["detail"] == (
        "Interview slots must end before 3001 in Asia/Shanghai"
    )
    assert listed.status_code == 200 and listed.json() == []
    assert after == before


def test_legacy_driver_exception_and_utc_session_control(
    client, account, engine, insert_slot, evidence
):
    """用直插的遗留时段复现驱动边界，并确认 UTC 会话能读取同一行。"""
    from app.main import app
    from app.interview import service
    from app.users.model import User

    owner = account()
    slot_id = insert_slot(owner, datetime.fromisoformat("9999-12-31T15:30:00Z"))
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
            controlled = [
                slot.model_dump(mode="json", exclude_none=True) for slot in controlled
            ]
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
    assert controlled == [
        {
            "id": slot_id,
            "starts_at": "9999-12-31T15:30:00Z",
            "ends_at": "9999-12-31T16:00:00Z",
            "is_booked": False,
        }
    ]
