from datetime import timedelta

import pytest
from conftest import FROZEN

PATH = "/employer/interview-slots"


@pytest.mark.parametrize(
    "side,microseconds,expected",
    [("end", -1, 409), ("end", 1, 201), ("start", 1, 409), ("start", -1, 201)],
)
def test_microsecond_overlap_edges_use_exact_intervals(
    client, account, create_slot, snapshot, side, microseconds, expected
):
    owner = account()
    start = FROZEN + timedelta(days=1, hours=12)
    create_slot(owner, start)
    proposed = start + timedelta(
        minutes=30 if side == "end" else -30, microseconds=microseconds
    )
    before = snapshot()
    result = client.post(
        PATH, headers=owner["headers"], json={"starts_at": proposed.isoformat()}
    )
    assert result.status_code == expected, result.text
    if expected == 409:
        assert snapshot() == before
    else:
        assert len(snapshot()["interview_slot"]) == 2


@pytest.mark.parametrize(
    "legacy_minutes,offset,expected", [(60, 15, 409), (15, -5, 409), (60, 60, 201)]
)
def test_existing_legacy_intervals_still_participate_in_overlap_rules(
    client, account, insert_slot, snapshot, legacy_minutes, offset, expected
):
    owner = account()
    start = FROZEN + timedelta(days=1, hours=12)
    insert_slot(owner, start, minutes=legacy_minutes)
    proposed = start + timedelta(minutes=offset)
    independently_overlaps = (
        start < proposed + timedelta(minutes=30)
        and start + timedelta(minutes=legacy_minutes) > proposed
    )
    assert independently_overlaps == (expected == 409)
    before = snapshot()
    result = client.post(
        PATH, headers=owner["headers"], json={"starts_at": proposed.isoformat()}
    )
    assert result.status_code == expected, result.text
    if expected == 409:
        assert snapshot() == before
    else:
        assert len(snapshot()["interview_slot"]) == 2
