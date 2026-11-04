"""FP-MATCH-1 匹配分：公式示例、归一化与雇主侧平级规则。"""

from app.employer.matching import match_score


def test_fp_match_1_skill_overlap_examples():
    """需求表格四组示例：全覆盖 100、半覆盖 50、零覆盖 0、空技能 100。"""
    assert match_score(["Python", "SQL"], ["Python", "SQL"]) == 100
    assert match_score(["Python"], ["Python", "SQL"]) == 50
    assert match_score(["Rust"], ["Python", "SQL"]) == 0
    assert match_score(["Python", "SQL"], []) == 100
    assert match_score([], []) == 100


def test_fp_match_1_normalization_applies_to_both_sides():
    """技能去空白、转小写、去空项、去重后才计算交集。"""
    assert match_score(["  Python ", "python", ""], ["PYTHON", "sql"]) == 50
    assert match_score(["Python", "python"], ["python"]) == 100
    assert match_score(["", "  "], ["python"]) == 0


def test_fp_match_1_score_is_floor_and_bounded():
    """分数是 floor 整除结果且落在 0-100；部分命中不足一份时不进位。"""
    # 2/3 * 100 = 66.67 -> floor 66
    assert match_score(["a", "b"], ["a", "b", "c"]) == 66
    # 1/3 * 100 = 33.33 -> floor 33
    assert match_score(["a"], ["a", "b", "c"]) == 33
    for candidate, required in (
        (["a"], ["a", "b"]),
        (["x"], ["a", "b"]),
        ([], ["a"]),
        (["a"], []),
    ):
        score = match_score(candidate, required)
        assert 0 <= score <= 100
        assert isinstance(score, int)


def test_fp_match_1_employer_applicant_tie_breakers(
    client, make_employer, make_candidate, make_job, make_application
):
    """申请人平级：按显示名不区分大小写，再按候选人 ID 稳定排序。"""
    employer = make_employer()
    job = make_job(employer, title="Tie Job", required_skills=["python"])
    # 三人同分（都只有 python，对 [python] 全覆盖）；显示名大小写交叉。
    zoe = make_candidate(name="zoe", skills=["python"])
    alice_upper = make_candidate(name="Alice", skills=["python"])
    alice_lower = make_candidate(name="alice", skills=["python"])
    for candidate_headers in (zoe, alice_lower, alice_upper):
        make_application(candidate_headers, job)

    listed = client.get(
        f"/employer/jobs/{job['id']}/applications", headers=employer
    )
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    # zoe 按小写名排在最后；Alice/alice 小写同名，再比候选人 ID。
    assert rows[-1]["display_name"] == "zoe"
    assert {row["display_name"] for row in rows[:2]} == {"Alice", "alice"}
    keys = [
        (row["display_name"].lower(), row["candidate_id"]) for row in rows[:2]
    ]
    assert keys == sorted(keys)

    # 同显示名时按候选人 ID 升序稳定排列。
    same_a = make_candidate(email="tie-a@example.com", name="Same", skills=["python"])
    same_b = make_candidate(email="tie-b@example.com", name="Same", skills=["python"])
    job2 = make_job(employer, title="Tie Job 2", required_skills=["python"])
    for candidate_headers in (same_b, same_a):
        make_application(candidate_headers, job2)

    listed2 = client.get(
        f"/employer/jobs/{job2['id']}/applications", headers=employer
    ).json()
    ids = [row["candidate_id"] for row in listed2]
    assert ids == sorted(ids)
    assert {row["display_name"] for row in listed2} == {"Same"}
