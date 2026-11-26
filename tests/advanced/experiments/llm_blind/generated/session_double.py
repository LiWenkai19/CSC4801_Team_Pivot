"""Flexible SQLModel ``Session`` double for the blind-generated F2 tests.

Written by the experiment owner as harness, not as an oracle: it contains no
booking expectations. It never opens a database connection.

It answers both lookup styles a service may use::

    session.get(Application, application_id, with_for_update=True)
    session.exec(select(Application).where(...)).first()

The generated test supplies the domain objects; ``Application``, ``InterviewSlot``
and ``Job`` are matched by the ``FROM <table>`` clause, and ``Booking`` queries are
answered from the optional existing-booking arguments. Any unrecognised query
returns an empty result, so a missing query branch surfaces as a clean assertion
failure rather than as a random truthy ``MagicMock``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid

from sqlmodel import Session

from app.employer.model import Application, Booking, InterviewSlot, Job


def _empty_result():
    value = MagicMock()
    value.first.return_value = None
    value.one_or_none.return_value = None
    value.all.return_value = []
    value.scalars.return_value = value
    value.__iter__.return_value = iter(())
    return value


def _result(rows):
    rows = list(rows)
    value = MagicMock()
    value.first.return_value = rows[0] if rows else None
    value.one_or_none.return_value = rows[0] if rows else None
    value.all.return_value = rows
    value.scalars.return_value = value
    value.__iter__.return_value = iter(rows)
    return value


def _primary_key(obj):
    if obj is None:
        return None
    return getattr(obj, "id", getattr(obj, "user_id", None))


def make_session(
    application=None,
    slot=None,
    job=None,
    *,
    application_booking=None,
    slot_booking=None,
    bookings=(),
):
    """Return a ``MagicMock(spec=Session)`` wired to the supplied objects.

    ``application``, ``slot`` and ``job`` are real SQLModel rows (or ``None`` to
    simulate a missing row). ``application_booking`` / ``slot_booking`` simulate
    an already-persisted booking row for that application or slot. Added
    ``Booking`` objects receive an ``id`` and ``created_at`` so a returned
    ``BookingPublic`` can be validated.
    """

    session = MagicMock(spec=Session)
    entities = {Application: application, InterviewSlot: slot, Job: job}

    def get(model, ident, **kwargs):
        obj = entities.get(model)
        if obj is None:
            return None
        key = _primary_key(obj)
        if key is not None and ident != key:
            return None
        return obj

    session.get.side_effect = get

    def exec_(statement, *args, **kwargs):
        text = str(statement).lower()
        if "from booking" in text:
            rows = list(bookings)
            if "application_id" in text and application_booking is not None:
                rows = [application_booking]
            elif "slot_id" in text and slot_booking is not None:
                rows = [slot_booking]
            return _result(rows)
        for model in (Application, InterviewSlot, Job):
            table = getattr(model, "__tablename__", None)
            if table and f"from {table}" in text:
                obj = entities.get(model)
                return _result([obj] if obj is not None else [])
        return _empty_result()

    session.exec.side_effect = exec_

    def add(obj):
        if isinstance(obj, Booking):
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.now(timezone.utc)

    session.add.side_effect = add
    session.refresh.side_effect = lambda obj: None
    return session
