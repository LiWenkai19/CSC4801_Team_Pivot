"""共享模型建立数据库及关键约束的隔离测试。"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.candidate.model import Booking, Company, InterviewSlot


def test_company_name_cannot_be_blank(flow):
    with Session(flow["engine"]) as session:
        session.add(Company(name="   "))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_slot_requires_thirty_minutes(flow):
    start = datetime(2030, 1, 1, tzinfo=timezone.utc)
    with Session(flow["engine"]) as session:
        session.add(InterviewSlot(employer_id=flow["ids"][2], starts_at=start,
                                  ends_at=start + timedelta(minutes=20)))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_booking_requires_existing_references(flow):
    with Session(flow["engine"]) as session:
        session.add(Booking(application_id=uuid4(), slot_id=uuid4()))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_slot_duration_constraint_compiles_for_both_databases():
    from sqlalchemy.dialects import postgresql, sqlite
    from sqlalchemy.schema import CreateTable

    postgres = str(CreateTable(InterviewSlot.__table__).compile(dialect=postgresql.dialect()))
    local = str(CreateTable(InterviewSlot.__table__).compile(dialect=sqlite.dialect()))
    assert "INTERVAL '30 minutes'" in postgres and "julianday" not in postgres
    assert "julianday" in local and "INTERVAL" not in local
