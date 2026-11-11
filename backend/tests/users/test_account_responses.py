import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select


def auth_of(response) -> dict:
    """解析注册/登录响应，并附上以会话 Cookie 和 CSRF 令牌组成的认证请求头。

    凭证只在 Set-Cookie 中下发；测试显式携带它们，模拟浏览器回传 Cookie
    以及前端从可读的 csrf_token Cookie 取值放进 X-CSRF-Token 头。
    """
    data = response.json()
    data["headers"] = {
        "Cookie": f"session={response.cookies['session']}",
        "X-CSRF-Token": response.cookies["csrf_token"],
    }
    return data


def expire_all_sessions(engine) -> None:
    """把库内全部会话改为已过期，模拟超过有效期后的请求。"""
    import datetime

    from app.users.model import UserSession, utc_now

    with Session(engine) as session:
        for row in session.exec(select(UserSession)).all():
            row.expires_at = utc_now() - datetime.timedelta(minutes=1)
            session.add(row)
        session.commit()


@pytest.fixture
def client(monkeypatch):
    """用演示配置和内存数据库验证实际路由，不连接业务数据库。"""
    for key, value in {
        "APP_NAME": "Account response tests",
        # http://testserver 不是 HTTPS，Secure Cookie 不会被回传，测试里关闭。
        "COOKIE_SECURE": "false",
        "DATABASE_URL": "postgresql+psycopg://test:test@127.0.0.1:1/test",
    }.items():
        monkeypatch.setenv(key, value)

    from app.db.session import get_db
    from app.users.router import user_router
    from app.users.model import User
    from app.users.schema import UserPublic
    from app.users.service import (
        get_current_user_public,
        require_candidate,
        require_employer,
    )

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
    def candidate_only(
        curr_user: User = Depends(require_candidate), session: Session = Depends(get_db)
    ):
        """通过测试路由执行候选人依赖，验证实际依赖调用链。"""
        return get_current_user_public(session, curr_user)

    @app.get("/test/employer", response_model=UserPublic)
    def employer_only(
        curr_user: User = Depends(require_employer), session: Session = Depends(get_db)
    ):
        """通过测试路由执行雇主依赖，验证实际依赖调用链。"""
        return get_current_user_public(session, curr_user)

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as test_client:
            # Cookie 已在响应对象上解析完毕；清空客户端 Cookie 罐，
            # 让每个请求的身份只由测试显式传入的 headers 决定，多账户切换不会串号。
            test_client.event_hooks["response"].append(
                lambda response: test_client.cookies.clear()
            )
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_register_login_and_me_return_current_schema(client, role):
    """两种角色的注册、登录和本人账户响应统一包含未完成状态。"""
    credentials = {"email": f"{role}@example.com", "password": "demo-password"}
    registered = client.post("/users/register", json=credentials | {"role": role})
    assert registered.status_code == 200
    # FP-AUTH-2：认证机密不出现在响应体，只通过 Set-Cookie 下发。
    assert set(registered.json()) == {"user"}
    account = registered.json()["user"]
    assert set(account) == {"id", "email", "role", "profile_completed"}
    assert account["email"] == credentials["email"]
    assert account["role"] == role
    assert account["profile_completed"] is False
    signup_headers = auth_of(registered)["headers"]
    signup_me = client.get("/users/me", headers=signup_headers)
    assert signup_me.status_code == 200
    assert signup_me.json() == account

    duplicate = client.post("/users/register", json=credentials | {"role": role})
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "User already exists"

    logged_in = client.post("/users/login", json=credentials)
    assert logged_in.status_code == 200
    assert set(logged_in.json()) == {"user"}
    assert logged_in.json()["user"] == account
    headers = auth_of(logged_in)["headers"]
    me = client.get("/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json() == account

    # FP-AUTH-1：登出在服务端删除会话，留存的旧 Cookie 随即失效。
    assert client.post("/users/logout", headers=headers).status_code == 204
    assert client.get("/users/me", headers=headers).status_code == 401
    # 注册时建立的会话与登录会话相互独立，不受这次登出影响。
    assert client.get("/users/me", headers=signup_headers).json() == account


def test_me_requires_valid_authentication(client):
    """本人账户接口拒绝缺失或无效 Token。"""
    assert client.get("/users/me").status_code == 401
    assert (
        client.get(
            "/users/me", headers={"Cookie": "session=invalid-token"}
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
        headers=auth_of(auth)["headers"],
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
        headers = {"Cookie": "session=invalid-token"}
    elif token_kind == "expired":
        headers = register_profile_user(client, role=required_role)["headers"]
        expire_all_sessions(client.app.state.test_engine)
    assert client.get(f"/test/{required_role}", headers=headers).status_code == 401


@pytest.mark.parametrize("description", [None, "We build software."])
def test_employer_profile_is_saved_for_current_user(client, description):
    """雇主首次创建资料返回 201，描述可省略，数据库所属用户正确。"""
    from app.users.model import EmployerProfile

    auth = auth_of(client.post(
        "/users/register",
        json={"email": "employer@example.com", "password": "demo", "role": "employer"},
    ))
    payload = {"company_name": " Demo Company "}
    if description is not None:
        payload["company_description"] = description
    response = client.post(
        "/users/employer/profile",
        json=payload,
        headers=auth["headers"],
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

    auth = auth_of(client.post(
        "/users/register",
        json={"email": "employer@example.com", "password": "demo", "role": "employer"},
    ))
    headers = auth["headers"]
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

    auth = auth_of(client.post(
        "/users/register",
        json={"email": "employer@example.com", "password": "demo", "role": "employer"},
    ))
    response = client.post(
        "/users/employer/profile",
        json=payload,
        headers=auth["headers"],
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
    return auth_of(response)


@pytest.mark.parametrize(
    "role, payload",
    [
        ("candidate", {"display_name": "Alice"}),
        ("employer", {"company_name": "Demo Company"}),
    ],
)
def test_me_refreshes_profile_status_after_creating_minimal_profile(client, role, payload):
    """仅填写名称即完成资料，原 Token 查询和再次登录均返回最新状态。"""
    auth = register_profile_user(client, role=role)
    headers = auth["headers"]
    before = client.get("/users/me", headers=headers)
    assert before.status_code == 200
    assert before.json() == auth["user"] | {"profile_completed": False}

    created = client.post(f"/users/{role}/profile", json=payload, headers=headers)
    assert created.status_code == 201
    if role == "candidate":
        assert created.json()["resume_text"] == ""
        assert created.json()["skills"] == []
    else:
        assert created.json()["company_description"] == ""

    after = client.get("/users/me", headers=headers)
    assert after.status_code == 200
    assert after.json() == auth["user"] | {"profile_completed": True}

    logged_in = client.post(
        "/users/login", json={"email": auth["user"]["email"], "password": "demo"}
    )
    assert logged_in.status_code == 200
    assert set(logged_in.json()) == {"user"}
    assert logged_in.json()["user"] == after.json()
    login_headers = auth_of(logged_in)["headers"]
    assert client.get("/users/me", headers=login_headers).json() == after.json()


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_me_ignores_other_users_profiles_and_client_supplied_owner(client, role):
    """他人资料和请求中伪造的用户 ID 都不影响本人完成状态。"""
    auth = register_profile_user(client, role=role)
    other = register_profile_user(client, role=role, email="other@example.com")
    other_headers = other["headers"]
    payload = (
        {"display_name": "Other", "resume_text": "Private resume"}
        if role == "candidate"
        else {"company_name": "Other Company"}
    )
    assert client.post(
        f"/users/{role}/profile", json=payload, headers=other_headers
    ).status_code == 201

    response = client.get(
        "/users/me",
        params={"user_id": other["user"]["id"]},
        headers=auth["headers"],
    )
    assert response.status_code == 200
    assert response.json() == auth["user"] | {"profile_completed": False}
    assert client.get("/users/me", headers=other_headers).json() == other["user"] | {
        "profile_completed": True
    }


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_me_only_counts_profile_matching_current_role(client, role):
    """隔离库中的错配角色资料不会被计为当前角色资料已完成。"""
    import uuid

    from app.users.model import CandidateProfile, EmployerProfile

    auth = register_profile_user(client, role=role)
    user_id = uuid.UUID(auth["user"]["id"])
    wrong_profile = (
        EmployerProfile(user_id=user_id, company_name="Wrong role")
        if role == "candidate"
        else CandidateProfile(user_id=user_id, display_name="Wrong role")
    )
    with Session(client.app.state.test_engine) as session:
        session.add(wrong_profile)
        session.commit()

    response = client.get(
        "/users/me", headers=auth["headers"]
    )
    assert response.status_code == 200
    assert response.json() == auth["user"] | {"profile_completed": False}


@pytest.mark.parametrize("identity", ["expired", "missing_account"])
def test_me_rejects_expired_token_or_missing_account(client, identity):
    """过期会话及已不存在的账户均返回 401，不泄露资料完成状态。"""
    import uuid

    from app.users.model import User, UserSession

    auth = register_profile_user(client)
    engine = client.app.state.test_engine
    if identity == "expired":
        expire_all_sessions(engine)
    else:
        # SQLite 测试库不强制外键：直接删掉账户，只留下指向它的会话。
        with Session(engine) as session:
            session.delete(session.get(User, uuid.UUID(auth["user"]["id"])))
            session.commit()

    response = client.get("/users/me", headers=auth["headers"])
    assert response.status_code == 401
    assert "profile_completed" not in response.json()
    if identity == "expired":
        # 过期会话在被访问时顺手从库中删除。
        with Session(engine) as session:
            assert session.exec(select(UserSession)).all() == []


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_me_does_not_treat_database_failure_as_incomplete_profile(client, monkeypatch, role):
    """资料查询失败应返回服务端错误，不能伪装为资料未填写。"""
    from sqlalchemy.exc import SQLAlchemyError

    from app.users.model import CandidateProfile, EmployerProfile

    auth = register_profile_user(client, role=role)
    original_get = Session.get

    def failed_profile_get(session, entity, ident, **kwargs):
        """仅模拟资料查询故障，保留真实 Token 认证及账户查询。"""
        if entity in (CandidateProfile, EmployerProfile):
            raise SQLAlchemyError("Simulated profile query failure")
        return original_get(session, entity, ident, **kwargs)

    monkeypatch.setattr(Session, "get", failed_profile_get)
    with TestClient(client.app, raise_server_exceptions=False) as failing_client:
        response = failing_client.get(
            "/users/me", headers=auth["headers"]
        )
    assert response.status_code == 500
    assert "profile_completed" not in response.text


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
        headers=auth["headers"],
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
    headers = auth["headers"]
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
        headers=auth["headers"],
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
        headers = {"Cookie": "session=invalid-token"}
    elif identity == "employer":
        auth = register_profile_user(
            client, role="employer", email="employer@example.com"
        )
        headers = auth["headers"]
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
        headers=auth["headers"],
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
        headers = {"Cookie": "session=invalid-token"}
    elif identity == "candidate":
        auth = auth_of(client.post(
            "/users/register",
            json={
                "email": "candidate@example.com",
                "password": "demo",
                "role": "candidate",
            },
        ))
        headers = auth["headers"]
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
            auth_of(client.post(
                "/users/register",
                json={
                    "email": f"{name}@example.com",
                    "password": "demo",
                    "role": "employer",
                },
            ))
        )
    response = client.post(
        "/users/employer/profile",
        json={"company_name": "Demo", "user_id": accounts[1]["user"]["id"]},
        headers=accounts[0]["headers"],
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

    auth = auth_of(client.post(
        "/users/register",
        json={"email": "employer@example.com", "password": "demo", "role": "employer"},
    ))
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


# ===== 会话 Cookie 与 CSRF =====


def _set_cookie_headers(response) -> dict[str, str]:
    """把多个 Set-Cookie 头按 Cookie 名整理成 {名称: 小写原始头}。"""
    return {
        header.split("=", 1)[0]: header.lower()
        for header in response.headers.get_list("set-cookie")
    }


def test_session_cookie_is_httponly_and_csrf_cookie_is_readable(client):
    """会话 Cookie 对 JS 不可见；CSRF Cookie 需要被前端读取。两者都带 SameSite=Lax。"""
    response = client.post(
        "/users/register",
        json={"email": "candidate@example.com", "password": "demo", "role": "candidate"},
    )
    cookies = _set_cookie_headers(response)
    assert "httponly" in cookies["session"]
    assert "samesite=lax" in cookies["session"]
    assert "httponly" not in cookies["csrf_token"]
    assert "samesite=lax" in cookies["csrf_token"]


def test_remember_me_controls_cookie_persistence(client):
    """未勾选"记住我"为浏览器会话 Cookie；勾选后保留 30 天。"""
    credentials = {"email": "candidate@example.com", "password": "demo"}
    client.post("/users/register", json=credentials | {"role": "candidate"})

    short = client.post("/users/login", json=credentials | {"remember_me": False})
    assert "max-age" not in _set_cookie_headers(short)["session"]
    long = client.post("/users/login", json=credentials | {"remember_me": True})
    assert "max-age=2592000" in _set_cookie_headers(long)["session"]


def test_each_login_creates_a_new_session_stored_only_as_hash(client):
    """每次登录换新会话 ID（防会话固定）；库里只有哈希，查不到 Cookie 原文。"""
    from app.users.model import UserSession

    credentials = {"email": "candidate@example.com", "password": "demo"}
    first = auth_of(
        client.post("/users/register", json=credentials | {"role": "candidate"})
    )["headers"]["Cookie"]
    second = auth_of(client.post("/users/login", json=credentials))["headers"]["Cookie"]
    assert first != second

    with Session(client.app.state.test_engine) as session:
        stored = session.exec(select(UserSession.token_hash)).all()
    raw_ids = {first.removeprefix("session="), second.removeprefix("session=")}
    assert len(stored) == 2
    assert raw_ids.isdisjoint(stored)


@pytest.mark.parametrize("csrf", [None, "wrong-token"])
def test_unsafe_requests_require_matching_csrf_token(client, csrf):
    """写请求缺少或带错 CSRF 令牌返回 403，且不写入任何数据；读请求不受影响。"""
    from app.users.model import CandidateProfile

    auth = register_profile_user(client)
    headers = {"Cookie": auth["headers"]["Cookie"]}
    if csrf:
        headers["X-CSRF-Token"] = csrf

    response = client.post(
        "/users/candidate/profile", json={"display_name": "Alice"}, headers=headers
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token missing or invalid"
    with Session(client.app.state.test_engine) as session:
        assert session.exec(select(CandidateProfile)).all() == []

    assert client.get("/users/me", headers=headers).status_code == 200
    assert client.post("/users/logout", headers=headers).status_code == 403
    assert client.get("/users/me", headers=headers).status_code == 200


def test_logout_requires_authentication(client):
    """未登录时登出返回 401。"""
    assert client.post("/users/logout").status_code == 401
