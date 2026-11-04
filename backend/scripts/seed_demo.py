"""重置并写入本地演示数据；演示凭据仅限本地使用，不得用于任何真实环境。

用法（在 backend 目录）：python scripts/seed_demo.py
会清空当前配置库的全部业务表后重建演示数据，仅供本地演示与验收。
"""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# 本地演示密码；README 与输出中均标注仅限本地演示。
DEMO_PASSWORD = "demo-local-only"

TABLES = (
    "booking",
    "application",
    "job_skill",
    "interview_slot",
    "job",
    "candidate_skill",
    "candidate_profile",
    "employer_profile",
    '"user"',
)


def fixed_id(name: str) -> uuid.UUID:
    """生成确定性 ID，重复执行后演示数据可预测。"""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"symanage-seed/{name}")


def reset_tables(session) -> None:
    """清空业务表并重置自增序列；外键依赖由 CASCADE 一并处理。"""
    from sqlalchemy import text

    session.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    session.commit()


def build_seed_rows() -> list[list]:
    """组装演示账户、公司资料、技能、职位、申请与面试时段。

    按外键依赖分组返回（组间无跨组外键）：账户 → 角色资料 → 候选人技能 →
    职位 → 职位技能 → 面试时段 → 申请。数据覆盖 FP-MATCH-1 四个打分示例
    （100/50/0/空要求=100）、四种申请状态，以及两名 Interviewing 候选人
    竞争同一空闲时段。
    """
    from app.employer.model import (
        Application,
        ApplicationStatus,
        InterviewSlot,
        Job,
        JobSkill,
    )
    from app.users.model import (
        CandidateProfile,
        CandidateSkill,
        EmployerProfile,
        Role,
        User,
    )
    from app.users.security import hash_password

    password_hash = hash_password(DEMO_PASSWORD)

    users = [
        User(
            id=fixed_id("employer-1"),
            email="demo-employer1@example.com",
            hashed_password=password_hash,
            role=Role.Employer,
        ),
        User(
            id=fixed_id("employer-2"),
            email="demo-employer2@example.com",
            hashed_password=password_hash,
            role=Role.Employer,
        ),
        User(
            id=fixed_id("alice"),
            email="demo-alice@example.com",
            hashed_password=password_hash,
            role=Role.Candidate,
        ),
        User(
            id=fixed_id("bob"),
            email="demo-bob@example.com",
            hashed_password=password_hash,
            role=Role.Candidate,
        ),
        User(
            id=fixed_id("carol"),
            email="demo-carol@example.com",
            hashed_password=password_hash,
            role=Role.Candidate,
        ),
    ]

    profiles = [
        EmployerProfile(
            user_id=fixed_id("employer-1"),
            company_name="Acme Demo Labs",
            company_description="Local demo employer one.",
        ),
        EmployerProfile(
            user_id=fixed_id("employer-2"),
            company_name="Beta Demo Studio",
            company_description="Local demo employer two.",
        ),
        CandidateProfile(
            user_id=fixed_id("alice"),
            display_name="Alice",
            resume_text="Demo resume for Alice.",
        ),
        CandidateProfile(
            user_id=fixed_id("bob"),
            display_name="Bob",
            resume_text="Demo resume for Bob.",
        ),
        CandidateProfile(
            user_id=fixed_id("carol"),
            display_name="Carol",
            resume_text="Demo resume for Carol.",
        ),
    ]

    # 技能名已按 CHECK 约束要求归一化（去空白、小写）。
    skills = [
        CandidateSkill(candidate_id=fixed_id("alice"), name="python"),
        CandidateSkill(candidate_id=fixed_id("alice"), name="sql"),
        CandidateSkill(candidate_id=fixed_id("bob"), name="python"),
        CandidateSkill(candidate_id=fixed_id("carol"), name="rust"),
    ]

    jobs = [
        Job(
            id=fixed_id("job-backend"),
            employer_id=fixed_id("employer-1"),
            title="Backend Engineer",
            description="Local demo job with skills python and sql.",
        ),
        Job(
            id=fixed_id("job-data-entry"),
            employer_id=fixed_id("employer-2"),
            title="Data Entry Clerk",
            description="Local demo job with skills typing and excel.",
        ),
        Job(
            id=fixed_id("job-general"),
            employer_id=fixed_id("employer-1"),
            title="General Assistant",
            description="Local demo job with no required skills.",
        ),
    ]

    job_skills = [
        JobSkill(job_id=fixed_id("job-backend"), name="python"),
        JobSkill(job_id=fixed_id("job-backend"), name="sql"),
        JobSkill(job_id=fixed_id("job-data-entry"), name="typing"),
        JobSkill(job_id=fixed_id("job-data-entry"), name="excel"),
    ]

    # 四种状态各至少一条：Alice/Bob 对 Backend Engineer 均为 Interviewing。
    applications = [
        Application(
            id=fixed_id("app-alice-backend"),
            candidate_id=fixed_id("alice"),
            job_id=fixed_id("job-backend"),
            status=ApplicationStatus.Interviewing,
        ),
        Application(
            id=fixed_id("app-bob-backend"),
            candidate_id=fixed_id("bob"),
            job_id=fixed_id("job-backend"),
            status=ApplicationStatus.Interviewing,
        ),
        Application(
            id=fixed_id("app-carol-backend"),
            candidate_id=fixed_id("carol"),
            job_id=fixed_id("job-backend"),
            status=ApplicationStatus.Rejected,
        ),
        Application(
            id=fixed_id("app-alice-general"),
            candidate_id=fixed_id("alice"),
            job_id=fixed_id("job-general"),
            status=ApplicationStatus.Accepted,
        ),
        Application(
            id=fixed_id("app-bob-general"),
            candidate_id=fixed_id("bob"),
            job_id=fixed_id("job-general"),
            status=ApplicationStatus.Pending,
        ),
    ]

    # 固定起止时间保证演示数据可重复；时段留空不预约，供两名 Interviewing 候选人竞争。
    slots = [
        InterviewSlot(
            id=fixed_id("slot-backend"),
            employer_id=fixed_id("employer-1"),
            job_id=fixed_id("job-backend"),
            starts_at=datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc),
            ends_at=datetime(2026, 12, 1, 11, 0, tzinfo=timezone.utc),
        ),
    ]

    return [users, profiles, skills, jobs, job_skills, slots, applications]


def print_demo_summary() -> None:
    """打印演示凭据（标注仅限本地）并复核 FP-MATCH-1 四个示例分数。"""
    from app.employer.matching import match_score

    print("Local demo data seeded. Credentials are LOCAL/DEMO ONLY:")
    print("  employer1: demo-employer1@example.com / " + DEMO_PASSWORD)
    print("  employer2: demo-employer2@example.com / " + DEMO_PASSWORD)
    print("  alice:     demo-alice@example.com / " + DEMO_PASSWORD)
    print("  bob:       demo-bob@example.com / " + DEMO_PASSWORD)
    print("  carol:     demo-carol@example.com / " + DEMO_PASSWORD)
    examples = (
        (["python", "sql"], ["python", "sql"], 100),
        (["python"], ["python", "sql"], 50),
        (["rust"], ["python", "sql"], 0),
        (["anything"], [], 100),
    )
    for candidate, required, expected in examples:
        actual = match_score(candidate, required)
        print(f"match_score({candidate}, {required}) = {actual} (expect {expected})")


def main() -> int:
    """按配置连接本地库，清空业务表后写入演示数据。"""
    from sqlmodel import Session

    from app.db.session import engine

    try:
        with Session(engine) as session:
            reset_tables(session)
            # 按外键依赖分组写入，组间 flush 保证被引用行先行落库。
            for group in build_seed_rows():
                session.add_all(group)
                session.flush()
            session.commit()
    except Exception as error:
        print(f"Seed failed: {error}")
        return 1
    finally:
        engine.dispose()

    print_demo_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
