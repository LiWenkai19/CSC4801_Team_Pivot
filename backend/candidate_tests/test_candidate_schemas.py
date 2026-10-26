# 【自动测试】fixture 准备隔离环境，客户端调用真实接口，assert 校验结果；测试不依赖生产数据库。
# 阅读提示：缩进表示代码属于哪个分支；= 保存值，== 比较值；None 表示缺失；类型注解不等于数据库操作。
# 导入 uuid，供后续代码调用；导入不是发起 HTTP 请求
import uuid

# 导入 pytest，供后续代码调用；导入不是发起 HTTP 请求
import pytest

# 导入 pydantic 中的 ValidationError，供后续代码调用；导入不是发起 HTTP 请求
from pydantic import ValidationError

# 导入 app.users.model 中的 Role、User，供后续代码调用；导入不是发起 HTTP 请求
from app.users.model import Role, User

# 导入 app.users.schema 中的 AuthResponse、CandidateProfileCreate、CandidateProfilePublic、CandidateProfileUpdate、EmployerProfileCreate、UserCreate、UserLogin、UserPublic，供后续代码调用；导入不是发起 HTTP 请求
from app.candidate.profile_schema import (
    # 继续导入 AuthResponse，与上面的 from/import 属于同一语句
    AuthResponse,
    # 继续导入 CandidateProfileCreate，与上面的 from/import 属于同一语句
    CandidateProfileCreate,
    # 继续导入 CandidateProfilePublic，与上面的 from/import 属于同一语句
    CandidateProfilePublic,
    # 继续导入 CandidateProfileUpdate，与上面的 from/import 属于同一语句
    CandidateProfileUpdate,
    # 继续导入 EmployerProfileCreate，与上面的 from/import 属于同一语句
    EmployerProfileCreate,
    # 继续导入 UserCreate，与上面的 from/import 属于同一语句
    UserCreate,
    # 继续导入 UserLogin，与上面的 from/import 属于同一语句
    UserLogin,
    # 继续导入 UserPublic，与上面的 from/import 属于同一语句
    UserPublic,
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)


# 函数 test_signup_only_requires_account_fields()：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_signup_only_requires_account_fields():
    """两种角色注册时都不需要提交基本资料。"""
    # for 循环：依次从 Role 取出元素，保存在 role 后处理
    for role in Role:
        # 将结果保存在 request：调用 UserCreate（参数见括号），取得结果或执行相应操作
        request = UserCreate(email="demo@example.com", password="password", role=role)
        # assert 检查测试预期：比较 set(request.model_dump()) == {'email', 'password', 'role'}；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        assert set(request.model_dump()) == {"email", "password", "role"}
        # assert 检查测试预期：比较 request.role is role；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        assert request.role is role


# 让相同测试用下面各组输入分别运行，覆盖不同边界
@pytest.mark.parametrize(
    # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
    "changes",
    [
        {"email": "invalid-email"},
        {"password": ""},
        {"role": "admin"},
        {"resume_text": "private"},
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    ],
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)
# 函数 test_signup_rejects_invalid_or_extra_fields(changes)：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_signup_rejects_invalid_or_extra_fields(changes):
    """注册拒绝无效账户字段及不属于注册步骤的资料。"""
    # 将结果保存在 已经过类型校验的请求内容：组装键值字典，字段名对应要发送/返回的数据
    payload = {"email": "demo@example.com", "password": "password", "role": "candidate"}
    # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
    with pytest.raises(ValidationError):
        # 按 schema 校验/提取字段，避免返回未声明的内部数据
        UserCreate.model_validate(payload | changes)


# 函数 test_login_preserves_password_and_remember_me_default()：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_login_preserves_password_and_remember_me_default():
    """登录不裁剪密码，并保留已有记住登录的默认值。"""
    # 将结果保存在 request：调用 UserLogin（参数见括号），取得结果或执行相应操作
    request = UserLogin(email="demo@example.com", password=" password ")
    # assert 检查测试预期：比较 request.password == ' password '；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert request.password == " password "
    # assert 检查测试预期：比较 request.remember_me is False；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert request.remember_me is False


# 函数 test_profile_create_allows_omitting_optional_content()：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_profile_create_allows_omitting_optional_content():
    """仅名称即可创建基本资料，其他内容默认空值。"""
    # 将结果保存在 候选人的技能：调用 CandidateProfileCreate（参数见括号），取得结果或执行相应操作
    candidate = CandidateProfileCreate(display_name=" Alice ")
    # 将结果保存在 employer：调用 EmployerProfileCreate（参数见括号），取得结果或执行相应操作
    employer = EmployerProfileCreate(company_name=" Demo ")
    # assert 检查测试预期：比较 candidate.display_name == 'Alice'；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert candidate.display_name == "Alice"
    # assert 检查测试预期：比较 candidate.resume_text == ''；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert candidate.resume_text == ""
    # assert 检查测试预期：比较 candidate.skills == []；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert candidate.skills == []
    # assert 检查测试预期：比较 employer.company_name == 'Demo'；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert employer.company_name == "Demo"
    # assert 检查测试预期：比较 employer.company_description == ''；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert employer.company_description == ""
    # 调用 candidate.skills.append（参数见括号），取得结果或执行相应操作
    candidate.skills.append("python")
    # assert 检查测试预期：比较 CandidateProfileCreate(display_name='Bob').skills == []；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert CandidateProfileCreate(display_name="Bob").skills == []


# 让相同测试用下面各组输入分别运行，覆盖不同边界
@pytest.mark.parametrize(
    # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
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
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ),
        (EmployerProfileCreate, {"company_name": "Demo", "role": "candidate"}),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    ],
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)
# 函数 test_profile_create_validates_names_types_and_ownership_fields(schema, payload)：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_profile_create_validates_names_types_and_ownership_fields(schema, payload):
    """资料创建拒绝空白名称、无效技能及客户端指定所有者或角色。"""
    # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
    with pytest.raises(ValidationError):
        # 按 schema 校验/提取字段，避免返回未声明的内部数据
        schema.model_validate(payload)


# 函数 test_profile_update_distinguishes_omission_from_clearing()：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_profile_update_distinguishes_omission_from_clearing():
    """未传字段不更新，显式空内容用于清空可选字段。"""
    # assert 检查测试预期：比较 CandidateProfileUpdate().model_dump(exclude_unset=True) == {}；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert CandidateProfileUpdate().model_dump(exclude_unset=True) == {}
    # assert 检查测试预期：比较 CandidateProfileUpdate(resume_text='', skills=[]).model_dump(exclude_unset=True) == {'resume_text': '', 'skills'…；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert CandidateProfileUpdate(resume_text="", skills=[]).model_dump(
        # 这一项指定 exclude_unset；逗号分隔同一调用/结构中的各个参数或字段
        exclude_unset=True
        # 继续完成上面的多行语句：assert 检查测试预期：比较 CandidateProfileUpdate(resume_text='', skills=[]).model_dump(exclude_unset=True) == {'resume_text': '', 'skills'…；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    ) == {"resume_text": "", "skills": []}


# 让相同测试用下面各组输入分别运行，覆盖不同边界
@pytest.mark.parametrize(
    # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
    "schema, field",
    [
        (CandidateProfileUpdate, "display_name"),
        (CandidateProfileUpdate, "resume_text"),
        (CandidateProfileUpdate, "skills"),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    ],
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)
# 函数 test_profile_update_rejects_explicit_null(schema, field)：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_profile_update_rejects_explicit_null(schema, field):
    """显式 null 不能写入数据库非空资料字段。"""
    # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
    with pytest.raises(ValidationError):
        # 按 schema 校验/提取字段，避免返回未声明的内部数据
        schema.model_validate({field: None})


# 函数 test_auth_response_excludes_password_hash_and_private_profile()：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_auth_response_excludes_password_hash_and_private_profile():
    """认证响应只暴露账户信息，不包含密码哈希或私有资料。"""
    # 将结果保存在 已通过认证的账户：调用 User（参数见括号），取得结果或执行相应操作
    user = User(
        # 这一项指定 账户邮箱；逗号分隔同一调用/结构中的各个参数或字段
        email="demo@example.com",
        hashed_password="fake-hash",
        role=Role.Candidate,
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 将结果保存在 public：按 schema 校验/提取字段，避免返回未声明的内部数据
    public = UserPublic(
        id=user.id, email=user.email, role=user.role, profile_completed=False
    )
    # 将结果保存在 接口返回的 HTTP 响应：将已校验对象转为字典；exclude_unset=True 只保留请求明确传入的字段
    response = AuthResponse(access_token="fake-token", user=public).model_dump(
        # 这一项指定 mode；逗号分隔同一调用/结构中的各个参数或字段
        mode="json"
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # assert 检查测试预期：比较 response['token_type'] == 'bearer'；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert response["token_type"] == "bearer"
    # assert 检查测试预期：比较 response['user'] == {'id': str(user.id), 'email': user.email, 'role': 'candidate'}；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert response["user"] == {
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "id": str(user.id),
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "email": user.email,
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "role": "candidate",
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        "profile_completed": False,
    }
    # assert 检查测试预期：比较 'hashed_password' not in response['user']；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert "hashed_password" not in response["user"]
    # assert 检查测试预期：比较 'resume_text' not in response['user']；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert "resume_text" not in response["user"]


# 函数 test_owner_profile_response_preserves_resume_text()：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_owner_profile_response_preserves_resume_text():
    """本人资料响应保留简历原文与空技能列表。"""
    # 将结果保存在 候选人资料：调用 CandidateProfilePublic（参数见括号），取得结果或执行相应操作
    profile = CandidateProfilePublic(
        # 这一项指定 资料所有者的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
        user_id=uuid.uuid4(),
        # 这一项指定 候选人显示名称；逗号分隔同一调用/结构中的各个参数或字段
        display_name="Alice",
        # 这一项指定 只有本人可读写的纯文本简历；逗号分隔同一调用/结构中的各个参数或字段
        resume_text=" Line 1\nLine 2 ",
        # 这一项指定 技术技能列表；逗号分隔同一调用/结构中的各个参数或字段
        skills=[],
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # assert 检查测试预期：比较 profile.resume_text == ' Line 1\nLine 2 '；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert profile.resume_text == " Line 1\nLine 2 "
    # assert 检查测试预期：比较 profile.skills == []；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
    assert profile.skills == []
