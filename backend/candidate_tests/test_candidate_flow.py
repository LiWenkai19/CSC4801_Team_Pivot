# 【自动测试】fixture 准备隔离环境，客户端调用真实接口，assert 校验结果；测试不依赖生产数据库。
# 阅读提示：缩进表示代码属于哪个分支；= 保存值，== 比较值；None 表示缺失；类型注解不等于数据库操作。
# 导入 uuid，供后续代码调用；导入不是发起 HTTP 请求
import uuid

# 导入 pytest，供后续代码调用；导入不是发起 HTTP 请求
import pytest

# 导入 sqlalchemy.exc 中的 SQLAlchemyError，供后续代码调用；导入不是发起 HTTP 请求
from sqlalchemy.exc import SQLAlchemyError

# 导入 sqlmodel 中的 Session、select，供后续代码调用；导入不是发起 HTTP 请求
from sqlmodel import Session, select

# 导入 app.candidate.model 中的 Application、ApplicationStatus、Booking，供后续代码调用；导入不是发起 HTTP 请求
from app.candidate.model import Application, ApplicationStatus, Booking

# 导入 app.matching 中的 applicant_sort_key、job_sort_key、match_score，供后续代码调用；导入不是发起 HTTP 请求
from app.matching import applicant_sort_key, job_sort_key, match_score

# 导入 app.users.model 中的 CandidateProfile、User，供后续代码调用；导入不是发起 HTTP 请求
from app.users.model import CandidateProfile, User

# 导入 app.users.schema 中的 CandidateProfileUpdate，供后续代码调用；导入不是发起 HTTP 请求
from app.candidate.profile_schema import CandidateProfileUpdate


# 函数 test_password_hash_is_salted_and_verified()：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_password_hash_is_salted_and_verified():
    # 导入 app.users.security 中的 hash_password、verify_password，供后续代码调用；导入不是发起 HTTP 请求
    from app.users.security import hash_password, verify_password

    # 将结果保存在 first：使用 Argon2 的随机盐生成密码哈希，不能用普通 SHA-256 代替
    first = hash_password("demo-password")
    # 将结果保存在 second：使用 Argon2 的随机盐生成密码哈希，不能用普通 SHA-256 代替
    second = hash_password("demo-password")
    # assert 检查测试预期：组合多个判断；and 要全部成立，or 只需其中一个成立；不成立则测试失败
    assert first != second and first != "demo-password"
    # assert 检查测试预期：调用 first.startswith（参数见括号），取得结果或执行相应操作；不成立则测试失败
    assert first.startswith("$argon2")
    # assert 检查测试预期：用密码库核对原始密码是否对应保存的哈希，不解密哈希；不成立则测试失败
    assert verify_password("demo-password", first)
    # assert 检查测试预期：根据 not verify_password('wrong', first) 取得本步所需的值；不成立则测试失败
    assert not verify_password("wrong", first)


# 函数 test_profile_persistence_omission_and_clearing(flow)：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_profile_persistence_omission_and_clearing(flow):
    # 将结果保存在 (c, h)：组装元组；用于多个排序依据时，从左向右依次比较
    c, h = flow["client"], flow["headers"][0]
    # 将结果保存在 path：根据 f'/users/candidates/{flow['ids'][0]}/profile' 取得本步所需的值
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    # assert 检查测试预期：比较 c.get(path, headers=h).json()['resume_text'] == 'Private\nResume'；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.get(path, headers=h).json()["resume_text"] == "Private\nResume"
    # 将结果保存在 接口返回的 HTTP 响应：用测试客户端发送真实接口请求，经过路由、权限和业务服务
    response = c.patch(
        # 继续完成上面的多行语句：将结果保存在 接口返回的 HTTP 响应：用测试客户端发送真实接口请求，经过路由、权限和业务服务
        path,
        # 带上测试账户的认证请求头，使请求以指定身份执行
        headers=h,
        # 请求的 JSON 正文，不是直接修改数据库
        json={"skills": [" SQL ", "Python", "sql", ""], "display_name": " New "},
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # assert 检查测试预期：比较 response.status_code == 200；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert response.status_code == 200
    # assert 检查测试预期：比较 response.json()['skills'] == ['python', 'sql']；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert response.json()["skills"] == ["python", "sql"]
    # assert 检查测试预期：比较 response.json()['display_name'] == 'New'；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert response.json()["display_name"] == "New"
    # assert 检查测试预期：比较 response.json()['resume_text'] == 'Private\nResume'；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert response.json()["resume_text"] == "Private\nResume"
    # assert 检查测试预期：比较 c.patch(path, headers=h, json={'skills': ['Rust']}).json()['skills'] == ['rust']；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.patch(path, headers=h, json={"skills": ["Rust"]}).json()["skills"] == [
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "rust"
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    ]
    # assert 检查测试预期：比较 c.patch(path, headers=h, json={'resume_text': '', 'skills': []}).status_code == 200；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert (
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.patch(path, headers=h, json={'resume_text': '', 'skills': []}).status_code == 200；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        c.patch(path, headers=h, json={"resume_text": "", "skills": []}).status_code
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.patch(path, headers=h, json={'resume_text': '', 'skills': []}).status_code == 200；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        == 200
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # assert 检查测试预期：比较 c.get(path, headers=h).json()['skills'] == []；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.get(path, headers=h).json()["skills"] == []
    # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
    with Session(flow["engine"]) as s:
        # assert 检查测试预期：比较 s.get(CandidateProfile, flow['ids'][0]).resume_text == ''；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        assert s.get(CandidateProfile, flow["ids"][0]).resume_text == ""


# 让相同测试用下面各组输入分别运行，覆盖不同边界
@pytest.mark.parametrize(
    # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
    "payload",
    [
        {"display_name": "  "},
        {"skills": [1]},
        {"resume_text": None},
        {"skills": None},
        {"role": "employer"},
        {"user_id": "injected"},
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    ],
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)
# 函数 test_profile_invalid_request_is_atomic(flow, payload)：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_profile_invalid_request_is_atomic(flow, payload):
    # 将结果保存在 c：用方括号从 flow 取指定字段/元素
    c = flow["client"]
    # 将结果保存在 path：根据 f'/users/candidates/{flow['ids'][0]}/profile' 取得本步所需的值
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    # assert 检查测试预期：比较 c.patch(path, headers=flow['headers'][0], json=payload).status_code == 422；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.patch(path, headers=flow["headers"][0], json=payload).status_code == 422
    # assert 检查测试预期：比较 c.get(path, headers=flow['headers'][0]).json()['resume_text'] == 'Private\nResume'；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert (
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.get(path, headers=flow['headers'][0]).json()['resume_text'] == 'Private\nResume'；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        c.get(path, headers=flow["headers"][0]).json()["resume_text"]
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.get(path, headers=flow['headers'][0]).json()['resume_text'] == 'Private\nResume'；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        == "Private\nResume"
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# 让相同测试用下面各组输入分别运行，覆盖不同边界
@pytest.mark.parametrize("method", ["get", "patch"])
# 函数 test_private_profile_authorization_and_missing(flow, method)：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_private_profile_authorization_and_missing(flow, method):
    # 将结果保存在 c：用方括号从 flow 取指定字段/元素
    c = flow["client"]
    # 将结果保存在 path：根据 f'/users/candidates/{flow['ids'][0]}/profile' 取得本步所需的值
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    # 将结果保存在 kwargs：条件成立取 if 前的值，否则取 else 后的值
    kwargs = {"json": {"resume_text": "stolen"}} if method == "patch" else {}
    # 将结果保存在 call：调用 getattr（参数见括号），取得结果或执行相应操作
    call = getattr(c, method)
    # assert 检查测试预期：比较 call(path, **kwargs).status_code == 401；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert call(path, **kwargs).status_code == 401
    # for 循环：依次从 flow['headers'][1:] 取出元素，保存在 h 后处理
    forbidden = flow["headers"][1:2] if method == "get" else flow["headers"][1:]
    for h in forbidden:
        # assert 检查测试预期：比较 call(path, headers=h, **kwargs).status_code == 403；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        assert call(path, headers=h, **kwargs).status_code == 403
    # 将结果保存在 registered：把 HTTP 响应正文解析为可供断言的字典/列表
    registered = c.post(
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "/users/register",
        # 请求的 JSON 正文，不是直接修改数据库
        json={"email": "missing@example.com", "password": "demo", "role": "candidate"},
        # 继续完成上面的多行语句：将结果保存在 registered：把 HTTP 响应正文解析为可供断言的字典/列表
    ).json()
    # 将结果保存在 missing_id：用方括号从 registered['user'] 取指定字段/元素
    missing_id = registered["user"]["id"]
    # 将结果保存在 missing_headers：组装键值字典，字段名对应要发送/返回的数据
    missing_headers = {"Authorization": f"Bearer {registered['access_token']}"}
    # assert 检查测试预期：比较 call(f'/users/candidates/{missing_id}/profile', headers=missing_headers, **kwargs).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert (
        # 继续完成上面的多行语句：assert 检查测试预期：比较 call(f'/users/candidates/{missing_id}/profile', headers=missing_headers, **kwargs).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        call(
            # 继续完成上面的多行语句：assert 检查测试预期：比较 call(f'/users/candidates/{missing_id}/profile', headers=missing_headers, **kwargs).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
            f"/users/candidates/{missing_id}/profile",
            headers=missing_headers,
            **kwargs,
            # 继续完成上面的多行语句：assert 检查测试预期：比较 call(f'/users/candidates/{missing_id}/profile', headers=missing_headers, **kwargs).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        ).status_code
        # 继续完成上面的多行语句：assert 检查测试预期：比较 call(f'/users/candidates/{missing_id}/profile', headers=missing_headers, **kwargs).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        == 404
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# 函数 test_profile_failed_commit_rolls_back(flow, monkeypatch)：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_profile_failed_commit_rolls_back(flow, monkeypatch):
    # 导入 app.candidate.service 中的 update_profile，供后续代码调用；导入不是发起 HTTP 请求
    from app.candidate.service import update_profile

    # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
    with Session(flow["engine"]) as s:
        # 将结果保存在 已通过认证的账户：用主键查询 User；找不到时得到 None
        user = s.get(User, flow["ids"][0])

        # 函数 fail()：模拟数据库已经写入但提交失败，验证服务能回滚而不留下半份数据。
        def fail():
            # 把暂存修改发给数据库检查约束，但尚未正式提交事务
            s.flush()
            # 抛出失败并立即停止成功路径：SQLAlchemyError('failed commit')
            raise SQLAlchemyError("failed commit")

        # 暂时替换方法以模拟失败，测试结束后由 monkeypatch 恢复
        monkeypatch.setattr(s, "commit", fail)
        # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
        with pytest.raises(SQLAlchemyError):
            # 只修改明确提交的字段，名称/简历/技能一起提交，任何失败都整体回滚
            update_profile(
                # 继续完成上面的多行语句：只修改明确提交的字段，名称/简历/技能一起提交，任何失败都整体回滚
                s,
                # 继续完成上面的多行语句：只修改明确提交的字段，名称/简历/技能一起提交，任何失败都整体回滚
                user,
                # 继续完成上面的多行语句：只修改明确提交的字段，名称/简历/技能一起提交，任何失败都整体回滚
                user.id,
                # 继续完成上面的多行语句：只修改明确提交的字段，名称/简历/技能一起提交，任何失败都整体回滚
                CandidateProfileUpdate(
                    # 这一项指定 候选人显示名称；逗号分隔同一调用/结构中的各个参数或字段
                    display_name="Bad",
                    skills=["rust"],
                    resume_text="bad",
                    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
                ),
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            )
    # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
    with Session(flow["engine"]) as s:
        # 将结果保存在 p：用主键查询 CandidateProfile；找不到时得到 None
        p = s.get(CandidateProfile, flow["ids"][0])
        # assert 检查测试预期：组合多个判断；and 要全部成立，or 只需其中一个成立；不成立则测试失败
        assert p.display_name == "Alice" and p.resume_text == "Private\nResume"
        # assert 检查测试预期：比较 sorted((skill.name for skill in p.skills)) == ['python', 'sql']；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        assert sorted(skill.name for skill in p.skills) == ["python", "sql"]


# 让相同测试用下面各组输入分别运行，覆盖不同边界
@pytest.mark.parametrize(
    # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
    "candidate,required,expected",
    [
        (["Python", "SQL"], ["Python", "SQL"], 100),
        (["Python"], ["Python", "SQL"], 50),
        (["Rust"], ["Python", "SQL"], 0),
        ([], [], 100),
        (["PYTHON", " python ", ""], ["python", "SQL", "rust", "SQL"], 33),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    ],
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)
# 函数 test_matching_examples_normalization_and_floor(candidate, required, expected)：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_matching_examples_normalization_and_floor(candidate, required, expected):
    # assert 检查测试预期：比较 match_score(candidate, required) == expected；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert match_score(candidate, required) == expected


# 函数 test_matching_both_tie_breakers()：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_matching_both_tie_breakers():
    # 将结果保存在 jobs：组装有顺序的列表，方括号内是各个元素
    jobs = [
        # 继续完成上面的多行语句：将结果保存在 jobs：组装有顺序的列表，方括号内是各个元素
        dict(id="b", title="alpha", score=50),
        # 继续完成上面的多行语句：将结果保存在 jobs：组装有顺序的列表，方括号内是各个元素
        dict(id="a", title="ALPHA", score=50),
        # 继续完成上面的多行语句：将结果保存在 jobs：组装有顺序的列表，方括号内是各个元素
        dict(id="c", title="z", score=100),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    ]
    # assert 检查测试预期：比较 [x['id'] for x in sorted(jobs, key=job_sort_key)] == ['c', 'a', 'b']；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert [x["id"] for x in sorted(jobs, key=job_sort_key)] == ["c", "a", "b"]
    # 将结果保存在 people：组装有顺序的列表，方括号内是各个元素
    people = [
        # 继续完成上面的多行语句：将结果保存在 people：组装有顺序的列表，方括号内是各个元素
        dict(candidate_id="b", display_name="Alice", score=50),
        # 继续完成上面的多行语句：将结果保存在 people：组装有顺序的列表，方括号内是各个元素
        dict(candidate_id="a", display_name="alice", score=50),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    ]
    # assert 检查测试预期：比较 [x['candidate_id'] for x in sorted(people, key=applicant_sort_key)] == ['a', 'b']；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert [x["candidate_id"] for x in sorted(people, key=applicant_sort_key)] == [
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "a",
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "b",
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    ]


# 函数 test_jobs_all_active_order_and_live_scores(flow)：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_jobs_all_active_order_and_live_scores(flow):
    # 将结果保存在 (c, h)：组装元组；用于多个排序依据时，从左向右依次比较
    c, h = flow["client"], flow["headers"][0]
    # 将结果保存在 准备返回的记录列表：把 HTTP 响应正文解析为可供断言的字典/列表
    rows = c.get("/candidate/jobs", headers=h).json()
    # assert 检查测试预期：比较 [r['title'] for r in rows] == ['alpha', 'Alpha', 'Beta', 'Empty']；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert [r["title"] for r in rows] == ["alpha", "Alpha", "Beta", "Empty"]
    # assert 检查测试预期：组合多个判断；and 要全部成立，or 只需其中一个成立；不成立则测试失败
    assert len(rows) == 4 and rows[0]["applied"]
    # 将结果保存在 path：根据 f'/users/candidates/{flow['ids'][0]}/profile' 取得本步所需的值
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    # 用测试客户端发送真实接口请求，经过路由、权限和业务服务
    c.patch(path, headers=h, json={"skills": ["Python"]})
    # assert 检查测试预期：比较 c.get('/candidate/jobs', headers=h).json()[0]['title'] == 'Empty'；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.get("/candidate/jobs", headers=h).json()[0]["title"] == "Empty"
    # 将结果保存在 detail：根据 f'/candidate/jobs/{flow['jobs'][0]}' 取得本步所需的值
    detail = f"/candidate/jobs/{flow['jobs'][0]}"
    # assert 检查测试预期：比较 c.get(detail, headers=h).json()['score'] == 50；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.get(detail, headers=h).json()["score"] == 50
    # 用测试客户端发送真实接口请求，经过路由、权限和业务服务
    c.patch(path, headers=h, json={"resume_text": "SQL Rust"})
    # assert 检查测试预期：比较 c.get(detail, headers=h).json()['score'] == 50；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.get(detail, headers=h).json()["score"] == 50
    # assert 检查测试预期：比较 c.get(f'/candidate/jobs/{flow['jobs'][-1]}', headers=h).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.get(f"/candidate/jobs/{flow['jobs'][-1]}", headers=h).status_code == 404


# 函数 test_application_pending_duplicate_and_private(flow)：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_application_pending_duplicate_and_private(flow):
    # 将结果保存在 (c, h)：组装元组；用于多个排序依据时，从左向右依次比较
    c, h = flow["client"], flow["headers"][0]
    # 将结果保存在 path：根据 f'/candidate/jobs/{flow['jobs'][1]}/applications' 取得本步所需的值
    path = f"/candidate/jobs/{flow['jobs'][1]}/applications"
    # assert 检查测试预期：比较 c.post(path, headers=h, json={'status': 'Accepted'}).status_code == 422；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.post(path, headers=h, json={"status": "Accepted"}).status_code == 422
    # 将结果保存在 接口返回的 HTTP 响应：用测试客户端发送真实接口请求，经过路由、权限和业务服务
    response = c.post(path, headers=h, json={})
    # assert 检查测试预期：组合多个判断；and 要全部成立，or 只需其中一个成立；不成立则测试失败
    assert response.status_code == 201 and response.json()["status"] == "Pending"
    # assert 检查测试预期：比较 c.post(path, headers=h).status_code == 409；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.post(path, headers=h).status_code == 409
    # 将结果保存在 detail：根据 f'/candidate/applications/{response.json()['id']}' 取得本步所需的值
    detail = f"/candidate/applications/{response.json()['id']}"
    # assert 检查测试预期：比较 c.get(detail, headers=flow['headers'][1]).status_code == 403；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.get(detail, headers=flow["headers"][1]).status_code == 403
    # assert 检查测试预期：比较 c.get(detail, headers=flow['headers'][2]).status_code == 403；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.get(detail, headers=flow["headers"][2]).status_code == 403
    # assert 检查测试预期：比较 c.get(f'/candidate/applications/{uuid.uuid4()}', headers=h).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert (
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.get(f'/candidate/applications/{uuid.uuid4()}', headers=h).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        c.get(f"/candidate/applications/{uuid.uuid4()}", headers=h).status_code == 404
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # assert 检查测试预期：比较 c.patch(detail, headers=h, json={'status': 'Accepted'}).status_code == 405；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.patch(detail, headers=h, json={"status": "Accepted"}).status_code == 405
    # assert 检查测试预期：比较 c.post(f'/candidate/jobs/{flow['jobs'][-1]}/applications', headers=h).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert (
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(f'/candidate/jobs/{flow['jobs'][-1]}/applications', headers=h).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        c.post(
            # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(f'/candidate/jobs/{flow['jobs'][-1]}/applications', headers=h).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
            f"/candidate/jobs/{flow['jobs'][-1]}/applications",
            headers=h,
            # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(f'/candidate/jobs/{flow['jobs'][-1]}/applications', headers=h).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        ).status_code
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(f'/candidate/jobs/{flow['jobs'][-1]}/applications', headers=h).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        == 404
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # assert 检查测试预期：比较 len(c.get('/candidate/applications', headers=h).json()) == 2；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert len(c.get("/candidate/applications", headers=h).json()) == 2
    # assert 检查测试预期：比较 len(c.get('/candidate/applications', headers=flow['headers'][1]).json()) == 1；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert len(c.get("/candidate/applications", headers=flow["headers"][1]).json()) == 1


# 函数 test_booking_conflict_visibility_and_status_retention(flow)：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_booking_conflict_visibility_and_status_retention(flow):
    # 将结果保存在 (c, h)：组装元组；用于多个排序依据时，从左向右依次比较
    c, h = flow["client"], flow["headers"]
    # 将结果保存在 path：根据 f'/candidate/applications/{flow['applications'][0]}' 取得本步所需的值
    path = f"/candidate/applications/{flow['applications'][0]}"
    # 将结果保存在 面试时段：调用 str（参数见括号），取得结果或执行相应操作
    slot = str(flow["slots"][0])
    # assert 检查测试预期：比较 [r['id'] for r in c.get(path + '/slots', headers=h[0]).json()] == [slot]；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert [r["id"] for r in c.get(path + "/slots", headers=h[0]).json()] == [slot]
    # assert 检查测试预期：比较 c.post(path + '/booking', headers=h[1], json={'slot_id': slot}).status_code == 403；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert (
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path + '/booking', headers=h[1], json={'slot_id': slot}).status_code == 403；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        c.post(path + "/booking", headers=h[1], json={"slot_id": slot}).status_code
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path + '/booking', headers=h[1], json={'slot_id': slot}).status_code == 403；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        == 403
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # assert 检查测试预期：比较 c.post(path + '/booking', headers=h[0], json={'slot_id': str(flow['slots'][1])}).status_code == 403；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert (
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path + '/booking', headers=h[0], json={'slot_id': str(flow['slots'][1])}).status_code == 403；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        c.post(
            # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path + '/booking', headers=h[0], json={'slot_id': str(flow['slots'][1])}).status_code == 403；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
            path + "/booking",
            headers=h[0],
            json={"slot_id": str(flow["slots"][1])},
            # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path + '/booking', headers=h[0], json={'slot_id': str(flow['slots'][1])}).status_code == 403；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        ).status_code
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path + '/booking', headers=h[0], json={'slot_id': str(flow['slots'][1])}).status_code == 403；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        == 403
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # assert 检查测试预期：比较 c.post(path + '/booking', headers=h[0], json={'slot_id': str(flow['slots'][2])}).status_code == 409；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert (
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path + '/booking', headers=h[0], json={'slot_id': str(flow['slots'][2])}).status_code == 409；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        c.post(
            # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path + '/booking', headers=h[0], json={'slot_id': str(flow['slots'][2])}).status_code == 409；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
            path + "/booking",
            headers=h[0],
            json={"slot_id": str(flow["slots"][2])},
            # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path + '/booking', headers=h[0], json={'slot_id': str(flow['slots'][2])}).status_code == 409；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        ).status_code
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path + '/booking', headers=h[0], json={'slot_id': str(flow['slots'][2])}).status_code == 409；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        == 409
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # assert 检查测试预期：比较 c.post(path + '/booking', headers=h[0], json={'slot_id': slot}).status_code == 201；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert (
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path + '/booking', headers=h[0], json={'slot_id': slot}).status_code == 201；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        c.post(path + "/booking", headers=h[0], json={"slot_id": slot}).status_code
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path + '/booking', headers=h[0], json={'slot_id': slot}).status_code == 201；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        == 201
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 将结果保存在 second：根据 f'/candidate/applications/{flow['applications'][1]}' 取得本步所需的值
    second = f"/candidate/applications/{flow['applications'][1]}"
    # 将结果保存在 conflict：用测试客户端发送真实接口请求，经过路由、权限和业务服务
    conflict = c.post(second + "/booking", headers=h[1], json={"slot_id": slot})
    # assert 检查测试预期：组合多个判断；and 要全部成立，or 只需其中一个成立；不成立则测试失败
    assert (
        # 继续完成上面的多行语句：assert 检查测试预期：组合多个判断；and 要全部成立，or 只需其中一个成立；不成立则测试失败
        conflict.status_code == 409
        # and 表示还必须同时满足这一条条件
        and conflict.json()["detail"] == "Slot already booked"
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # assert 检查测试预期：比较 c.get(second + '/slots', headers=h[1]).json() == []；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.get(second + "/slots", headers=h[1]).json() == []
    # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
    with Session(flow["engine"]) as s:
        # assert 检查测试预期：比较 len(s.exec(select(Booking)).all()) == 1；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        assert len(s.exec(select(Booking)).all()) == 1
        # 将结果保存在 app：用主键查询 Application；找不到时得到 None
        app = s.get(Application, flow["applications"][0])
        # 将结果保存在 app.status：读取 ApplicationStatus 的 已拒绝 属性
        app.status = ApplicationStatus.Rejected
        # 把对象加入数据库工作区；这一行本身还不等于提交成功
        s.add(app)
        # 提交整个事务；成功后数据库中的修改才正式生效
        s.commit()
    # assert 检查测试预期：比较 c.get(path, headers=h[0]).json()['booking']['slot_id'] == slot；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.get(path, headers=h[0]).json()["booking"]["slot_id"] == slot
    # assert 检查测试预期：比较 c.get(second + '/slots', headers=h[1]).json() == []；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.get(second + "/slots", headers=h[1]).json() == []


# 函数 test_sql_metacharacters_are_bound_values(flow)：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_sql_metacharacters_are_bound_values(flow):
    # 将结果保存在 c：用方括号从 flow 取指定字段/元素
    c = flow["client"]
    # 将结果保存在 login：用测试客户端发送真实接口请求，经过路由、权限和业务服务
    login = c.post(
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "/users/login",
        # 请求的 JSON 正文，不是直接修改数据库
        json={"email": "x' OR '1'='1@example.com", "password": "demo-password"},
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # assert 检查测试预期：比较 login.status_code in (401, 422)；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert login.status_code in (401, 422)
    # 导入 app.users.service 中的 get_user_by_email，供后续代码调用；导入不是发起 HTTP 请求
    from app.users.service import get_user_by_email

    # 导入 sqlalchemy 中的 event，供后续代码调用；导入不是发起 HTTP 请求
    from sqlalchemy import event

    # 将结果保存在 captured：组装有顺序的列表，方括号内是各个元素
    captured = []

    # 监听数据库事件，让下面函数在对应事件发生时执行
    @event.listens_for(flow["engine"], "before_cursor_execute")
    # 函数 capture(conn, cursor, statement, parameters, context, executemany)：把下面的一组操作封装成可重复调用的步骤。
    def capture(conn, cursor, statement, parameters, context, executemany):
        # 调用 captured.append（参数见括号），取得结果或执行相应操作
        captured.append((statement, parameters))

    # 将结果保存在 malicious：使用固定值 "' OR 1=1; DROP TABLE user;--"
    malicious = "' OR 1=1; DROP TABLE user;--"
    # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
    with Session(flow["engine"]) as s:
        # assert 检查测试预期：比较 get_user_by_email(s, malicious) is None；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        assert get_user_by_email(s, malicious) is None
        # assert 检查测试预期：比较 len(s.exec(select(User)).all()) == 4；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        assert len(s.exec(select(User)).all()) == 4
    # 将结果保存在 (statement, parameters)：调用 next（参数见括号），取得结果或执行相应操作
    statement, parameters = next((q, p) for q, p in captured if malicious in p)
    # assert 检查测试预期：组合多个判断；and 要全部成立，or 只需其中一个成立；不成立则测试失败
    assert malicious not in statement and malicious in parameters


# 函数 test_booking_pending_existing_missing_and_failed_commit(flow, monkeypatch)：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_booking_pending_existing_missing_and_failed_commit(flow, monkeypatch):
    # 导入 app.candidate.service 中的 book，供后续代码调用；导入不是发起 HTTP 请求
    from app.candidate.service import book

    # 将结果保存在 (c, h)：组装元组；用于多个排序依据时，从左向右依次比较
    c, h = flow["client"], flow["headers"][0]
    # 将结果保存在 pending：把 HTTP 响应正文解析为可供断言的字典/列表
    pending = c.post(
        # 继续完成上面的多行语句：将结果保存在 pending：把 HTTP 响应正文解析为可供断言的字典/列表
        f"/candidate/jobs/{flow['jobs'][1]}/applications",
        headers=h,
        # 继续完成上面的多行语句：将结果保存在 pending：把 HTTP 响应正文解析为可供断言的字典/列表
    ).json()
    # 将结果保存在 已经过类型校验的请求内容：组装键值字典，字段名对应要发送/返回的数据
    payload = {"slot_id": str(flow["slots"][0])}
    # assert 检查测试预期：比较 c.post(f'/candidate/applications/{pending['id']}/booking', headers=h, json=payload).status_code == 409；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert (
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(f'/candidate/applications/{pending['id']}/booking', headers=h, json=payload).status_code == 409；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        c.post(
            # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(f'/candidate/applications/{pending['id']}/booking', headers=h, json=payload).status_code == 409；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
            f"/candidate/applications/{pending['id']}/booking",
            headers=h,
            json=payload,
            # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(f'/candidate/applications/{pending['id']}/booking', headers=h, json=payload).status_code == 409；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        ).status_code
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(f'/candidate/applications/{pending['id']}/booking', headers=h, json=payload).status_code == 409；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        == 409
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 将结果保存在 path：根据 f'/candidate/applications/{flow['applications'][0]}/booking' 取得本步所需的值
    path = f"/candidate/applications/{flow['applications'][0]}/booking"
    # assert 检查测试预期：比较 c.post(path, json=payload).status_code == 401；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.post(path, json=payload).status_code == 401
    # assert 检查测试预期：比较 c.post(path, headers=flow['headers'][2], json=payload).status_code == 403；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.post(path, headers=flow["headers"][2], json=payload).status_code == 403
    # assert 检查测试预期：比较 c.post(path, headers=h, json={'slot_id': str(uuid.uuid4())}).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert (
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path, headers=h, json={'slot_id': str(uuid.uuid4())}).status_code == 404；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        c.post(path, headers=h, json={"slot_id": str(uuid.uuid4())}).status_code == 404
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
    with Session(flow["engine"]) as s:
        # 将结果保存在 已通过认证的账户：用主键查询 User；找不到时得到 None
        user = s.get(User, flow["ids"][0])

        # 函数 fail()：模拟数据库已经写入但提交失败，验证服务能回滚而不留下半份数据。
        def fail():
            # 把暂存修改发给数据库检查约束，但尚未正式提交事务
            s.flush()
            # 抛出失败并立即停止成功路径：SQLAlchemyError('failed commit')
            raise SQLAlchemyError("failed commit")

        # 暂时替换方法以模拟失败，测试结束后由 monkeypatch 恢复
        monkeypatch.setattr(s, "commit", fail)
        # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
        with pytest.raises(SQLAlchemyError):
            # 在数据库事务内先锁申请再锁时段，重新校验资格，确保并发竞争只有一人成功
            book(s, user, flow["applications"][0], flow["slots"][0])
    # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
    with Session(flow["engine"]) as s:
        # assert 检查测试预期：比较 s.exec(select(Booking)).all() == []；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        assert s.exec(select(Booking)).all() == []
    # assert 检查测试预期：比较 c.post(path, headers=h, json=payload).status_code == 201；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.post(path, headers=h, json=payload).status_code == 201
    # assert 检查测试预期：比较 c.post(path, headers=h, json=payload).json()['detail'] == 'Application already booked'；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert (
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path, headers=h, json=payload).json()['detail'] == 'Application already booked'；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        c.post(path, headers=h, json=payload).json()["detail"]
        # 继续完成上面的多行语句：assert 检查测试预期：比较 c.post(path, headers=h, json=payload).json()['detail'] == 'Application already booked'；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        == "Application already booked"
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# 函数 test_employer_uses_shared_score_and_sees_booking_without_resume(flow)：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_employer_uses_shared_score_and_sees_booking_without_resume(flow):
    # 将结果保存在 (c, headers)：组装元组；用于多个排序依据时，从左向右依次比较
    c, headers = flow["client"], flow["headers"]
    # 用测试客户端发送真实接口请求，经过路由、权限和业务服务
    c.post(
        # 继续完成上面的多行语句：用测试客户端发送真实接口请求，经过路由、权限和业务服务
        f"/candidate/applications/{flow['applications'][0]}/booking",
        # 带上测试账户的认证请求头，使请求以指定身份执行
        headers=headers[0],
        # 请求的 JSON 正文，不是直接修改数据库
        json={"slot_id": str(flow["slots"][0])},
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 将结果保存在 path：根据 f'/employer/jobs/{flow['jobs'][0]}/applications' 取得本步所需的值
    path = f"/employer/jobs/{flow['jobs'][0]}/applications"
    # assert 检查测试预期：比较 c.get(path, headers=headers[0]).status_code == 403；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.get(path, headers=headers[0]).status_code == 403
    # assert 检查测试预期：比较 c.get(path, headers=headers[3]).status_code == 403；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert c.get(path, headers=headers[3]).status_code == 403
    # 将结果保存在 准备返回的记录列表：把 HTTP 响应正文解析为可供断言的字典/列表
    rows = c.get(path, headers=headers[2]).json()
    # assert 检查测试预期：比较 [r['score'] for r in rows] == [100, 0]；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert [r["score"] for r in rows] == [100, 0]
    # assert 检查测试预期：比较 rows[0]['booking']['slot_id'] == str(flow['slots'][0])；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert rows[0]["booking"]["slot_id"] == str(flow["slots"][0])
    # assert 检查测试预期：组合多个判断；and 要全部成立，or 只需其中一个成立；不成立则测试失败
    assert "resume_text" not in str(rows) and "hashed_password" not in str(rows)
