"""雇主面试时段的规则和数据库事务。"""

from datetime import timedelta
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from app.employer.model import Application, Booking, InterviewSlot, Job
from app.interview.schema import ManagedSlotPublic, SlotCreate, SlotPublic
from app.users.model import CandidateProfile, EmployerProfile, User, utc_now

SLOT_LENGTH = timedelta(minutes=30)


class InvalidSlotError(ValueError):
    """创建时段的开始时间或时长不合法。"""


class NotFoundError(ValueError):
    """时段或创建所需的雇主资料不存在。"""


class ForbiddenError(ValueError):
    """时段属于另一位雇主。"""


class ConflictError(ValueError):
    """时段重叠、已经开始或已有预约。"""


def create_slot(session: Session, employer: User, payload: SlotCreate) -> SlotPublic:
    """为当前雇主创建一个未来且不重叠的 30 分钟时段。"""
    starts_at = payload.starts_at
    try:
        # 同一雇主的并发创建必须先获取同一把锁，再检查已有时段。
        if session.get(EmployerProfile, employer.id, with_for_update=True) is None:
            raise NotFoundError("Employer profile not found")
        if starts_at <= utc_now():
            raise InvalidSlotError("Slot must start in the future")
        try:
            ends_at = starts_at + SLOT_LENGTH
        except OverflowError as error:
            raise InvalidSlotError("Slot end time is out of range") from error

        overlapping_slot = session.exec(
            select(InterviewSlot.id)
            .where(
                InterviewSlot.employer_id == employer.id,
                InterviewSlot.starts_at < ends_at,
                InterviewSlot.ends_at > starts_at,
            )
            .limit(1)
        ).first()
        if overlapping_slot is not None:
            raise ConflictError("Slot overlaps an existing slot")

        slot = InterviewSlot(
            employer_id=employer.id,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        response = SlotPublic.model_validate(slot)
        session.add(slot)
        session.commit()
    except (ValueError, SQLAlchemyError):
        session.rollback()
        raise
    return response


def list_slots(session: Session, employer: User) -> list[ManagedSlotPublic]:
    """返回当前雇主尚未开始的时段、预约状态及申请人信息。"""
    statement = (
        select(
            InterviewSlot,
            Booking.id,
            Application.job_id,
            Job.title,
            CandidateProfile.display_name,
        )
        .outerjoin(Booking, Booking.slot_id == InterviewSlot.id)
        .outerjoin(Application, Application.id == Booking.application_id)
        .outerjoin(Job, Job.id == Application.job_id)
        .outerjoin(
            CandidateProfile, CandidateProfile.user_id == Application.candidate_id
        )
        .where(
            InterviewSlot.employer_id == employer.id,
            InterviewSlot.starts_at > utc_now(),
        )
        .order_by(col(InterviewSlot.starts_at), col(InterviewSlot.id))
    )
    return [
        ManagedSlotPublic(
            id=slot.id,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
            is_booked=booking_id is not None,
            # 新预约会写入 slot.job_id；历史数据为空时回退到申请上的职位。
            job_id=slot.job_id or application_job_id,
            job_title=job_title,
            applicant_name=applicant_name,
        )
        for (
            slot,
            booking_id,
            application_job_id,
            job_title,
            applicant_name,
        ) in session.exec(statement)
    ]


def delete_slot(session: Session, employer: User, slot_id: UUID) -> None:
    """锁定时段后重查归属、预约和开始时间，再决定是否删除。"""
    try:
        slot = session.exec(
            select(InterviewSlot).where(InterviewSlot.id == slot_id).with_for_update()
        ).one_or_none()
        if slot is None:
            raise NotFoundError("Slot not found")
        if slot.employer_id != employer.id:
            raise ForbiddenError("Slot belongs to another employer")

        # 与候选人预约锁同一行，预约查询须在获得时段锁之后执行。
        booking = session.exec(
            select(Booking.id).where(Booking.slot_id == slot.id)
        ).first()
        if booking is not None:
            raise ConflictError("Slot already booked")
        if slot.starts_at <= utc_now():
            raise ConflictError("Slot is in the past")

        session.delete(slot)
        session.commit()
    except (ValueError, SQLAlchemyError):
        session.rollback()
        raise
