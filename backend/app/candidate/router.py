import uuid

from fastapi import APIRouter, Body, Depends, HTTPException

from sqlmodel import Session, select

from app.candidate import service

from app.candidate.model import Application

from app.candidate.schema import (
    ApplicationPublic,
    BookingCreate,
    BookingPublic,
    EmptyRequest,
    JobPublic,
    SlotPublic,
)

from app.db.session import get_db

from app.users.model import User

from app.candidate.profile_schema import CandidateProfilePublic, CandidateProfileUpdate

from app.users.service import get_current_user, require_candidate, require_employer

router = APIRouter(tags=["candidate"])


@router.get("/employer/jobs/{job_id}/applications")
def employer_applicants(
    job_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(require_employer),
):
    return execute(service.employer_applicants, session, user, job_id)


def execute(action, *args):
    try:
        return action(*args)
    except service.FlowError as error:
        raise HTTPException(error.status, str(error)) from error


@router.get(
    "/users/candidates/{candidate_id}/profile",
    response_model=CandidateProfilePublic,
)
def read_profile(
    candidate_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 明确挑选资料字段，不把完整账户或 ORM 对象直接暴露给浏览器
    return service.profile_public(
        execute(service.readable_profile, session, user, candidate_id)
    )


@router.patch(
    "/users/candidates/{candidate_id}/profile",
    response_model=CandidateProfilePublic,
)
def patch_profile(
    candidate_id: uuid.UUID,
    payload: CandidateProfileUpdate,
    session: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    return execute(service.update_profile, session, user, candidate_id, payload)


@router.get("/candidate/jobs", response_model=list[JobPublic])
def jobs(session: Session = Depends(get_db), user: User = Depends(require_candidate)):
    return execute(service.list_jobs, session, user)


@router.get("/candidate/jobs/{job_id}", response_model=JobPublic)
def job_detail(
    job_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    profile = execute(service.owned_profile, session, user, user.id)
    return service.job_public(
        session,
        execute(service.active_job, session, job_id),
        profile,
    )


@router.post(
    "/candidate/jobs/{job_id}/applications",
    # 限定返回 JSON 字段与类型，避免意外泄露未声明内容
    response_model=ApplicationPublic,
    # 设置成功响应状态码；201 表示已创建新记录
    status_code=201,
)
def apply(
    job_id: uuid.UUID,
    payload: EmptyRequest = Body(default=EmptyRequest()),
    session: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    return execute(service.apply, session, user, job_id)


@router.get("/candidate/applications", response_model=list[ApplicationPublic])
def applications(
    session: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    rows = session.exec(
        select(Application)
        # 为查询添加筛选条件；不是把字符串拼接为 SQL
        .where(Application.candidate_id == user.id)
        # 指定数据库结果的排序依据
        .order_by(Application.id)
    )
    return [service.application_public(session, a) for a in rows]


@router.get(
    "/candidate/applications/{application_id}",
    response_model=ApplicationPublic,
)
def application_detail(
    application_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    return service.application_public(
        session,
        execute(service.owned_application, session, user, application_id),
    )


@router.get(
    "/candidate/applications/{application_id}/slots",
    response_model=list[SlotPublic],
)
def slots(
    application_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    return execute(service.available_slots, session, user, application_id)


@router.post(
    "/candidate/applications/{application_id}/booking",
    # 限定返回 JSON 字段与类型，避免意外泄露未声明内容
    response_model=BookingPublic,
    # 设置成功响应状态码；201 表示已创建新记录
    status_code=201,
)
def booking(
    application_id: uuid.UUID,
    payload: BookingCreate,
    session: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    return execute(service.book, session, user, application_id, payload.slot_id)
