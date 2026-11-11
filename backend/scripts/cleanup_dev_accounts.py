"""一次性脚本：清除 start.bat 遗留的 dev 临时账号（含资料行）。

用法（在 backend 目录）：python scripts/cleanup_dev_accounts.py
只删除邮箱为 dev-candidate@example.com / dev-employer@example.com 的账号，
与 scripts/dev_start.py 的自动清理逻辑一致。
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

DEV_EMAILS = ("dev-candidate@example.com", "dev-employer@example.com")


def main() -> int:
    from sqlalchemy import bindparam, text

    from app.db.session import engine

    with engine.begin() as conn:
        ids = [
            row[0]
            for row in conn.execute(
                text('SELECT id FROM "user" WHERE email IN :p').bindparams(
                    bindparam("p", expanding=True)
                ),
                {"p": list(DEV_EMAILS)},
            ).all()
        ]
        print(f"found {len(ids)} leftover dev account(s)")
        for uid in ids:
            # 先清业务行，再清资料与账号；顺序按外键依赖，同 seed_demo 的 TABLES。
            conn.execute(
                text(
                    "DELETE FROM booking WHERE application_id IN "
                    "(SELECT id FROM application WHERE candidate_id = :i "
                    "OR job_id IN (SELECT id FROM job WHERE employer_id = :i)) "
                    "OR slot_id IN (SELECT id FROM interview_slot WHERE employer_id = :i)"
                ),
                {"i": uid},
            )
            conn.execute(
                text(
                    "DELETE FROM application WHERE candidate_id = :i "
                    "OR job_id IN (SELECT id FROM job WHERE employer_id = :i)"
                ),
                {"i": uid},
            )
            conn.execute(
                text(
                    "DELETE FROM job_skill "
                    "WHERE job_id IN (SELECT id FROM job WHERE employer_id = :i)"
                ),
                {"i": uid},
            )
            conn.execute(
                text(
                    "DELETE FROM interview_slot WHERE employer_id = :i "
                    "OR job_id IN (SELECT id FROM job WHERE employer_id = :i)"
                ),
                {"i": uid},
            )
            conn.execute(
                text("DELETE FROM job WHERE employer_id = :i"), {"i": uid}
            )
            conn.execute(
                text("DELETE FROM candidate_skill WHERE candidate_id = :i"), {"i": uid}
            )
            conn.execute(
                text("DELETE FROM candidate_profile WHERE user_id = :i"), {"i": uid}
            )
            conn.execute(
                text("DELETE FROM employer_profile WHERE user_id = :i"), {"i": uid}
            )
            conn.execute(text('DELETE FROM "user" WHERE id = :i'), {"i": uid})
        left = conn.execute(
            text('SELECT count(*) FROM "user" WHERE email LIKE :p'), {"p": "dev-%"}
        ).scalar()
        print(f"remaining dev users: {left}")
    engine.dispose()
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
