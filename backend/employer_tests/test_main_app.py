"""合并后的 app.main:app 入口：雇主完整流程可用。"""

from fastapi.testclient import TestClient
from sqlmodel import Session


def test_main_app_employer_flow(migrated_engine):
    """注册雇主 -> 填写资料 -> 创建公司 -> 发布职位 -> 软删除。"""
    from app.db.session import get_db
    from app.main import app

    def test_db():
        with Session(migrated_engine) as session:
            yield session

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as client:
            registered = client.post(
                "/users/register",
                json={"email": "main-flow@example.com", "password": "demo-password", "role": "employer"},
            )
            assert registered.status_code == 200, registered.text
            headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

            profile = client.post("/users/employer/profile", json={"company_name": "Main Co"}, headers=headers)
            assert profile.status_code == 201, profile.text

            company = client.post("/employer/company", json={"name": "Main Co"}, headers=headers)
            assert company.status_code == 201, company.text

            job = client.post(
                "/employer/jobs",
                json={"title": "Engineer", "description": "Build.", "required_skills": ["Python"]},
                headers=headers,
            )
            assert job.status_code == 201, job.text
            assert job.json()["required_skills"] == ["python"]

            removed = client.delete(f"/employer/jobs/{job.json()['id']}", headers=headers)
            assert removed.status_code == 204
            assert client.get(f"/employer/jobs/{job.json()['id']}", headers=headers).status_code == 404
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
