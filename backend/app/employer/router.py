"""雇主 HTTP 路由；业务错误在这里转换为 HTTPException。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.db.session import get_db
from app.employer import service
from app.employer.schema import (
    ApplicationStatusPublic,
    ApplicationStatusUpdate,
    CompanyCreate,
    CompanyPublic,
    CompanyUpdate,
    JobCreate,
    JobPublic,
    JobUpdate,
)
from app.users.model import User
from app.users.service import EmployerRoleRequiredError, require_employer

employer_router = APIRouter(prefix="/employer", tags=["employer"])

ERROR_STATUS = {
    EmployerRoleRequiredError: status.HTTP_403_FORBIDDEN,
    service.EmployerProfileRequiredError: status.HTTP_409_CONFLICT,
    service.CompanyAlreadyLinkedError: status.HTTP_409_CONFLICT,
    service.CompanyNotFoundError: status.HTTP_404_NOT_FOUND,
    service.CompanyRequiredError: status.HTTP_409_CONFLICT,
    service.JobNotFoundError: status.HTTP_404_NOT_FOUND,
    service.JobForbiddenError: status.HTTP_403_FORBIDDEN,
    service.JobHasDependentsError: status.HTTP_409_CONFLICT,
    service.ApplicationNotFoundError: status.HTTP_404_NOT_FOUND,
}
BUSINESS_ERRORS = tuple(ERROR_STATUS)


def _to_http(error: ValueError) -> HTTPException:
    """把已知业务异常映射到固定状态码，detail 使用异常文本。"""
    return HTTPException(
        status_code=ERROR_STATUS[type(error)],
        detail=str(error),
    )


def execute(action, *args):
    """在路由层统一翻译业务异常。"""
    try:
        return action(*args)
    except BUSINESS_ERRORS as error:
        raise _to_http(error) from error


@employer_router.post(
    "/company", response_model=CompanyPublic, status_code=status.HTTP_201_CREATED
)
def create_company(
    payload: CompanyCreate,
    session: Session = Depends(get_db),
    user: User = Depends(require_employer),
):
    """创建公司并自动让当前雇主成为成员。"""
    return execute(service.create_company, session, user, payload)


@employer_router.get("/company", response_model=CompanyPublic)
def get_company(
    session: Session = Depends(get_db),
    user: User = Depends(require_employer),
):
    """读取当前雇主的公司资料。"""
    return execute(service.get_my_company, session, user)


@employer_router.patch("/company", response_model=CompanyPublic)
def update_company(
    payload: CompanyUpdate,
    session: Session = Depends(get_db),
    user: User = Depends(require_employer),
):
    """局部修改当前雇主的公司资料。"""
    return execute(service.update_my_company, session, user, payload)


@employer_router.post(
    "/jobs", response_model=JobPublic, status_code=status.HTTP_201_CREATED
)
def create_job(
    payload: JobCreate,
    session: Session = Depends(get_db),
    user: User = Depends(require_employer),
):
    """发布职位。"""
    return execute(service.create_job, session, user, payload)


@employer_router.get("/jobs", response_model=list[JobPublic])
def list_jobs(
    session: Session = Depends(get_db),
    user: User = Depends(require_employer),
):
    """列出当前雇主负责的未删除职位。"""
    return execute(service.list_my_jobs, session, user)


@employer_router.get("/jobs/{job_id}", response_model=JobPublic)
def get_job(
    job_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(require_employer),
):
    """读取当前雇主的单个职位。"""
    return execute(service.get_my_job, session, user, job_id)


@employer_router.patch("/jobs/{job_id}", response_model=JobPublic)
def update_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
    session: Session = Depends(get_db),
    user: User = Depends(require_employer),
):
    """局部修改职位；技能整体替换。"""
    return execute(service.update_job, session, user, job_id, payload)


@employer_router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(require_employer),
):
    """软删除职位；有依赖记录时返回 409。"""
    execute(service.delete_job, session, user, job_id)


@employer_router.patch(
    "/applications/{application_id}/status",
    response_model=ApplicationStatusPublic,
)
def change_application_status(
    application_id: uuid.UUID,
    payload: ApplicationStatusUpdate,
    session: Session = Depends(get_db),
    user: User = Depends(require_employer),
):
    """把申请设置为四个状态之一。"""
    return execute(
        service.change_application_status, session, user, application_id, payload
    )
