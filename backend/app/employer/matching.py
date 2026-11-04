"""FP-MATCH-1 技能重叠打分；雇主与候选人视图共用这一个实现。"""

from app.users.service import normalize_skills


def match_score(candidate_skills: list[str], required_skills: list[str]) -> int:
    """按 FP-MATCH-1 公式计算 0-100 的整数匹配分。"""
    required = set(normalize_skills(required_skills))
    if not required:
        return 100
    candidate = set(normalize_skills(candidate_skills))
    return (100 * len(candidate & required)) // len(required)
