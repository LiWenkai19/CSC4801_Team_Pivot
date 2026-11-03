import uuid

import pytest

from sqlalchemy.exc import SQLAlchemyError

from sqlmodel import Session, select

from app.candidate.model import Application, ApplicationStatus, Booking

from app.matching import applicant_sort_key, job_sort_key, match_score

from app.users.model import CandidateProfile, User

from app.candidate.profile_schema import CandidateProfileUpdate


def test_password_hash_is_salted_and_verified():
    from app.users.security import hash_password, verify_password

    first = hash_password("demo-password")
    second = hash_password("demo-password")
    assert first != second and first != "demo-password"
    assert first.startswith("$argon2")
    assert verify_password("demo-password", first)
    assert not verify_password("wrong", first)


def test_profile_persistence_omission_and_clearing(flow):
    c, h = flow["client"], flow["headers"][0]
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    assert c.get(path, headers=h).json()["resume_text"] == "Private\nResume"
    response = c.patch(
        path,
        # 带上测试账户的认证请求头，使请求以指定身份执行
        headers=h,
        # 请求的 JSON 正文，不是直接修改数据库
        json={"skills": [" SQL ", "Python", "sql", ""], "display_name": " New "},
    )
    assert response.status_code == 200
    assert response.json()["skills"] == ["python", "sql"]
    assert response.json()["display_name"] == "New"
    assert response.json()["resume_text"] == "Private\nResume"
    assert c.patch(path, headers=h, json={"skills": ["Rust"]}).json()["skills"] == [
        "rust"
    ]
    assert (
        c.patch(path, headers=h, json={"resume_text": "", "skills": []}).status_code
        == 200
    )
    assert c.get(path, headers=h).json()["skills"] == []
    with Session(flow["engine"]) as s:
        assert s.get(CandidateProfile, flow["ids"][0]).resume_text == ""


# 让相同测试用下面各组输入分别运行，覆盖不同边界
@pytest.mark.parametrize(
    "payload",
    [
        {"display_name": "  "},
        {"skills": [1]},
        {"resume_text": None},
        {"skills": None},
        {"role": "employer"},
        {"user_id": "injected"},
    ],
)
def test_profile_invalid_request_is_atomic(flow, payload):
    c = flow["client"]
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    assert c.patch(path, headers=flow["headers"][0], json=payload).status_code == 422
    assert (
        c.get(path, headers=flow["headers"][0]).json()["resume_text"]
        == "Private\nResume"
    )


# 让相同测试用下面各组输入分别运行，覆盖不同边界
@pytest.mark.parametrize("method", ["get", "patch"])
def test_private_profile_authorization_and_missing(flow, method):
    c = flow["client"]
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    kwargs = {"json": {"resume_text": "stolen"}} if method == "patch" else {}
    call = getattr(c, method)
    assert call(path, **kwargs).status_code == 401
    forbidden = flow["headers"][1:2] if method == "get" else flow["headers"][1:]
    for h in forbidden:
        assert call(path, headers=h, **kwargs).status_code == 403
    registered = c.post(
        "/users/register",
        # 请求的 JSON 正文，不是直接修改数据库
        json={"email": "missing@example.com", "password": "demo", "role": "candidate"},
    ).json()
    missing_id = registered["user"]["id"]
    missing_headers = {"Authorization": f"Bearer {registered['access_token']}"}
    assert (
        call(
            f"/users/candidates/{missing_id}/profile",
            headers=missing_headers,
            **kwargs,
        ).status_code
        == 404
    )


def test_profile_failed_commit_rolls_back(flow, monkeypatch):
    from app.candidate.service import update_profile

    with Session(flow["engine"]) as s:
        user = s.get(User, flow["ids"][0])

        def fail():
            s.flush()
            raise SQLAlchemyError("failed commit")

        # 暂时替换方法以模拟失败，测试结束后由 monkeypatch 恢复
        monkeypatch.setattr(s, "commit", fail)
        with pytest.raises(SQLAlchemyError):
            # 只修改明确提交的字段，名称/简历/技能一起提交，任何失败都整体回滚
            update_profile(
                s,
                user,
                user.id,
                CandidateProfileUpdate(
                    display_name="Bad",
                    skills=["rust"],
                    resume_text="bad",
                ),
            )
    with Session(flow["engine"]) as s:
        p = s.get(CandidateProfile, flow["ids"][0])
        assert p.display_name == "Alice" and p.resume_text == "Private\nResume"
        assert sorted(skill.name for skill in p.skills) == ["python", "sql"]


# 让相同测试用下面各组输入分别运行，覆盖不同边界
@pytest.mark.parametrize(
    "candidate,required,expected",
    [
        (["Python", "SQL"], ["Python", "SQL"], 100),
        (["Python"], ["Python", "SQL"], 50),
        (["Rust"], ["Python", "SQL"], 0),
        ([], [], 100),
        (["PYTHON", " python ", ""], ["python", "SQL", "rust", "SQL"], 33),
    ],
)
def test_matching_examples_normalization_and_floor(candidate, required, expected):
    assert match_score(candidate, required) == expected


def test_matching_both_tie_breakers():
    jobs = [
        dict(id="b", title="alpha", score=50),
        dict(id="a", title="ALPHA", score=50),
        dict(id="c", title="z", score=100),
    ]
    assert [x["id"] for x in sorted(jobs, key=job_sort_key)] == ["c", "a", "b"]
    people = [
        dict(candidate_id="b", display_name="Alice", score=50),
        dict(candidate_id="a", display_name="alice", score=50),
    ]
    assert [x["candidate_id"] for x in sorted(people, key=applicant_sort_key)] == [
        "a",
        "b",
    ]


def test_jobs_all_active_order_and_placeholder_scores(flow):
    c, h = flow["client"], flow["headers"][0]
    rows = c.get("/candidate/jobs", headers=h).json()
    assert [r["title"] for r in rows] == ["alpha", "Alpha", "Beta", "Empty"]
    assert len(rows) == 4 and rows[0]["applied"]
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    # 用测试客户端发送真实接口请求，经过路由、权限和业务服务
    c.patch(path, headers=h, json={"skills": ["Python"]})
    assert c.get("/candidate/jobs", headers=h).json()[0]["title"] == "alpha"
    detail = f"/candidate/jobs/{flow['jobs'][0]}"
    assert c.get(detail, headers=h).json()["score"] == 0
    assert c.get(detail, headers=h).json()["score_kind"] == "placeholder"
    # 用测试客户端发送真实接口请求，经过路由、权限和业务服务
    c.patch(path, headers=h, json={"resume_text": "SQL Rust"})
    assert c.get(detail, headers=h).json()["score"] == 0
    assert c.get(f"/candidate/jobs/{flow['jobs'][-1]}", headers=h).status_code == 404


def test_application_pending_duplicate_and_private(flow):
    c, h = flow["client"], flow["headers"][0]
    path = f"/candidate/jobs/{flow['jobs'][1]}/applications"
    assert c.post(path, headers=h, json={"status": "Accepted"}).status_code == 422
    response = c.post(path, headers=h, json={})
    assert response.status_code == 201 and response.json()["status"] == "Pending"
    assert c.post(path, headers=h).status_code == 409
    detail = f"/candidate/applications/{response.json()['id']}"
    assert c.get(detail, headers=flow["headers"][1]).status_code == 403
    assert c.get(detail, headers=flow["headers"][2]).status_code == 403
    assert (
        c.get(f"/candidate/applications/{uuid.uuid4()}", headers=h).status_code == 404
    )
    assert c.patch(detail, headers=h, json={"status": "Accepted"}).status_code == 405
    assert (
        c.post(
            f"/candidate/jobs/{flow['jobs'][-1]}/applications",
            headers=h,
        ).status_code
        == 404
    )
    assert len(c.get("/candidate/applications", headers=h).json()) == 2
    assert len(c.get("/candidate/applications", headers=flow["headers"][1]).json()) == 1


def test_booking_conflict_visibility_and_status_retention(flow):
    c, h = flow["client"], flow["headers"]
    path = f"/candidate/applications/{flow['applications'][0]}"
    slot = str(flow["slots"][0])
    assert [r["id"] for r in c.get(path + "/slots", headers=h[0]).json()] == [slot]
    assert (
        c.post(path + "/booking", headers=h[1], json={"slot_id": slot}).status_code
        == 403
    )
    assert (
        c.post(
            path + "/booking",
            headers=h[0],
            json={"slot_id": str(flow["slots"][1])},
        ).status_code
        == 403
    )
    assert (
        c.post(
            path + "/booking",
            headers=h[0],
            json={"slot_id": str(flow["slots"][2])},
        ).status_code
        == 409
    )
    assert (
        c.post(path + "/booking", headers=h[0], json={"slot_id": slot}).status_code
        == 201
    )
    second = f"/candidate/applications/{flow['applications'][1]}"
    conflict = c.post(second + "/booking", headers=h[1], json={"slot_id": slot})
    assert (
        conflict.status_code == 409
        # and 表示还必须同时满足这一条条件
        and conflict.json()["detail"] == "Slot already booked"
    )
    assert c.get(second + "/slots", headers=h[1]).json() == []
    with Session(flow["engine"]) as s:
        assert len(s.exec(select(Booking)).all()) == 1
        app = s.get(Application, flow["applications"][0])
        app.status = ApplicationStatus.Rejected
        # 把对象加入数据库工作区；这一行本身还不等于提交成功
        s.add(app)
        # 提交整个事务；成功后数据库中的修改才正式生效
        s.commit()
    assert c.get(path, headers=h[0]).json()["booking"]["slot_id"] == slot
    assert c.get(second + "/slots", headers=h[1]).json() == []


def test_sql_metacharacters_are_bound_values(flow):
    c = flow["client"]
    login = c.post(
        "/users/login",
        # 请求的 JSON 正文，不是直接修改数据库
        json={"email": "x' OR '1'='1@example.com", "password": "demo-password"},
    )
    assert login.status_code in (401, 422)
    from app.users.service import get_user_by_email

    from sqlalchemy import event

    captured = []

    # 监听数据库事件，让下面函数在对应事件发生时执行
    @event.listens_for(flow["engine"], "before_cursor_execute")
    def capture(conn, cursor, statement, parameters, context, executemany):
        captured.append((statement, parameters))

    malicious = "' OR 1=1; DROP TABLE user;--"
    with Session(flow["engine"]) as s:
        assert get_user_by_email(s, malicious) is None
        assert len(s.exec(select(User)).all()) == 4
    statement, parameters = next((q, p) for q, p in captured if malicious in p)
    assert malicious not in statement and malicious in parameters


def test_booking_pending_existing_missing_and_failed_commit(flow, monkeypatch):
    from app.candidate.service import book

    c, h = flow["client"], flow["headers"][0]
    pending = c.post(
        f"/candidate/jobs/{flow['jobs'][1]}/applications",
        headers=h,
    ).json()
    payload = {"slot_id": str(flow["slots"][0])}
    assert (
        c.post(
            f"/candidate/applications/{pending['id']}/booking",
            headers=h,
            json=payload,
        ).status_code
        == 409
    )
    path = f"/candidate/applications/{flow['applications'][0]}/booking"
    assert c.post(path, json=payload).status_code == 401
    assert c.post(path, headers=flow["headers"][2], json=payload).status_code == 403
    assert (
        c.post(path, headers=h, json={"slot_id": str(uuid.uuid4())}).status_code == 404
    )
    with Session(flow["engine"]) as s:
        user = s.get(User, flow["ids"][0])

        def fail():
            s.flush()
            raise SQLAlchemyError("failed commit")

        # 暂时替换方法以模拟失败，测试结束后由 monkeypatch 恢复
        monkeypatch.setattr(s, "commit", fail)
        with pytest.raises(SQLAlchemyError):
            # 在数据库事务内先锁申请再锁时段，重新校验资格，确保并发竞争只有一人成功
            book(s, user, flow["applications"][0], flow["slots"][0])
    with Session(flow["engine"]) as s:
        assert s.exec(select(Booking)).all() == []
    assert c.post(path, headers=h, json=payload).status_code == 201
    assert (
        c.post(path, headers=h, json=payload).json()["detail"]
        == "Application already booked"
    )


def test_employer_uses_shared_score_and_sees_booking_without_resume(flow):
    c, headers = flow["client"], flow["headers"]
    # 用测试客户端发送真实接口请求，经过路由、权限和业务服务
    c.post(
        f"/candidate/applications/{flow['applications'][0]}/booking",
        # 带上测试账户的认证请求头，使请求以指定身份执行
        headers=headers[0],
        # 请求的 JSON 正文，不是直接修改数据库
        json={"slot_id": str(flow["slots"][0])},
    )
    path = f"/employer/jobs/{flow['jobs'][0]}/applications"
    assert c.get(path, headers=headers[0]).status_code == 403
    assert c.get(path, headers=headers[3]).status_code == 403
    rows = c.get(path, headers=headers[2]).json()
    assert [r["score"] for r in rows] == [0, 0]
    assert all(r["score_kind"] == "placeholder" for r in rows)
    assert rows[0]["booking"]["slot_id"] == str(flow["slots"][0])
    assert "resume_text" not in str(rows) and "hashed_password" not in str(rows)
