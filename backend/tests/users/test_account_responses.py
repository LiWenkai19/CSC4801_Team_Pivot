import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select


@pytest.fixture
def client(monkeypatch):
    """用演示配置和内存数据库验证实际路由，不连接业务数据库。"""
    for key, value in {
        "APP_NAME": "Account response tests",
        "SECRET_KEY": "isolated-test-key-with-at-least-32-characters",
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "10",
        "DATABASE_URL": "postgresql+psycopg://test:test@127.0.0.1:1/test",
    }.items():
        monkeypatch.setenv(key, value)

    from app.db.session import get_db
    from app.users.router import user_router
    from app.users.model import User
    from app.users.schema import UserPublic
    from app.users.service import require_candidate, require_employer

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    def test_db():
        """仅向真实业务服务提供隔离的数据库 Session。"""
        with Session(engine) as session:
            yield session

    app = FastAPI()
    app.state.test_engine = engine
    app.include_router(user_router)

    @app.get("/test/candidate", response_model=UserPublic)
    def candidate_only(curr_user: User = Depends(require_candidate)):
        """通过测试路由执行候选人依赖，验证实际依赖调用链。"""
        return UserPublic.model_validate(curr_user)

    @app.get("/test/employer", response_model=UserPublic)
    def employer_only(curr_user: User = Depends(require_employer)):
        """通过测试路由执行雇主依赖，验证实际依赖调用链。"""
        return UserPublic.model_validate(curr_user)

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_register_login_and_me_return_current_schema(client, role):
    """两种角色注册与登录返回认证结构，签发的令牌可读取本人账户。"""
    credentials = {"email": f"{role}@example.com", "password": "demo-password"}
    registered = client.post("/users/register", json=credentials | {"role": role})
    assert registered.status_code == 200
    assert set(registered.json()) == {"access_token", "token_type", "user"}
    assert registered.json()["token_type"] == "bearer"
    account = registered.json()["user"]
    assert set(account) == {"id", "email", "role"}
    assert account["email"] == credentials["email"]
    assert account["role"] == role
    signup_headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    signup_me = client.get("/users/me", headers=signup_headers)
    assert signup_me.status_code == 200
    assert signup_me.json() == account

    duplicate = client.post("/users/register", json=credentials | {"role": role})
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "User already exists"

    logged_in = client.post("/users/login", json=credentials)
    assert logged_in.status_code == 200
    assert set(logged_in.json()) == {"access_token", "token_type", "user"}
    assert logged_in.json()["token_type"] == "bearer"
    assert logged_in.json()["user"] == account
    headers = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}
    me = client.get("/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json() == account

    form_login = client.post(
        "/users/token",
        data={"username": credentials["email"], "password": credentials["password"]},
    )
    assert form_login.status_code == 200
    form_headers = {"Authorization": f"Bearer {form_login.json()['access_token']}"}
    assert client.get("/users/me", headers=form_headers).json() == account


def test_me_requires_valid_authentication(client):
    """本人账户接口拒绝缺失或无效 Token。"""
    assert client.get("/users/me").status_code == 401
    assert (
        client.get(
            "/users/me", headers={"Authorization": "Bearer invalid-token"}
        ).status_code
        == 401
    )


def test_register_rejects_invalid_role(client):
    """注册仍拒绝两种角色以外的取值。"""
    response = client.post(
        "/users/register",
        json={
            "email": "demo@example.com",
            "password": "demo-password",
            "role": "admin",
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("email", ["candidate@example.com", "missing@example.com"])
def test_login_rejects_wrong_password_or_missing_account(client, email):
    """无效凭据或不存在的账户不能取得认证响应。"""
    client.post(
        "/users/register",
        json={
            "email": "candidate@example.com",
            "password": "demo-password",
            "role": "candidate",
        },
    )
    response = client.post(
        "/users/login", json={"email": email, "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


@pytest.mark.parametrize("role", ["candidate", "employer"])
@pytest.mark.parametrize("required_role", ["candidate", "employer"])
def test_role_dependencies_allow_matching_role_and_reject_other_role(
    client, role, required_role
):
    """使用真实注册 Token 验证角色匹配放行，角色不符返回 403。"""
    auth = client.post(
        "/users/register",
        json={
            "email": f"{role}@example.com",
            "password": "demo-password",
            "role": role,
        },
    )
    assert auth.status_code == 200
    response = client.get(
        f"/test/{required_role}",
        headers={"Authorization": f"Bearer {auth.json()['access_token']}"},
    )
    if role == required_role:
        assert response.status_code == 200
        assert response.json() == auth.json()["user"]
    else:
        assert response.status_code == 403
        assert (
            response.json()["detail"] == f"{required_role.capitalize()} role required"
        )


@pytest.mark.parametrize("required_role", ["candidate", "employer"])
@pytest.mark.parametrize("token_kind", ["missing", "invalid", "expired"])
def test_role_dependencies_require_valid_authentication(
    client, required_role, token_kind
):
    """角色依赖先执行认证，缺失、无效或过期 Token 都返回 401。"""
    headers = {}
    if token_kind == "invalid":
        headers = {"Authorization": "Bearer invalid-token"}
    elif token_kind == "expired":
        import jwt

        from app.core.config import settings
        from app.users.model import utc_now

        token = jwt.encode(
            {"sub": "candidate@example.com", "exp": int(utc_now().timestamp()) - 60},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/test/{required_role}", headers=headers).status_code == 401


@pytest.mark.parametrize("description", [None, "We build software."])
def test_employer_profile_is_saved_for_current_user(client, description):
    """雇主首次创建资料返回 201，描述可省略，数据库所属用户正确。"""
    from app.users.model import EmployerProfile

    auth = client.post(
        "/users/register",
        json={"email": "employer@example.com", "password": "demo", "role": "employer"},
    ).json()
    payload = {"company_name": " Demo Company "}
    if description is not None:
        payload["company_description"] = description
    response = client.post(
        "/users/employer/profile",
        json=payload,
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 201
    assert response.json() == {
        "user_id": auth["user"]["id"],
        "company_name": "Demo Company",
        "company_description": description or "",
    }
    with Session(client.app.state.test_engine) as session:
        saved = session.exec(select(EmployerProfile)).one()
        assert str(saved.user_id) == auth["user"]["id"]
        assert saved.company_name == "Demo Company"
        assert saved.company_description == (description or "")


def test_employer_profile_duplicate_does_not_overwrite(client):
    """重复提交返回 409，第一次创建的公司资料保持不变。"""
    from app.users.model import EmployerProfile
    from sqlmodel import select

    auth = client.post(
        "/users/register",
        json={"email": "employer@example.com", "password": "demo", "role": "employer"},
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    assert (
        client.post(
            "/users/employer/profile", json={"company_name": "First"}, headers=headers
        ).status_code
        == 201
    )
    duplicate = client.post(
        "/users/employer/profile", json={"company_name": "Second"}, headers=headers
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Employer profile already exists"
    with Session(client.app.state.test_engine) as session:
        assert session.exec(select(EmployerProfile)).one().company_name == "First"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"company_name": " \t "},
        {"company_name": "Demo", "company_description": None},
    ],
)
def test_employer_profile_rejects_invalid_fields_without_writing(client, payload):
    """缺失名称、空白名称及 null 描述被拒绝，不留下资料记录。"""
    from app.users.model import EmployerProfile
    from sqlmodel import select

    auth = client.post(
        "/users/register",
        json={"email": "employer@example.com", "password": "demo", "role": "employer"},
    ).json()
    response = client.post(
        "/users/employer/profile",
        json=payload,
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 422
    with Session(client.app.state.test_engine) as session:
        assert session.exec(select(EmployerProfile)).all() == []


def register_profile_user(client, role="candidate", email="candidate@example.com"):
    """注册隔离演示用户并返回真实接口签发的认证信息。"""
    response = client.post(
        "/users/register", json={"email": email, "password": "demo", "role": role}
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize("with_content", [False, True])
def test_candidate_profile_saves_normalized_skills_and_private_resume(
    client, with_content
):
    """资料和技能均持久化，技能规范化，简历原文保留且可省略。"""
    import uuid
    from app.users.model import CandidateProfile, CandidateSkill

    auth = register_profile_user(client)
    payload = {"display_name": " Alice "}
    if with_content:
        payload.update(
            resume_text=" My resume\nSecond line ",
            skills=[" SQL ", "Python", "python", "", "\t "],
        )
    response = client.post(
        "/users/candidate/profile",
        json=payload,
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 201
    expected_skills = ["python", "sql"] if with_content else []
    assert response.json() == {
        "user_id": auth["user"]["id"],
        "display_name": "Alice",
        "resume_text": payload.get("resume_text", ""),
        "skills": expected_skills,
    }
    with Session(client.app.state.test_engine) as session:
        saved = session.get(CandidateProfile, uuid.UUID(auth["user"]["id"]))
        assert saved.display_name == "Alice"
        assert saved.resume_text == payload.get("resume_text", "")
        assert sorted(skill.name for skill in saved.skills) == expected_skills
        assert len(session.exec(select(CandidateSkill)).all()) == len(expected_skills)


def test_candidate_profile_duplicate_preserves_original_records(client):
    """重复提交返回 409，不覆盖原有简历、名称或技能。"""
    from app.users.model import CandidateProfile, CandidateSkill

    auth = register_profile_user(client)
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    original = {
        "display_name": "Alice",
        "resume_text": "Private resume",
        "skills": ["Python"],
    }
    assert (
        client.post(
            "/users/candidate/profile", json=original, headers=headers
        ).status_code
        == 201
    )
    duplicate = client.post(
        "/users/candidate/profile",
        json={"display_name": "Bob", "resume_text": "Changed", "skills": ["Rust"]},
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Candidate profile already exists"
    with Session(client.app.state.test_engine) as session:
        saved = session.exec(select(CandidateProfile)).one()
        assert saved.display_name == "Alice" and saved.resume_text == "Private resume"
        assert session.exec(select(CandidateSkill)).one().name == "python"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"display_name": " \t "},
        {"display_name": "Alice", "resume_text": None},
        {"display_name": "Alice", "skills": None},
        {"display_name": "Alice", "skills": [1]},
    ],
)
def test_candidate_profile_invalid_input_does_not_write(client, payload):
    """非法名称、简历或技能被拒绝，资料和技能均不写入。"""
    from app.users.model import CandidateProfile, CandidateSkill

    auth = register_profile_user(client)
    response = client.post(
        "/users/candidate/profile",
        json=payload,
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 422
    with Session(client.app.state.test_engine) as session:
        assert session.exec(select(CandidateProfile)).all() == []
        assert session.exec(select(CandidateSkill)).all() == []


@pytest.mark.parametrize("identity", ["anonymous", "invalid", "employer"])
def test_candidate_profile_requires_authenticated_candidate(client, identity):
    """候选人资料接口拒绝未认证请求和雇主，简历不会返回给雇主。"""
    from app.users.model import CandidateProfile, CandidateSkill

    headers = {}
    if identity == "invalid":
        headers = {"Authorization": "Bearer invalid-token"}
    elif identity == "employer":
        auth = register_profile_user(
            client, role="employer", email="employer@example.com"
        )
        headers = {"Authorization": f"Bearer {auth['access_token']}"}
    response = client.post(
        "/users/candidate/profile",
        json={"display_name": "Alice", "resume_text": "Private", "skills": ["Python"]},
        headers=headers,
    )
    assert response.status_code == (403 if identity == "employer" else 401)
    assert "resume_text" not in response.json()
    with Session(client.app.state.test_engine) as session:
        assert session.exec(select(CandidateProfile)).all() == []
        assert session.exec(select(CandidateSkill)).all() == []


def test_candidate_profile_cannot_be_created_for_another_user(client):
    """额外提交他人的 ID 不会改变候选人资料、简历及技能的归属。"""
    from app.users.model import CandidateProfile, CandidateSkill

    auth = register_profile_user(client)
    other = register_profile_user(client, email="other@example.com")
    response = client.post(
        "/users/candidate/profile",
        json={
            "display_name": "Alice",
            "user_id": other["user"]["id"],
            "skills": ["SQL"],
        },
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 201
    assert response.json()["user_id"] == auth["user"]["id"]
    with Session(client.app.state.test_engine) as session:
        assert (
            str(session.exec(select(CandidateProfile)).one().user_id)
            == auth["user"]["id"]
        )
        assert (
            str(session.exec(select(CandidateSkill)).one().candidate_id)
            == auth["user"]["id"]
        )


def test_candidate_profile_failed_commit_rolls_back_profile_and_skills(
    client, monkeypatch
):
    """数据库提交失败时资料和技能全部回滚，不留下半份资料。"""
    import uuid
    from sqlalchemy.exc import SQLAlchemyError
    from app.users.model import CandidateProfile, CandidateSkill, User
    from app.users.schema import CandidateProfileCreate
    from app.users.service import create_candidate_profile

    auth = register_profile_user(client)
    with Session(client.app.state.test_engine) as session:
        user = session.get(User, uuid.UUID(auth["user"]["id"]))
        assert user is not None

        def failed_commit():
            """先写入两张表，再模拟事务提交前的数据库失败。"""
            session.flush()
            assert session.exec(select(CandidateProfile)).one() is not None
            assert len(session.exec(select(CandidateSkill)).all()) == 2
            raise SQLAlchemyError("Simulated commit failure")

        monkeypatch.setattr(session, "commit", failed_commit)
        with pytest.raises(SQLAlchemyError, match="Simulated commit failure"):
            create_candidate_profile(
                session,
                user,
                CandidateProfileCreate(display_name="Alice", skills=["Python", "SQL"]),
            )
        assert session.exec(select(CandidateProfile)).all() == []
        assert session.exec(select(CandidateSkill)).all() == []


@pytest.mark.parametrize("identity", ["anonymous", "invalid", "candidate"])
def test_employer_profile_requires_authenticated_employer(client, identity):
    """资料接口拒绝未认证请求及候选人身份，且不写入数据库。"""
    from app.users.model import EmployerProfile
    from sqlmodel import select

    headers = {}
    if identity == "invalid":
        headers = {"Authorization": "Bearer invalid-token"}
    elif identity == "candidate":
        auth = client.post(
            "/users/register",
            json={
                "email": "candidate@example.com",
                "password": "demo",
                "role": "candidate",
            },
        ).json()
        headers = {"Authorization": f"Bearer {auth['access_token']}"}
    response = client.post(
        "/users/employer/profile", json={"company_name": "Demo"}, headers=headers
    )
    assert response.status_code == (403 if identity == "candidate" else 401)
    with Session(client.app.state.test_engine) as session:
        assert session.exec(select(EmployerProfile)).all() == []


def test_employer_profile_ignores_client_supplied_owner(client):
    """客户端提交他人 ID 不能改变资料归属。"""
    from sqlmodel import select
    from app.users.model import EmployerProfile

    accounts = []
    for name in ["first", "second"]:
        accounts.append(
            client.post(
                "/users/register",
                json={
                    "email": f"{name}@example.com",
                    "password": "demo",
                    "role": "employer",
                },
            ).json()
        )
    response = client.post(
        "/users/employer/profile",
        json={"company_name": "Demo", "user_id": accounts[1]["user"]["id"]},
        headers={"Authorization": f"Bearer {accounts[0]['access_token']}"},
    )
    assert response.status_code == 201
    assert response.json()["user_id"] == accounts[0]["user"]["id"]
    with Session(client.app.state.test_engine) as session:
        assert (
            str(session.exec(select(EmployerProfile)).one().user_id)
            == accounts[0]["user"]["id"]
        )


def test_employer_profile_rolls_back_failed_commit(client, monkeypatch):
    """提交失败时回滚已写入的资料，Session 可继续使用。"""
    import uuid
    from sqlalchemy.exc import SQLAlchemyError
    from sqlmodel import select
    from app.users.model import EmployerProfile, User
    from app.users.schema import EmployerProfileCreate
    from app.users.service import create_employer_profile

    auth = client.post(
        "/users/register",
        json={"email": "employer@example.com", "password": "demo", "role": "employer"},
    ).json()
    with Session(client.app.state.test_engine) as session:
        user = session.get(User, uuid.UUID(auth["user"]["id"]))
        assert user is not None

        def failed_commit():
            """模拟写入完成但事务尚未提交时发生数据库错误。"""
            session.flush()
            raise SQLAlchemyError("Simulated commit failure")

        monkeypatch.setattr(session, "commit", failed_commit)
        with pytest.raises(SQLAlchemyError, match="Simulated commit failure"):
            create_employer_profile(
                session, user, EmployerProfileCreate(company_name="Demo")
            )
        assert session.exec(select(EmployerProfile)).all() == []
