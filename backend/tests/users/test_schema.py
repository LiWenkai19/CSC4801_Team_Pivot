import uuid

import pytest
from pydantic import ValidationError

from app.users.model import Role, User
from app.users.schema import (
    AuthResponse,
    CandidateProfileCreate,
    CandidateProfilePublic,
    CandidateProfileUpdate,
    EmployerProfileCreate,
    EmployerProfileUpdate,
    UserCreate,
    UserLogin,
    UserPublic,
)


def test_signup_only_requires_account_fields():
    """两种角色注册时都不需要提交基本资料。"""
    for role in Role:
        request = UserCreate(email="demo@example.com", password="password", role=role)
        assert set(request.model_dump()) == {"email", "password", "role"}
        assert request.role is role


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "invalid-email"},
        {"password": ""},
        {"role": "admin"},
        {"resume_text": "private"},
    ],
)
def test_signup_rejects_invalid_or_extra_fields(changes):
    """注册拒绝无效账户字段及不属于注册步骤的资料。"""
    payload = {"email": "demo@example.com", "password": "password", "role": "candidate"}
    with pytest.raises(ValidationError):
        UserCreate.model_validate(payload | changes)


def test_login_preserves_password_and_remember_me_default():
    """登录不裁剪密码，并保留已有记住登录的默认值。"""
    request = UserLogin(email="demo@example.com", password=" password ")
    assert request.password == " password "
    assert request.remember_me is False


def test_profile_create_allows_omitting_optional_content():
    """仅名称即可创建基本资料，其他内容默认空值。"""
    candidate = CandidateProfileCreate(display_name=" Alice ")
    employer = EmployerProfileCreate(company_name=" Demo ")
    assert candidate.display_name == "Alice"
    assert candidate.resume_text == ""
    assert candidate.skills == []
    assert employer.company_name == "Demo"
    assert employer.company_description == ""
    candidate.skills.append("python")
    assert CandidateProfileCreate(display_name="Bob").skills == []


@pytest.mark.parametrize(
    "schema, payload",
    [
        (CandidateProfileCreate, {}),
        (CandidateProfileCreate, {"display_name": " \t "}),
        (EmployerProfileCreate, {}),
        (EmployerProfileCreate, {"company_name": " \n "}),
        (CandidateProfileCreate, {"display_name": "Alice", "skills": [1]}),
        (
            CandidateProfileCreate,
            {"display_name": "Alice", "user_id": str(uuid.uuid4())},
        ),
        (EmployerProfileCreate, {"company_name": "Demo", "role": "candidate"}),
    ],
)
def test_profile_create_validates_names_types_and_ownership_fields(schema, payload):
    """资料创建拒绝空白名称、无效技能及客户端指定所有者或角色。"""
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


def test_profile_update_distinguishes_omission_from_clearing():
    """未传字段不更新，显式空内容用于清空可选字段。"""
    assert CandidateProfileUpdate().model_dump(exclude_unset=True) == {}
    assert EmployerProfileUpdate().model_dump(exclude_unset=True) == {}
    assert CandidateProfileUpdate(resume_text="", skills=[]).model_dump(
        exclude_unset=True
    ) == {"resume_text": "", "skills": []}
    assert EmployerProfileUpdate(company_description="").model_dump(
        exclude_unset=True
    ) == {"company_description": ""}


@pytest.mark.parametrize(
    "schema, field",
    [
        (CandidateProfileUpdate, "display_name"),
        (CandidateProfileUpdate, "resume_text"),
        (CandidateProfileUpdate, "skills"),
        (EmployerProfileUpdate, "company_name"),
        (EmployerProfileUpdate, "company_description"),
    ],
)
def test_profile_update_rejects_explicit_null(schema, field):
    """显式 null 不能写入数据库非空资料字段。"""
    with pytest.raises(ValidationError):
        schema.model_validate({field: None})


def test_auth_response_excludes_password_hash_and_private_profile():
    """认证响应只暴露账户信息，不包含密码哈希或私有资料。"""
    user = User(
        email="demo@example.com", hashed_password="fake-hash", role=Role.Candidate
    )
    public = UserPublic.model_validate(user)
    response = AuthResponse(access_token="fake-token", user=public).model_dump(
        mode="json"
    )
    assert response["token_type"] == "bearer"
    assert response["user"] == {
        "id": str(user.id),
        "email": user.email,
        "role": "candidate",
    }
    assert "hashed_password" not in response["user"]
    assert "resume_text" not in response["user"]


def test_owner_profile_response_preserves_resume_text():
    """本人资料响应保留简历原文与空技能列表。"""
    profile = CandidateProfilePublic(
        user_id=uuid.uuid4(),
        display_name="Alice",
        resume_text=" Line 1\nLine 2 ",
        skills=[],
    )
    assert profile.resume_text == " Line 1\nLine 2 "
    assert profile.skills == []
