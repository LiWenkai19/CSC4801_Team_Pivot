"""候选人与雇主共用的确定性匹配契约。"""


from app.users.service import normalize_skills  # Reuse the team contract.


def match_score(candidate: list[str], required: list[str]) -> int:
    required_set = set(normalize_skills(required))
    if not required_set:
        return 100
    return (
        100 * len(set(normalize_skills(candidate)) & required_set) // len(required_set)
    )


def job_sort_key(row: dict) -> tuple:
    return -row["score"], row["title"].lower(), str(row["id"])


def applicant_sort_key(row: dict) -> tuple:
    return -row["score"], row["display_name"].lower(), str(row["candidate_id"])


# 当前推荐评分为占位符，与上面的历史交集算法分开，避免误认为已上线真实匹配。
SCORE_KIND = "placeholder"


def placeholder_match_score(candidate: list[str], required: list[str]) -> int:
    """保留双方技能输入；零分不代表真实匹配程度。"""
    return 0
