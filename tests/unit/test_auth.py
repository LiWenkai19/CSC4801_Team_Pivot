"""FP-AUTH-1/2/3与FP-SEC-2：账户、凭据、会话和拒绝合同。"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from app.main import app
from app.users import security, service
from app.users.model import Role, UserSession
from app.users.schema import AuthResponse, UserCreate, UserPublic

NOW = datetime(2030, 5, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize("role", list(Role))
def test_fp_auth_1_registration_and_session_lifecycle(db, actors, monkeypatch, role):
    request = UserCreate(
        email="unit@example.com", password="local-unit-only", role=role
    )
    created = service.create_user(db, request)
    assert created.email == request.email and created.role == role
    assert security.verify_password(request.password, created.hashed_password)
    db.commit.assert_called_once()
    monkeypatch.setattr(service, "utc_now", lambda: NOW)
    db.reset_mock()
    raw, row = service.create_session(db, created, remember_me=False)
    assert row.user_id == created.id
    assert row.token_hash == security.hash_session_token(raw) != raw
    assert row.csrf_token and row.csrf_token != raw
    assert row.expires_at == NOW + service.session_lifetime(False)
    service.revoke_session(db, row)
    db.delete.assert_called_once_with(row)
    assert db.commit.call_count == 2


def test_fp_auth_1_duplicate_identifier_is_rejected(db, actors, result):
    db.exec.return_value = result(first=actors[0])
    with pytest.raises(ValueError, match="User already exists"):
        service.create_user(
            db, UserCreate(email=actors[0].email, password="test", role=Role.Candidate)
        )
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "field,value", [("email", "invalid"), ("password", ""), ("role", "admin")]
)
def test_fp_auth_1_invalid_registration(field, value):
    payload = dict(email="normal@example.com", password="test", role="candidate")
    payload[field] = value
    with pytest.raises(ValidationError):
        UserCreate(**payload)


def test_fp_auth_1_login_checks_actual_password(db, actors, result):
    user = actors[0]
    user.hashed_password = security.hash_password("correct")
    db.exec.return_value = result(first=user)
    assert service.authenticate_user(db, user.email, "correct") is user
    assert service.authenticate_user(db, user.email, "wrong") is None
    db.exec.return_value = result()
    assert service.authenticate_user(db, "missing@example.com", "correct") is None


def test_fp_auth_2_salted_hash_and_password_verification():
    first, second = security.hash_password("same"), security.hash_password("same")
    assert (
        first != second and first.startswith("$argon2") and second.startswith("$argon2")
    )
    assert security.verify_password("same", first)
    assert not security.verify_password("wrong", first)


def test_fp_auth_2_response_has_no_authentication_secrets(actors):
    user = actors[0]
    body = AuthResponse(
        user=UserPublic(
            id=user.id, email=user.email, role=user.role, profile_completed=False
        )
    ).model_dump()
    assert set(body) == {"user"}
    assert set(body["user"]) == {"id", "email", "role", "profile_completed"}


@pytest.mark.parametrize(
    "path,fields,missing",
    [
        ("/users/login", {}, "email"),
        ("/users/register", {"email": "unit@example.com"}, "role"),
    ],
)
def test_fp_auth_2_validation_errors_do_not_echo_password(path, fields, missing):
    """登录或注册缺少必填字段时，只返回校验详情，且不回显密码。"""
    password = "synthetic-validation-password"

    with TestClient(app) as client:
        response = client.post(path, json={**fields, "password": password})

    assert response.status_code == 422
    assert password not in response.text
    assert response.json() == {
        "detail": [{"loc": ["body", missing], "msg": "Field required", "type": "missing"}]
    }
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("token", [None, "unknown-token"])
def test_fp_auth_3_unauthenticated_is_401(db, token):
    with pytest.raises(HTTPException) as caught:
        service.get_valid_session(db, token)
    assert caught.value.status_code == 401


def test_fp_auth_3_expired_session_is_revoked(db, actors, result, monkeypatch):
    monkeypatch.setattr(service, "utc_now", lambda: NOW)
    row = UserSession(
        user_id=actors[0].id, token_hash="hash", csrf_token="csrf", expires_at=NOW
    )
    db.exec.return_value = result(first=row)
    with pytest.raises(HTTPException) as caught:
        service.get_valid_session(db, "token")
    assert caught.value.status_code == 401
    db.delete.assert_called_once_with(row)
    db.commit.assert_called_once()


def test_fp_auth_3_valid_session_and_role_guards(db, actors, result, monkeypatch):
    monkeypatch.setattr(service, "utc_now", lambda: NOW)
    row = SimpleNamespace(expires_at=NOW + timedelta(seconds=1), user=actors[0])
    db.exec.return_value = result(first=row)
    assert service.get_valid_session(db, "valid") is row
    assert service.get_current_user(row) is actors[0]
    assert service.require_candidate(actors[0]) is actors[0]
    assert service.require_employer(actors[1]) is actors[1]
    for guard, user in [
        (service.require_candidate, actors[1]),
        (service.require_employer, actors[0]),
    ]:
        with pytest.raises(HTTPException) as caught:
            guard(user)
        assert caught.value.status_code == 403


@pytest.mark.parametrize(
    "method,token,accepted",
    [
        ("GET", None, True),
        ("POST", None, False),
        ("PATCH", "wrong", False),
        ("DELETE", "right", True),
    ],
)
def test_fp_auth_3_csrf_contract(method, token, accepted):
    request = Request({"type": "http", "method": method})
    session = SimpleNamespace(csrf_token="right")
    if accepted:
        assert service.require_csrf(request, session, token) is session
    else:
        with pytest.raises(HTTPException) as caught:
            service.require_csrf(request, session, token)
        assert caught.value.status_code == 403


def test_fp_sec_2_email_is_a_bound_value(db):
    from sqlalchemy.dialects import postgresql

    ordinary_text = "ordinary'quote;--@example.com"
    service.get_user_by_email(db, ordinary_text)
    query = db.exec.call_args.args[0].compile(dialect=postgresql.dialect())
    assert ordinary_text in query.params.values()
    assert ordinary_text not in str(query)


def test_fp_auth_3_openapi_documents_actual_error_shapes():
    """错误响应声明覆盖已有的拒绝合同，且与真实未认证响应一致。"""
    from app.main import app
    from fastapi.testclient import TestClient

    schema = app.openapi()
    account_codes = {
        ("/users/register", "post"): (400,),
        ("/users/login", "post"): (400, 401),
        ("/users/logout", "post"): (401, 403),
        ("/users/me", "get"): (401,),
        ("/users/candidate/profile", "post"): (401, 403, 409),
        ("/users/employer/profile", "post"): (401, 403, 409),
    }
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method not in {"get", "post", "patch", "delete"}:
                continue
            codes = account_codes.get((path, method), (401, 403))
            if path.startswith(("/candidate", "/employer")) and (
                "{" in path or path.endswith(("/profile", "/company"))
            ):
                codes = (*codes, 404)
            for code in codes:
                definition = operation["responses"][str(code)]["content"]["application/json"]["schema"]
                if "$ref" in definition:
                    definition = schema["components"]["schemas"][definition["$ref"].rsplit("/", 1)[-1]]
                assert "detail" in definition["required"]
                assert definition["properties"]["detail"]["type"] == "string"
    with TestClient(app) as client:
        actual = client.get("/candidate/jobs")
    assert actual.status_code == 401
    assert actual.json() == {"detail": "Not authenticated"}
