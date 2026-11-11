"""候选人 HTTP 接口；只负责校验、依赖注入与业务异常转换。"""

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlmodel import Session

from app.candidate import service
from app.candidate.schema import (
    ApplicationPublic,
    BookingCreate,
    BookingPublic,
    ProfileUpdate,
    RecommendedJob,
    RequestSchema,
    SlotPublic,
)
from app.db.session import get_db
from app.users.model import User
from app.users.schema import CandidateProfilePublic
from app.users.service import (
    CandidateRoleRequiredError,
    get_current_user,
    require_candidate,
)

candidate_router = APIRouter(prefix="/candidate", tags=["candidate"])

ERROR_STATUS = {
    CandidateRoleRequiredError: status.HTTP_403_FORBIDDEN,
    service.ForbiddenError: status.HTTP_403_FORBIDDEN,
    service.NotFoundError: status.HTTP_404_NOT_FOUND,
    service.ConflictError: status.HTTP_409_CONFLICT,
}
BUSINESS_ERRORS = tuple(ERROR_STATUS)


def execute(action, *args):
    """按异常继承链转换已声明的业务错误，不吞掉意外异常。"""
    try:
        return action(*args)
    except BUSINESS_ERRORS as error:
        for error_type in type(error).__mro__:
            if error_type in ERROR_STATUS:
                raise HTTPException(ERROR_STATUS[error_type], str(error)) from error
        raise


@candidate_router.get("/profile", response_model=CandidateProfilePublic)
def get_profile(
    session: Session = Depends(get_db), user: User = Depends(require_candidate)
):
    """读取本人资料。"""
    return execute(service.get_my_profile, session, user)


@candidate_router.patch("/profile", response_model=CandidateProfilePublic)
def update_profile(
    payload: ProfileUpdate,
    session: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    """局部更新本人资料。"""
    return execute(service.update_my_profile, session, user, payload)


@candidate_router.get("/profiles/{candidate_id}", response_model=CandidateProfilePublic)
def read_profile(
    candidate_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """本人或有投递关系的雇主读取资料。"""
    return execute(service.read_profile, session, user, candidate_id)


@candidate_router.get("/jobs", response_model=list[RecommendedJob])
def list_jobs(
    session: Session = Depends(get_db), user: User = Depends(require_candidate)
):
    """列出有效职位及匹配分数。"""
    return execute(service.list_jobs, session, user)


@candidate_router.get("/jobs/{job_id}", response_model=RecommendedJob)
def get_job(
    job_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    """读取有效职位详情。"""
    return execute(service.get_job, session, user, job_id)


@candidate_router.post(
    "/jobs/{job_id}/applications",
    response_model=ApplicationPublic,
    status_code=status.HTTP_201_CREATED,
)
def apply(
    job_id: uuid.UUID,
    payload: RequestSchema = Body(default=RequestSchema()),
    session: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    """投递一次；请求不能指定候选人或申请状态。"""
    return execute(service.apply, session, user, job_id)


@candidate_router.get("/applications", response_model=list[ApplicationPublic])
def list_applications(
    session: Session = Depends(get_db), user: User = Depends(require_candidate)
):
    """读取本人申请列表。"""
    return execute(service.list_applications, session, user)


@candidate_router.get(
    "/applications/{application_id}", response_model=ApplicationPublic
)
def get_application(
    application_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    """读取本人申请状态及预约。"""
    return execute(service.get_application, session, user, application_id)


@candidate_router.get(
    "/applications/{application_id}/slots", response_model=list[SlotPublic]
)
def available_slots(
    application_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    """读取本人面试申请可预约的时段。"""
    return execute(service.available_slots, session, user, application_id)


@candidate_router.post(
    "/applications/{application_id}/booking",
    response_model=BookingPublic,
    status_code=status.HTTP_201_CREATED,
)
def book(
    application_id: uuid.UUID,
    payload: BookingCreate,
    session: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    """原子预约，冲突返回 409。"""
    return execute(service.book, session, user, application_id, payload.slot_id)
