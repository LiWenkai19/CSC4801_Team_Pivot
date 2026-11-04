"""FP-EMP-1 公司资料：查看、编辑、校验与权限边界。"""


def test_fp_emp_1_view_and_edit_company_profile(client, make_employer):
    """雇主可查看并局部编辑公司资料；省略字段保持原值。"""
    headers = make_employer(company_name="Acme", description="We build tools.")
    viewed = client.get("/employer/company", headers=headers)
    assert viewed.status_code == 200
    assert viewed.json() == {
        "user_id": viewed.json()["user_id"],
        "company_name": "Acme",
        "company_description": "We build tools.",
    }

    renamed = client.patch(
        "/employer/company", json={"company_name": "Acme 2"}, headers=headers
    )
    assert renamed.status_code == 200
    body = renamed.json()
    assert body["company_name"] == "Acme 2"
    assert body["company_description"] == "We build tools."

    rewritten = client.patch(
        "/employer/company",
        json={"company_description": ""},
        headers=headers,
    )
    assert rewritten.status_code == 200
    assert rewritten.json()["company_name"] == "Acme 2"
    assert rewritten.json()["company_description"] == ""


def test_fp_emp_1_company_profile_validation(client, make_employer):
    """空白名称、显式 null、未声明字段都 422 且不写入。"""
    headers = make_employer(company_name="Acme")
    invalid_payloads = [
        {"company_name": "   "},
        {"company_name": None},
        {"company_description": None},
        {"unknown_field": "x"},
    ]
    for payload in invalid_payloads:
        response = client.patch("/employer/company", json=payload, headers=headers)
        assert response.status_code == 422, payload
    unchanged = client.get("/employer/company", headers=headers).json()
    assert unchanged["company_name"] == "Acme"


def test_fp_emp_1_missing_profile_returns_404(client, register):
    """已认证雇主未填写资料时查看返回 404。"""
    headers = register("noprofile@example.com", "employer")
    response = client.get("/employer/company", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Company not found"


def test_fp_emp_1_role_and_auth_boundaries(client, register, make_candidate):
    """候选人 403、未登录 401；两者都不能读写公司资料。"""
    candidate = make_candidate()
    assert client.get("/employer/company", headers=candidate).status_code == 403
    patched = client.patch(
        "/employer/company", json={"company_name": "X"}, headers=candidate
    )
    assert patched.status_code == 403

    anonymous_get = client.get("/employer/company")
    assert anonymous_get.status_code == 401
    anonymous_patch = client.patch("/employer/company", json={"company_name": "X"})
    assert anonymous_patch.status_code == 401
