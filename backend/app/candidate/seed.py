"""只针对本地演示数据库的显式重置命令，不在服务启动时执行。"""

import argparse

import uuid

from datetime import timedelta

from sqlmodel import Session, select

from app.candidate.model import (
    Application,
    ApplicationStatus,
    Booking,
    InterviewSlot,
    Job,
    JobSkill,
)

from app.db.session import engine

from app.users.model import (
    CandidateProfile,
    CandidateSkill,
    EmployerProfile,
    Role,
    User,
    utc_now,
)

from app.users.security import hash_password


def seed(session: Session):
    if session.exec(select(User)).first() is not None:
        raise ValueError(
            "Database is not empty; use --reset --confirm-demo-reset for a dedicated demo database"
        )
    users = [
        User(
            id=uuid.UUID(int=i + 1),
            email=email,
            role=Role.Candidate if i in (0, 1, 4) else Role.Employer,
            hashed_password=hash_password("Demo-only-123!"),
        )
        for i, email in enumerate(
            [
                "alice@example.com",
                "bob@example.com",
                "employer1@example.com",
                "employer2@example.com",
                "carol@example.com",
            ]
        )
    ]
    session.add_all(users)
    session.flush()
    session.add_all(
        [
            CandidateProfile(
                user_id=users[0].id,
                display_name="Alice",
                resume_text="Fictional local demo resume.",
            ),
            CandidateProfile(
                user_id=users[1].id,
                display_name="Bob",
                resume_text="Fictional local demo resume.",
            ),
            CandidateProfile(
                user_id=users[4].id,
                display_name="Carol",
                resume_text="Fictional Rust candidate.",
            ),
            EmployerProfile(
                user_id=users[2].id,
                company_name="Demo Labs",
                company_description="Local demo",
            ),
            EmployerProfile(
                user_id=users[3].id,
                company_name="Example Studio",
                company_description="Local demo",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [CandidateSkill(candidate_id=users[0].id, name=s) for s in ["python", "sql"]]
    )
    # 把对象加入数据库工作区；这一行本身还不等于提交成功
    session.add(CandidateSkill(candidate_id=users[1].id, name="python"))
    # 把对象加入数据库工作区；这一行本身还不等于提交成功
    session.add(CandidateSkill(candidate_id=users[4].id, name="rust"))
    titles = [
        "Backend Engineer",
        "Rust Engineer",
        "Open Role",
        "Data Engineer",
        "Platform Engineer",
    ]
    jobs = [
        Job(
            id=uuid.UUID(int=100 + i),
            employer_id=users[2 if i < 4 else 3].id,
            title=t,
            description=f"{t}: fictional role for local demonstration.",
        )
        for i, t in enumerate(titles)
    ]
    session.add_all(jobs)
    session.flush()
    required = [["python", "sql"], ["rust"], [], ["python", "sql"], ["sql"]]
    session.add_all(
        [
            JobSkill(job_id=job.id, name=s)
            for job, skills in zip(jobs, required)
            for s in skills
        ]
    )
    session.add_all(
        [
            Application(
                id=uuid.UUID(int=200),
                candidate_id=users[0].id,
                job_id=jobs[0].id,
                status=ApplicationStatus.Interviewing,
            ),
            Application(
                id=uuid.UUID(int=201),
                candidate_id=users[1].id,
                job_id=jobs[0].id,
                status=ApplicationStatus.Interviewing,
            ),
            Application(
                id=uuid.UUID(int=202),
                candidate_id=users[0].id,
                job_id=jobs[1].id,
                status=ApplicationStatus.Rejected,
            ),
            Application(
                id=uuid.UUID(int=203),
                candidate_id=users[0].id,
                job_id=jobs[2].id,
                status=ApplicationStatus.Accepted,
            ),
            Application(
                id=uuid.UUID(int=204),
                candidate_id=users[0].id,
                job_id=jobs[3].id,
                status=ApplicationStatus.Pending,
            ),
        ]
    )
    start = (utc_now() + timedelta(days=2)).replace(
        hour=2,
        minute=0,
        second=0,
        microsecond=0,
    )
    # 把对象加入数据库工作区；这一行本身还不等于提交成功
    session.add(
        InterviewSlot(
            id=uuid.UUID(int=300),
            employer_id=users[2].id,
            starts_at=start,
            ends_at=start + timedelta(minutes=30),
        )
    )
    # 提交整个事务；成功后数据库中的修改才正式生效
    # 第二个时段用于演示发生竞争冲突后，候选人仍能重新选择并预约。
    session.add(
        InterviewSlot(
            id=uuid.UUID(int=301),
            employer_id=users[2].id,
            starts_at=start + timedelta(hours=1),
            ends_at=start + timedelta(hours=1, minutes=30),
        )
    )
    session.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--confirm-demo-reset", action="store_true")
    args = parser.parse_args()
    if args.reset and not args.confirm_demo_reset:
        parser.error(
            "Reset requires --confirm-demo-reset; all application records will be deleted"
        )
    with Session(engine) as session:
        if args.reset:
            for model in [
                Booking,
                InterviewSlot,
                Application,
                JobSkill,
                Job,
                CandidateSkill,
                CandidateProfile,
                EmployerProfile,
                User,
            ]:
                for row in session.exec(select(model)):
                    # 准备删除指定记录；最终是否生效取决于事务提交
                    session.delete(row)
                session.flush()
        # 给专用空演示库写入固定 ID 的虚构账户、技能、职位、申请与未来时段
        seed(session)
    # 输出本地演示操作的结果提示，不输出真实密钥
    print(
        "Local demo ready: alice@example.com / bob@example.com; password Demo-only-123!"
    )


if __name__ == "__main__":
    # 解析演示重置参数；只有显式确认后才删除配置库内的应用记录
    main()
