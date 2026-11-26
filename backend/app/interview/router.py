"""雇主面试时段接口。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from app.users.schema import error_responses

from app.db.session import get_db
from app.interview import service
from app.interview.schema import ManagedSlotPublic, SlotCreate, SlotPublic
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


# A business-rule failure returns {"detail": "<message>"}, while a request-body
# validation failure returns FastAPI's default HTTPValidationError array. Both
# are 422, so the OpenAPI response has to document both shapes.
SLOT_CREATE_422 = {
    "description": (
        "Request validation failed (detail is an error array) or the slot "
        "violated a business rule (detail is a message string)."
    ),
    "content": {
        "application/json": {
            "schema": {
                "anyOf": [
                    {"$ref": "#/components/schemas/HTTPValidationError"},
                    {
                        "type": "object",
                        "required": ["detail"],
                        "properties": {
                            "detail": {
                                "type": "string",
                                "description": "Business rule message, for example "
                                "'Slot must start in the future'.",
                            }
                        },
                    },
                ]
            }
        }
    },
}


@interview_router.post(
    "",
    response_model=SlotPublic,
    status_code=status.HTTP_201_CREATED,
    responses={**error_responses(401, 403, 404, 409), **{422: SLOT_CREATE_422}},
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


@interview_router.get("", response_model=list[ManagedSlotPublic], responses=error_responses(401, 403))
def list_slots(
    session: Session = Depends(get_db),
    employer: User = Depends(require_employer),
) -> list[ManagedSlotPublic]:
    """查询当前雇主尚未开始的时段及预约状态。"""
    return service.list_slots(session, employer)


@interview_router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(401, 403, 404, 409))
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
