"""原子重置本地演示库；演示凭据仅限本地，不得用于真实环境。

在 backend 目录执行 python scripts/seed_demo.py。默认生成 UTC 次日 10:00 的
共享 30 分钟时段；可用 --reference-date YYYY-MM-DD 固定基准日期复现。
相同基准日期生成相同业务数据（密码使用随机盐）；历史日期可能产生过期时段。
命令清空配置库的全部业务数据及会话，请只对本地演示库执行。
"""

import argparse
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
DEMO_PASSWORD = "demo-local-only"
TABLES = (
    "booking",
    "application",
    "job_skill",
    "interview_slot",
    "job",
    "candidate_skill",
    "user_session",
    "candidate_profile",
    "employer_profile",
    '"user"',
)


def fixed_id(name: str) -> uuid.UUID:
    """保留既有固定 ID，兼容演示链接与测试。"""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"symanage-seed/{name}")


def slot_start(reference_date: date) -> datetime:
    """以 UTC 日期安排次日时段，避免写死日历日期后过期。"""
    return datetime.combine(reference_date + timedelta(days=1), time(10), timezone.utc)


def reset_tables(session) -> None:
    """在调用方事务内清空数据，不提前提交；失败时清空也会回滚。"""
    from sqlalchemy import text

    session.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))


def build_seed_rows(reference_date: date | None = None) -> list[list]:
    """按外键顺序组装数据；不写库，保留原函数的分组返回合同。"""
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

    reference_date = (
        reference_date
        if reference_date is not None
        else datetime.now(timezone.utc).date()
    )
    starts_at = slot_start(reference_date)
    timestamp = datetime.combine(reference_date, time(), timezone.utc)
    password_hash = hash_password(DEMO_PASSWORD)
    accounts = [
        ("employer-1", "demo-employer1@example.com", Role.Employer),
        ("employer-2", "demo-employer2@example.com", Role.Employer),
        ("alice", "demo-alice@example.com", Role.Candidate),
        ("bob", "demo-bob@example.com", Role.Candidate),
        ("carol", "demo-carol@example.com", Role.Candidate),
    ]
    users = [
        User(
            id=fixed_id(key),
            email=email,
            hashed_password=password_hash,
            role=role,
            created_at=timestamp,
        )
        for key, email, role in accounts
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
        *[
            CandidateProfile(
                user_id=fixed_id(name.lower()),
                display_name=name,
                resume_text=f"Demo resume for {name}.",
            )
            for name in ("Alice", "Bob", "Carol")
        ],
    ]
    skills = [
        CandidateSkill(candidate_id=fixed_id(who), name=skill)
        for who, skill in [
            ("alice", "python"),
            ("alice", "sql"),
            ("bob", "python"),
            ("carol", "rust"),
        ]
    ]
    job_specs = [
        (
            "job-backend",
            "employer-1",
            "Backend Engineer",
            "Local demo job with skills python and sql.",
            ["python", "sql"],
        ),
        (
            "job-data-entry",
            "employer-2",
            "Data Entry Clerk",
            "Local demo job with skills typing and excel.",
            ["typing", "excel"],
        ),
        (
            "job-general",
            "employer-1",
            "General Assistant",
            "Local demo job with no required skills.",
            [],
        ),
    ]
    jobs = [
        Job(
            id=fixed_id(key),
            employer_id=fixed_id(owner),
            title=title,
            description=description,
            created_at=timestamp,
            updated_at=timestamp,
        )
        for key, owner, title, description, _ in job_specs
    ]
    job_skills = [
        JobSkill(job_id=fixed_id(key), name=skill)
        for key, _, _, _, required in job_specs
        for skill in required
    ]
    slots = [
        InterviewSlot(
            id=fixed_id("slot-backend"),
            employer_id=fixed_id("employer-1"),
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=30),
        )
    ]
    app_specs = [
        ("alice", "backend", ApplicationStatus.Interviewing),
        ("bob", "backend", ApplicationStatus.Interviewing),
        ("carol", "backend", ApplicationStatus.Rejected),
        ("alice", "general", ApplicationStatus.Accepted),
        ("bob", "general", ApplicationStatus.Pending),
    ]
    applications = [
        Application(
            id=fixed_id(f"app-{who}-{job}"),
            candidate_id=fixed_id(who),
            job_id=fixed_id("job-" + job),
            status=status,
            created_at=timestamp,
            updated_at=timestamp,
        )
        for who, job, status in app_specs
    ]
    return [users, profiles, skills, jobs, job_skills, slots, applications]


def print_demo_summary(starts_at: datetime | None = None) -> None:
    """标出演示凭据、时段与匹配示例，不将命令成功当作预约测试。"""
    from app.employer.matching import match_score

    print("Local demo data seeded. Credentials are LOCAL/DEMO ONLY:")
    for who in ("employer1", "employer2", "alice", "bob", "carol"):
        print(f"  {who}: demo-{who}@example.com / {DEMO_PASSWORD}")
    if starts_at is not None:
        print(
            f"Shared 30-minute slot: {starts_at.isoformat()} (UTC); Alice and Bob are Interviewing."
        )
    for candidate, required, expected in (
        (["python", "sql"], ["python", "sql"], 100),
        (["python"], ["python", "sql"], 50),
        (["rust"], ["python", "sql"], 0),
        (["anything"], [], 100),
    ):
        print(
            f"match_score({candidate}, {required}) = {match_score(candidate, required)} (expect {expected})"
        )


def main(argv: list[str] | None = None) -> int:
    """构建数据后，在同一事务中重置与写入，失败时保留原数据。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-date", type=date.fromisoformat, help="固定 UTC 基准日期 YYYY-MM-DD"
    )
    args = parser.parse_args(argv)
    reference_date = (
        args.reference_date
        if args.reference_date is not None
        else datetime.now(timezone.utc).date()
    )
    try:
        slot_start(reference_date)
    except OverflowError:
        parser.error("reference-date must leave room for the next day's slot")
    from sqlmodel import Session
    from app.db.session import engine

    try:
        groups = build_seed_rows(reference_date)
        with Session(engine) as session, session.begin():
            reset_tables(session)
            for group in groups:
                session.add_all(group)
                session.flush()
    except Exception as error:
        print(f"Seed failed; reset rolled back: {error}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    print_demo_summary(slot_start(reference_date))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
