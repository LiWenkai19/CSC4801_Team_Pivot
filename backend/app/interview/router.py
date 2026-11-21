"""雇主面试时段接口。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.db.session import get_db
from app.interview import service
from app.interview.schema import SlotCreate, SlotPublic
from app.users.model import User
from app.users.service import require_employer

interview_router = APIRouter(prefix="/employer/interview-slots", tags=["interview"])

ERROR_STATUS: dict[type[ValueError], int] = {
    service.InvalidSlotError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    service.NotFoundError: status.HTTP_404_NOT_FOUND,
    service.ForbiddenError: status.HTTP_403_FORBIDDEN,
    service.ConflictError: status.HTTP_409_CONFLICT,
}
BUSINESS_ERRORS = tuple(ERROR_STATUS)


@interview_router.post(
    "", response_model=SlotPublic, status_code=status.HTTP_201_CREATED
)
def create_slot(
    payload: SlotCreate,
    session: Session = Depends(get_db),
    employer: User = Depends(require_employer),
) -> SlotPublic:
    """发布一个可供候选人预约的时段。"""
    try:
        return service.create_slot(session, employer, payload)
    except BUSINESS_ERRORS as error:
        raise HTTPException(ERROR_STATUS[type(error)], str(error)) from error


@interview_router.get("", response_model=list[SlotPublic])
def list_slots(
    session: Session = Depends(get_db),
    employer: User = Depends(require_employer),
) -> list[SlotPublic]:
    """查询当前雇主的可用时段。"""
    return service.list_slots(session, employer)


@interview_router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_slot(
    slot_id: UUID,
    session: Session = Depends(get_db),
    employer: User = Depends(require_employer),
) -> None:
    """删除当前雇主的一个未来空闲时段。"""
    try:
        service.delete_slot(session, employer, slot_id)
    except BUSINESS_ERRORS as error:
        raise HTTPException(ERROR_STATUS[type(error)], str(error)) from error
