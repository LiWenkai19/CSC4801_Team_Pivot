"""FP-EMP-1 公司资料：创建、读取、修改与权限边界。"""

import uuid

from sqlmodel import select

from app.employer import adapters
from app.employer.model import EmployerCompany


def test_fp_emp_1_create_company_links_employer(client, db, make_employer):
    """创建公司自动成为成员，company 与 employer_company 一一对应。"""
    headers = make_employer(email="owner@example.com", company_name="Acme")
    me = client.get("/users/me", headers=headers).json()

    company = db.exec(select(adapters.Company)).one()
    membership = db.exec(select(EmployerCompany)).one()
    assert company.name == "Acme"
    assert company.description == "We build software."
    assert membership.employer_id == uuid.UUID(me["id"])
    assert membership.company_id == company.id

    response = client.get("/employer/company", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Acme"


def test_fp_emp_1_create_company_requires_profile_and_once(client, db, make_employer):
    """缺少雇主资料返回 409；重复创建返回 409 且公司数量不变。"""
    without_profile = make_employer(profile=False, company=False)
    missing = client.post(
        "/employer/company", json={"name": "No profile"}, headers=without_profile
    )
    assert missing.status_code == 409
    assert missing.json()["detail"] == "Employer profile required"
    assert db.exec(select(adapters.Company)).all() == []

    headers = make_employer(email="once@example.com", company_name="First")
    duplicate = client.post(
        "/employer/company", json={"name": "Second"}, headers=headers
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Company already linked"
    companies = db.exec(select(adapters.Company)).all()
    assert len(companies) == 1
    assert companies[0].name == "First"


def test_fp_emp_1_get_and_patch_company(client, db, make_employer):
    """GET 返回所建内容；PATCH 只改传入字段，{} 原样返回。"""
    headers = make_employer(company_name="Original")
    created = client.get("/employer/company", headers=headers)
    assert created.status_code == 200
    assert created.json()["name"] == "Original"
    assert created.json()["description"] == "We build software."
    assert set(created.json()) == {
        "id",
        "name",
        "description",
        "created_at",
        "updated_at",
    }

    patched = client.patch(
        "/employer/company", json={"description": "New text"}, headers=headers
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Original"
    assert patched.json()["description"] == "New text"

    unchanged = client.patch("/employer/company", json={}, headers=headers)
    assert unchanged.status_code == 200
    assert unchanged.json() == patched.json()

    db.expire_all()
    saved = db.exec(select(adapters.Company)).one()
    assert saved.name == "Original"
    assert saved.description == "New text"


def test_fp_emp_1_patch_rejects_blank_null_extra(client, db, make_employer):
    """空白名称、显式 null 与多余字段都返回 422，数据库不变。"""
    headers = make_employer(company_name="Stable")
    for payload in (
        {"name": "   "},
        {"description": None},
        {"id": str(uuid.uuid4())},
    ):
        response = client.patch("/employer/company", json=payload, headers=headers)
        assert response.status_code == 422, payload

    db.expire_all()
    saved = db.exec(select(adapters.Company)).one()
    assert saved.name == "Stable"
    assert saved.description == "We build software."


def test_fp_emp_1_company_auth_outcomes(client, make_candidate, make_employer):
    """无 Token 401，候选人 403，未关联公司的雇主 404。"""
    assert client.get("/employer/company").status_code == 401

    candidate = make_candidate()
    forbidden = client.get("/employer/company", headers=candidate)
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Employer role required"

    unlinked = make_employer(email="unlinked@example.com", company=False)
    missing = client.get("/employer/company", headers=unlinked)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Company not found"


def test_fp_emp_1_patch_only_affects_own_company(client, db, make_employer):
    """雇主 A 修改公司后，雇主 B 的公司保持不变。"""
    first = make_employer(email="a@example.com", company_name="Company A")
    second = make_employer(email="b@example.com", company_name="Company B")

    response = client.patch(
        "/employer/company", json={"name": "Company A2"}, headers=first
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Company A2"

    other = client.get("/employer/company", headers=second)
    assert other.status_code == 200
    assert other.json()["name"] == "Company B"

    db.expire_all()
    names = sorted(company.name for company in db.exec(select(adapters.Company)))
    assert names == ["Company A2", "Company B"]
