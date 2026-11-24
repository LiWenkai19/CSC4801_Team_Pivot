"""公司资料与申请状态的修前复现及版本保护合同。"""

import pytest


@pytest.mark.parametrize("target", ["company", "application"])
def test_stale_company_or_status_tab_cannot_overwrite_newer_save(
    client, account, job, target
):
    employer, _ = account("employer")
    candidate, _ = account()
    posting = job(employer)
    applied = client.post(
        f"/candidate/jobs/{posting['id']}/applications", headers=candidate
    )
    assert applied.status_code == 201
    application_id = applied.json()["application_id"]
    if target == "company":
        path = "/employer/company"

        def read():
            return client.get(path, headers=employer).json()

        first, stale = (
            {"company_name": "New company A"},
            {"company_name": "Stale company B"},
        )
    else:
        path = f"/employer/applications/{application_id}/status"

        def read():
            return client.get(
                f"/employer/jobs/{posting['id']}/applications", headers=employer
            ).json()[0]

        first, stale = {"status": "Interviewing"}, {"status": "Rejected"}
    initial = read()
    # 同一测试兼容修前无版本响应以保存红证据；修后显式复用同一旧版本，绝不为第二次保存刷新版本。
    version = {"version": initial["version"]} if "version" in initial else {}
    saved = client.patch(path, headers=employer, json={**version, **first})
    assert saved.status_code == 200
    before_stale = read()
    refused = client.patch(path, headers=employer, json={**version, **stale})
    assert refused.status_code == 409
    assert refused.json() == {"detail": "Resource version conflict"}
    assert read() == before_stale


@pytest.fixture(params=["company", "application"])
def editor(request, client, account, job):
    owner, owner_id = account("employer")
    candidate, _ = account()
    posting = job(owner)
    applied = client.post(
        f"/candidate/jobs/{posting['id']}/applications", headers=candidate
    ).json()
    is_company = request.param == "company"
    read_path = (
        "/employer/company"
        if is_company
        else f"/employer/jobs/{posting['id']}/applications"
    )
    path = (
        read_path
        if is_company
        else f"/employer/applications/{applied['application_id']}/status"
    )

    def read():
        response = client.get(read_path, headers=owner)
        assert response.status_code == 200
        return response.json() if is_company else response.json()[0]

    initial = read()
    assert initial["version"] == applied["version"] == 1
    return dict(
        kind=request.param,
        path=path,
        read=read,
        initial=initial,
        owner=owner,
        owner_id=owner_id,
        candidate=candidate,
        application_id=applied["application_id"],
        field="company_description" if is_company else "status",
        values=["First", "Second", ""]
        if is_company
        else ["Accepted", "Rejected", "Interviewing"],
    )


@pytest.mark.parametrize("version", [None, 0, -1, True, False, "1", 1.5, "missing"])
def test_extended_invalid_versions_cannot_write(client, editor, version):
    r = editor
    payload = {r["field"]: r["values"][0]}
    if version != "missing":
        payload["version"] = version
    response = client.patch(r["path"], headers=r["owner"], json=payload)
    assert response.status_code == 422
    assert any(e["loc"] == ["body", "version"] for e in response.json()["detail"])
    assert r["read"]() == r["initial"]


@pytest.mark.parametrize("count", [2, 3])
def test_extended_concurrent_edit_has_one_winner(client, editor, count):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi.testclient import TestClient
    from app.main import app

    r = editor
    frozen_version = r["initial"]["version"]
    barrier = Barrier(count)

    def save(value):
        with TestClient(app) as local:
            barrier.wait(timeout=10)
            return local.patch(
                r["path"],
                headers=r["owner"],
                json={"version": frozen_version, r["field"]: value},
            )

    with ThreadPoolExecutor(max_workers=count) as pool:
        futures = [pool.submit(save, value) for value in r["values"][:count]]
        responses = [future.result(timeout=20) for future in futures]
    assert sorted(response.status_code for response in responses) == [200] + [409] * (
        count - 1
    )
    winner = next(
        response.json() for response in responses if response.status_code == 200
    )
    final = r["read"]()
    assert final["version"] == frozen_version + 1
    assert final[r["field"]] == winner[r["field"]]
    for response in responses:
        if response.status_code == 409:
            assert response.json() == {"detail": "Resource version conflict"}


def test_extended_same_value_and_omission_revision_rules(client, editor):
    r = editor
    only_version = client.patch(r["path"], headers=r["owner"], json={"version": 1})
    assert only_version.status_code == (200 if r["kind"] == "company" else 422)
    assert r["read"]() == r["initial"]
    for version in (1, 2):
        saved = client.patch(
            r["path"],
            headers=r["owner"],
            json={"version": version, r["field"]: r["initial"][r["field"]]},
        )
        assert saved.status_code == 200 and saved.json()["version"] == version + 1
    if r["kind"] == "company":
        saved = client.patch(
            r["path"],
            headers=r["owner"],
            json={"version": 3, "company_description": ""},
        )
        assert saved.status_code == 200 and saved.json()["version"] == 4
        assert saved.json()["company_name"] == r["initial"]["company_name"]
        assert saved.json()["company_description"] == ""


def test_extended_authorization_and_missing_precede_conflict(client, editor, account):
    import uuid

    r = editor
    payload = {"version": 999, r["field"]: r["values"][0]}
    assert client.patch(r["path"], json=payload).status_code == 401
    assert (
        client.patch(r["path"], headers=r["candidate"], json=payload).status_code == 403
    )
    if r["kind"] == "company":
        incomplete, _ = account("employer", complete=False)
        assert (
            client.patch(r["path"], headers=incomplete, json=payload).status_code == 404
        )
    else:
        other, _ = account("employer")
        assert client.patch(r["path"], headers=other, json=payload).status_code == 403
        assert (
            client.patch(
                f"/employer/applications/{uuid.uuid4()}/status",
                headers=r["owner"],
                json=payload,
            ).status_code
            == 404
        )
    assert r["read"]() == r["initial"]


def call_service(db, r, version, value):
    import uuid
    from app.employer import service
    from app.employer.schema import CompanyUpdate, ApplicationStatusUpdate
    from app.users.model import User

    user = db.get(User, r["owner_id"])
    if r["kind"] == "company":
        return service.update_my_company(
            db, user, CompanyUpdate(version=version, company_description=value)
        )
    return service.change_application_status(
        db,
        user,
        uuid.UUID(r["application_id"]),
        ApplicationStatusUpdate(version=version, status=value),
    )


def test_extended_commit_failure_rolls_back_revision_and_content(
    client, editor, db, monkeypatch
):
    from sqlalchemy.exc import SQLAlchemyError

    r = editor

    def fail():
        db.flush()
        raise SQLAlchemyError("Injected failure after actual flush")

    monkeypatch.setattr(db, "commit", fail)
    with pytest.raises(SQLAlchemyError):
        call_service(db, r, 1, r["values"][0])
    assert r["read"]() == r["initial"]


def test_extended_identity_cache_cannot_hide_new_revision(client, editor, db):
    import uuid
    from app.employer.model import Application
    from app.users.model import EmployerProfile
    from app.employer.service import ResourceVersionConflictError

    r = editor
    cached = db.get(
        EmployerProfile if r["kind"] == "company" else Application,
        r["owner_id"] if r["kind"] == "company" else uuid.UUID(r["application_id"]),
    )
    assert cached.version == 1
    saved = client.patch(
        r["path"], headers=r["owner"], json={"version": 1, r["field"]: r["values"][0]}
    )
    assert saved.status_code == 200 and saved.json()["version"] == 2
    with pytest.raises(ResourceVersionConflictError):
        call_service(db, r, 1, r["values"][1])
    assert r["read"]()[r["field"]] == r["values"][0]
    assert r["read"]()["version"] == 2


def test_extended_response_captured_before_next_commit(client, editor, db, monkeypatch):
    r = editor
    original = db.commit

    def commit_then_other_save():
        original()
        saved = client.patch(
            r["path"],
            headers=r["owner"],
            json={"version": 2, r["field"]: r["values"][1]},
        )
        assert saved.status_code == 200 and saved.json()["version"] == 3

    monkeypatch.setattr(db, "commit", commit_then_other_save)
    saved = call_service(db, r, 1, r["values"][0])
    assert saved.version == 2 and getattr(saved, r["field"]) == r["values"][0]
    assert r["read"]()["version"] == 3


def test_company_creation_cannot_choose_version(client, account):
    headers, _ = account("employer", complete=False)
    response = client.post(
        "/users/employer/profile",
        headers=headers,
        json={"company_name": "No client revision", "version": 99},
    )
    assert response.status_code == 422
    assert client.get("/employer/company", headers=headers).status_code == 404


def test_extended_migration_preserves_old_company_application_and_defaults(engine):
    """只在测试集群中新建随机库，验证 7b -> 8c 升级与降级，不迁移应用数据库。"""
    import uuid
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.exc import IntegrityError
    from app.core.config import settings
    from app.users.model import EmployerProfile
    from app.employer.model import Application

    name = "editor_migration_" + uuid.uuid4().hex[:12]
    admin = create_engine(
        engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    isolated = create_engine(engine.url.set(database=name))
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    original_url = settings.DATABASE_URL
    owner, candidate, job_id, application_id = [uuid.uuid4() for _ in range(4)]
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        settings.DATABASE_URL = engine.url.set(database=name).render_as_string(
            hide_password=False
        )
        command.upgrade(config, "7b2c9d4e6f10")
        with isolated.begin() as c:
            for identifier, role in ((owner, "employer"), (candidate, "candidate")):
                c.execute(
                    text(
                        """INSERT INTO "user"(id,email,hashed_password,role,created_at) VALUES(:id,:email,'synthetic',:role,CURRENT_TIMESTAMP)"""
                    ),
                    dict(
                        id=identifier, email=str(identifier) + "@example.com", role=role
                    ),
                )
            c.execute(
                text(
                    "INSERT INTO employer_profile(user_id,company_name,company_description) VALUES(:id,'Preserved company','Preserved description')"
                ),
                dict(id=owner),
            )
            c.execute(
                text(
                    "INSERT INTO candidate_profile(user_id,display_name,resume_text) VALUES(:id,'Candidate','Private')"
                ),
                dict(id=candidate),
            )
            c.execute(
                text(
                    "INSERT INTO job(id,employer_id,title,description,is_deleted,created_at,updated_at) VALUES(:id,:owner,'Job','Details',false,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
                ),
                dict(id=job_id, owner=owner),
            )
            c.execute(
                text(
                    "INSERT INTO application(id,candidate_id,job_id,status,created_at,updated_at) VALUES(:id,:candidate,:job,'Interviewing',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
                ),
                dict(id=application_id, candidate=candidate, job=job_id),
            )
            before = {
                table: c.execute(text(f"SELECT to_jsonb(t) FROM {table} t"))
                .scalars()
                .all()
                for table in ("employer_profile", "application")
            }
        command.upgrade(config, "head")
        with isolated.connect() as c:
            for table, model in (
                ("employer_profile", EmployerProfile),
                ("application", Application),
            ):
                rows = (
                    c.execute(text(f"SELECT to_jsonb(t) FROM {table} t"))
                    .scalars()
                    .all()
                )
                assert rows == [dict(row, version=1) for row in before[table]]
                column = next(
                    col
                    for col in inspect(c).get_columns(table)
                    if col["name"] == "version"
                )
                assert (
                    column["nullable"] is False
                    and str(column["default"]).strip("()' ") == "1"
                )
                assert model.model_fields["version"].default == 1
                assert str(model.__table__.c.version.server_default.arg) == "1"
                assert any(
                    "version > 0" in item["sqltext"]
                    for item in inspect(c).get_check_constraints(table)
                )
        for table in ("employer_profile", "application"):
            for value in (0, -1, None):
                with pytest.raises(IntegrityError):
                    with isolated.begin() as c:
                        c.execute(
                            text(f"UPDATE {table} SET version=:value"),
                            dict(value=value),
                        )
        # Existing rows gain 1; new raw SQL inserts also receive 1 without using ORM defaults.
        with isolated.begin() as c:
            second = uuid.uuid4()
            c.execute(
                text(
                    """INSERT INTO "user"(id,email,hashed_password,role,created_at) VALUES(:id,:email,'synthetic','employer',CURRENT_TIMESTAMP)"""
                ),
                dict(id=second, email=str(second) + "@example.com"),
            )
            assert (
                c.execute(
                    text(
                        "INSERT INTO employer_profile(user_id,company_name,company_description) VALUES(:id,'New','') RETURNING version"
                    ),
                    dict(id=second),
                ).scalar_one()
                == 1
            )
            other_job = uuid.uuid4()
            c.execute(
                text(
                    "INSERT INTO job(id,employer_id,title,description,is_deleted,created_at,updated_at) VALUES(:id,:owner,'Other','Details',false,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
                ),
                dict(id=other_job, owner=owner),
            )
            assert (
                c.execute(
                    text(
                        "INSERT INTO application(id,candidate_id,job_id,status,created_at,updated_at) VALUES(:id,:candidate,:job,'Pending',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP) RETURNING version"
                    ),
                    dict(id=uuid.uuid4(), candidate=candidate, job=other_job),
                ).scalar_one()
                == 1
            )
        command.downgrade(config, "7b2c9d4e6f10")
        command.upgrade(config, "head")
        with isolated.connect() as c:
            assert (
                c.execute(
                    text("SELECT count(*) FROM employer_profile WHERE version=1")
                ).scalar_one()
                == 2
            )
            assert (
                c.execute(
                    text("SELECT count(*) FROM application WHERE version=1")
                ).scalar_one()
                == 2
            )
    finally:
        settings.DATABASE_URL = original_url
        isolated.dispose()
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
