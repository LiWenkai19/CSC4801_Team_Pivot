import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from sqlalchemy import create_engine, inspect, text
from sqlmodel import Session, SQLModel
from fastapi.testclient import TestClient
import audit_context as r

OUT, SRC = r.OUT, r.SRC
cases = []


def record(id, ok, expected, actual, cause=None, reason=None):
    cases.append(
        {
            "id": id,
            "outcome": "passed" if ok else "failed",
            "expected": expected,
            "actual": actual,
            "cause_id": None if ok else cause,
            "reason": None if ok else reason,
        }
    )
    r.save(
        "delivery-results.json",
        {
            "sha": r.SHA,
            "cases": cases,
            "counts": {
                key: sum(x["outcome"] == key for x in cases)
                for key in ["passed", "failed"]
            },
            "docker_excluded": True,
            "repairs": [],
        },
    )


def envdb(name):
    env = dict(os.environ)
    env["DATABASE_URL"] = env["DATABASE_URL"].rsplit("/", 1)[0] + "/" + name
    return env


def snapshot(engine):
    output = {}
    with engine.connect() as c:
        tables = inspect(c).get_table_names()
        for table in tables:
            rows = [
                dict(row)
                for row in c.execute(text('SELECT * FROM "' + table + '"')).mappings()
            ]
            for row in rows:
                for key in ["hashed_password", "created_at", "updated_at"]:
                    row.pop(key, None)
            output[table] = sorted(
                rows, key=lambda x: json.dumps(x, sort_keys=True, default=str)
            )
    canonical = json.dumps(output, sort_keys=True, default=str)
    return {
        "semantic_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "counts": {t: len(rows) for t, rows in output.items()},
        "rows": output,
    }


def main():
    from app.users import model as users
    from app.employer import model as employers
    from app.core.config import settings
    from sqlalchemy.engine import make_url

    url = make_url(os.environ["DATABASE_URL"])
    engine = create_engine(url)
    install = (SRC / "INSTALL.md").read_text(encoding="utf-8")
    sections = re.split(r"(?m)^## (.+)\r?\n", install)
    body = {sections[i]: sections[i + 1].strip() for i in range(1, len(sections), 2)}
    required = [
        "Environment Variables",
        "Database Setup and Migrations",
        "Demo Data and Reset Command",
        "Local Development",
        "Running Unit Tests",
        "Troubleshooting",
    ]
    missing = [name for name in required if not body.get(name)]
    record(
        "INSTALL-non-docker-instructions",
        not missing,
        "Six non-Docker operational sections contain executable configuration/setup/start/seed/test instructions",
        {"empty_sections": missing},
        "SE-02",
        "INSTALL仍缺非Docker运行必需配置与命令，不能仅凭源码推导的测试harness代替安装说明。",
    )
    for kind in ["no-env", "example-env"]:
        cwd = OUT / "config-probes" / kind
        cwd.mkdir(parents=True, exist_ok=True)
        if kind == "example-env":
            (cwd / ".env").write_bytes((SRC / ".env.example").read_bytes())
        env = dict(os.environ)
        for key in list(env):
            if key.startswith(("APP_", "DATABASE_", "SESSION_", "CSRF_", "COOKIE_")):
                env.pop(key)
        result = r.run(
            "config-" + kind,
            [r.PYTHON, "-c", "from app.main import app; print(app.title)"],
            env,
            cwd,
            20,
        )
        diagnostic = Path(result["log"]).read_text(encoding="utf-8")
        valid_configuration_boundary = (
            result["exit_code"] != 0
            and all(name in diagnostic for name in ("APP_NAME", "DATABASE_URL", "Field required"))
            and "ModuleNotFoundError" not in diagnostic
        ) if kind == "no-env" else result["exit_code"] == 0
        record(
            "INSTALL-" + kind + "-import",
            valid_configuration_boundary,
            "Missing required settings are explicitly rejected; documented example configuration permits import",
            {"exit_code": result["exit_code"], "log": result["log"]},
            "SE-02",
            "文档未给出APP_NAME/DATABASE_URL配置；根.env.example仍为旧SQLite示例，Settings读取当前目录.env后仍缺必填项。",
        )
    valid = r.run(
        "config-positive-control",
        [r.PYTHON, "-c", "from app.main import app; print(app.title)"],
        dict(os.environ),
        OUT / "config-probes/no-env",
        20,
    )
    record(
        "INSTALL-explicit-isolated-env-control",
        valid["exit_code"] == 0,
        "Actual mandatory settings supplied by test harness allow import",
        {"exit_code": valid["exit_code"]},
    )
    from packaging.requirements import Requirement
    import importlib.metadata

    versions = []
    for line in (SRC / "requirements.lock").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        req = Requirement(line)
        if req.marker and not req.marker.evaluate():
            continue
        actual = importlib.metadata.version(req.name)
        versions.append(
            {
                "package": req.name,
                "actual": actual,
                "matches": req.specifier.contains(actual),
            }
        )
    r.save("locked-dependency-verification.json", versions)
    record(
        "INSTALL-lock-versions",
        all(x["matches"] for x in versions),
        "All applicable pinned versions match",
        {
            "count": len(versions),
            "mismatches": [x for x in versions if not x["matches"]],
        },
    )

    # Three databases in one fresh local cluster, never the user's configured DB.
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        for name in ["audit_empty", "audit_upgrade"]:
            if not c.execute(
                text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": name}
            ).first():
                c.execute(text("CREATE DATABASE " + name))
    admin.dispose()
    empty = r.run(
        "migrate-empty",
        [r.PYTHON, "-m", "alembic", "upgrade", "head"],
        envdb("audit_empty"),
    )
    prior = r.run(
        "migrate-initial-revision",
        [r.PYTHON, "-m", "alembic", "upgrade", "e07644577837"],
        envdb("audit_upgrade"),
    )
    preserved_id = uuid.uuid4()
    previous = create_engine(url.set(database="audit_upgrade"))
    with previous.begin() as c:
        c.execute(
            text(
                'INSERT INTO "user"(id,email,hashed_password,role,created_at) VALUES(:id,:email,:password,:role,CURRENT_TIMESTAMP)'
            ),
            {
                "id": preserved_id,
                "email": "migration-control@example.com",
                "password": "synthetic-hash-only",
                "role": "candidate",
            },
        )
    previous.dispose()
    upgraded = r.run(
        "migrate-old-to-head",
        [r.PYTHON, "-m", "alembic", "upgrade", "head"],
        envdb("audit_upgrade"),
    )
    repeat = r.run(
        "migrate-repeat-head",
        [r.PYTHON, "-m", "alembic", "upgrade", "head"],
        envdb("audit_empty"),
    )
    record(
        "MIGRATION-empty-old-and-repeat",
        all(x["exit_code"] == 0 for x in [empty, prior, upgraded, repeat]),
        "Fresh initialization, initial-revision upgrade, repeated upgrade all succeed",
        {"exit_codes": [x["exit_code"] for x in [empty, prior, upgraded, repeat]]},
    )
    previous = create_engine(url.set(database="audit_upgrade"))
    with previous.connect() as c:
        preserved = c.execute(
            text('SELECT email,role FROM "user" WHERE id=:id'), {"id": preserved_id}
        ).one()
    record(
        "MIGRATION-preserves-existing-user",
        tuple(preserved) == ("migration-control@example.com", "candidate"),
        "Existing valid user survives full revision-chain upgrade",
        {"preserved": True},
    )
    previous.dispose()
    check = r.run(
        "alembic-default-check", [r.PYTHON, "-m", "alembic", "check"], dict(os.environ)
    )
    record(
        "MIGRATION-default-alembic-check",
        check["exit_code"] == 0,
        "Default Alembic check runs without new schema operations",
        {"exit_code": check["exit_code"], "server_defaults_compared": False},
    )
    inventories = {}
    diffs = {}
    for name in ["slots_test", "audit_empty", "audit_upgrade"]:
        db = create_engine(url.set(database=name))
        with db.connect() as c:
            inspector = inspect(c)
            diffs[name] = compare_metadata(
                MigrationContext.configure(
                    c, opts={"compare_server_default": True, "compare_type": True}
                ),
                SQLModel.metadata,
            )
            inventories[name] = {
                table: {
                    "columns": [
                        {k: str(v) for k, v in col.items()}
                        for col in inspector.get_columns(table)
                    ],
                    "unique": inspector.get_unique_constraints(table),
                    "foreign_keys": inspector.get_foreign_keys(table),
                    "checks": inspector.get_check_constraints(table),
                    "pk": inspector.get_pk_constraint(table),
                }
                for table in inspector.get_table_names()
            }
        db.dispose()
    r.save("schema-inventories.json", inventories)
    r.save("model-migration-differences.json", diffs)
    record(
        "MIGRATION-model-default-type-consistency",
        all(not x for x in diffs.values()),
        "Model and all migrated schemas agree including server defaults/types",
        {"differences": diffs},
        "SE-06",
        "Application.status模型声明server_default Pending，但主迁移未创建该数据库默认值；默认alembic check未启用server-default比较，因此会通过。",
    )
    # Check actual schema equality across the two independent upgrade paths.
    record(
        "MIGRATION-empty-vs-upgrade-schema",
        inventories["audit_empty"] == inventories["audit_upgrade"],
        "Empty and old-version upgrade paths produce identical schemas",
        {"same_inventory": inventories["audit_empty"] == inventories["audit_upgrade"]},
    )

    seed_results = []
    snapshots = []
    for index in [1, 2]:
        result = r.run(
            "seed-" + str(index),
            [r.PYTHON, "scripts/seed_demo.py"],
            dict(os.environ),
            timeout=35,
        )
        seed_results.append(result)
        snapshots.append(snapshot(engine))
    r.save(
        "seed-snapshots.json",
        {
            "first": snapshots[0],
            "second": snapshots[1],
            "ignored_fields": ["hashed_password", "created_at", "updated_at"],
        },
    )
    record(
        "SEED-command-and-repeat-determinism",
        all(x["exit_code"] == 0 for x in seed_results)
        and snapshots[0]["semantic_sha256"] == snapshots[1]["semantic_sha256"],
        "Two actual reset/seed commands succeed and yield equal business snapshots",
        {
            "codes": [x["exit_code"] for x in seed_results],
            "semantic_equal": snapshots[0]["semantic_sha256"]
            == snapshots[1]["semantic_sha256"],
            "counts": snapshots[1]["counts"],
        },
    )
    with engine.connect() as c:
        roles = dict(
            c.execute(text('SELECT role,count(*) FROM "user" GROUP BY role')).all()
        )
        statuses = {
            row[0] for row in c.execute(text("SELECT DISTINCT status FROM application"))
        }
        required_jobs = c.execute(
            text("SELECT count(DISTINCT job_id) FROM job_skill")
        ).scalar_one()
        slots = [
            dict(row)
            for row in c.execute(
                text(
                    "SELECT id,starts_at,ends_at,extract(epoch from ends_at-starts_at)/60 AS minutes,starts_at>CURRENT_TIMESTAMP AS future FROM interview_slot"
                )
            ).mappings()
        ]
        eligible = [
            dict(row)
            for row in c.execute(
                text(
                    "SELECT a.id AS application_id,s.id AS slot_id FROM application a JOIN job j ON j.id=a.job_id JOIN interview_slot s ON s.employer_id=j.employer_id WHERE a.status='Interviewing' AND NOT j.is_deleted AND s.starts_at>CURRENT_TIMESTAMP AND s.ends_at-s.starts_at=interval '30 minutes' AND NOT EXISTS(SELECT 1 FROM booking b WHERE b.slot_id=s.id OR b.application_id=a.id)"
                )
            ).mappings()
        ]
    record(
        "SEED-roles-jobs-statuses",
        roles.get("candidate", 0) >= 2
        and roles.get("employer", 0) >= 2
        and required_jobs >= 2
        and statuses == {"Pending", "Interviewing", "Rejected", "Accepted"},
        "Required role/job counts and all four statuses exist",
        {
            "roles": roles,
            "jobs_with_skills": required_jobs,
            "statuses": sorted(statuses),
        },
    )
    from app.main import app
    from scripts.seed_demo import fixed_id

    clients = []
    apis = {}
    for who in ["alice", "bob", "carol", "employer1"]:
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()
        clients.append(client)
        login = client.post(
            "/users/login",
            json={"email": f"demo-{who}@example.com", "password": "demo-local-only"},
        )
        assert login.status_code == 200
        apis[who] = client
    try:
        job_id = str(fixed_id("job-backend"))
        general_id = str(fixed_id("job-general"))
        for who, jobid, expected in [
            ("alice", job_id, 100),
            ("bob", job_id, 50),
            ("carol", job_id, 0),
            ("carol", general_id, 100),
        ]:
            response = apis[who].get("/candidate/jobs/" + jobid)
            actual = (
                response.json().get("match_score")
                if response.status_code == 200
                else None
            )
            record(
                "SEED-score-" + who + "-" + str(expected),
                response.status_code == 200 and actual == expected,
                "Actual seeded API score equals " + str(expected),
                {"status": response.status_code, "score": actual},
            )
        pairs = []
        for who in ["alice", "bob"]:
            appid = str(fixed_id("app-" + who + "-backend"))
            response = apis[who].get("/candidate/applications/" + appid + "/slots")
            assert response.status_code == 200
            pairs.append({row["id"] for row in response.json()})
        common = pairs[0] & pairs[1]
        record(
            "SEED-two-candidate-common-availability",
            len(common) > 0 and len(eligible) >= 2,
            "Two Interviewing candidates can select the same future unbooked 30-minute seed slot",
            {
                "common_slots": sorted(common),
                "eligible_pairs": eligible,
                "stored_slots": slots,
            },
            "SE-05",
            "唯一seed时段仍为60分钟，不满足预约严格30分钟要求；当前时段仍未来，失败不是过期或接口故障。",
        )
        # The shared seed supports one winner; the later candidate must get 409.
        for who in ["alice", "bob"]:
            before = snapshot(engine)
            client = apis[who]
            csrf = client.cookies["csrf_token"]
            appid = str(fixed_id("app-" + who + "-backend"))
            response = client.post(
                "/candidate/applications/" + appid + "/booking",
                headers={"X-CSRF-Token": csrf},
                json={"slot_id": str(fixed_id("slot-backend"))},
            )
            after = snapshot(engine)
            expected_status = 201 if who == "alice" else 409
            expected_booking = {
                "application_id": appid,
                "slot_id": str(fixed_id("slot-backend")),
            }
            storage_ok = (
                len(after["rows"]["booking"]) == 1
                and all(after["rows"]["booking"][0][key] == uuid.UUID(value)
                        for key, value in expected_booking.items())
            ) if who == "alice" else (
                before["semantic_sha256"] == after["semantic_sha256"]
                and response.json().get("detail") == "Slot already booked"
            )
            record(
                "SEED-original-booking-" + who,
                response.status_code == expected_status and storage_ok,
                "Alice books the shared seed slot (201); Bob is rejected (409) without state changes",
                {
                    "status": response.status_code,
                    "body": response.json(),
                    "business_state_unchanged": before["semantic_sha256"]
                    == after["semantic_sha256"],
                },
                "SE-05",
                "原seed数据的60分钟时段被业务规则正确拒绝；拒绝后业务快照保持，不能据此声称预约模块本身坏了。",
            )
        # A separate API-created positive control does not repair or alter seed script.
        owner = apis["employer1"]
        fresh = owner.post(
            "/employer/interview-slots",
            headers={"X-CSRF-Token": owner.cookies["csrf_token"]},
            json={"starts_at": "2031-06-01T02:00:00Z"},
        )
        assert fresh.status_code == 201
        alice_slots = apis["alice"].get(
            "/candidate/applications/" + str(fixed_id("app-alice-backend")) + "/slots"
        )
        bob_slots = apis["bob"].get(
            "/candidate/applications/" + str(fixed_id("app-bob-backend")) + "/slots"
        )
        positive = (
            alice_slots.status_code == 409
            and alice_slots.json().get("detail") == "Application already booked"
            and bob_slots.status_code == 200
            and any(row["id"] == fresh.json()["id"] for row in bob_slots.json())
        )
        record(
            "SEED-separate-valid-slot-control",
            positive,
            "The new slot is visible to unbooked Bob; Alice's existing booking prevents a second selection",
            {"alice_status": alice_slots.status_code, "bob_status": bob_slots.status_code},
        )
    finally:
        for client in reversed(clients):
            client.__exit__(None, None, None)

    # Demonstrate the migration default gap without conflating it with ORM behavior.
    with engine.connect() as c:
        candidate_id, posting_id = c.execute(
            text(
                "SELECT c.user_id,j.id FROM candidate_profile c CROSS JOIN job j WHERE NOT EXISTS(SELECT 1 FROM application a WHERE a.candidate_id=c.user_id AND a.job_id=j.id) LIMIT 1"
            )
        ).one()
    identifier = uuid.uuid4()
    raw_error = None
    try:
        with engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO application(id,candidate_id,job_id,created_at,updated_at) VALUES(:id,:candidate,:job,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
                ),
                {"id": identifier, "candidate": candidate_id, "job": posting_id},
            )
    except Exception as e:
        raw_error = {
            "type": type(e).__name__,
            "driver_type": type(getattr(e, "orig", None)).__name__,
            "column": getattr(
                getattr(getattr(e, "orig", None), "diag", None), "column_name", None
            ),
        }
    with engine.begin() as connection:
        raw_status = connection.execute(
            text("SELECT status FROM application WHERE id=:id"), {"id": identifier}
        ).scalar_one_or_none()
        connection.execute(text("DELETE FROM application WHERE id=:id"), {"id": identifier})
    with Session(engine) as db:
        row = employers.Application(candidate_id=candidate_id, job_id=posting_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        orm_status = row.status.value
        db.delete(row)
        db.commit()
    record(
        "MIGRATION-default-raw-insert-vs-ORM",
        raw_error is None and raw_status == orm_status == "Pending",
        "Database default promised by model applies when status omitted; ordinary ORM still defaults Pending",
        {"raw_insert_error": raw_error, "raw_status": raw_status, "orm_status": orm_status},
        "SE-06",
        "数据库未提供模型声明的默认值，省略status的直接写入违反非空；ORM自身赋Pending仍成功，影响范围分别记录。",
    )
    engine.dispose()
    print(
        json.dumps(
            {
                "counts": {
                    k: sum(x["outcome"] == k for x in cases)
                    for k in ["passed", "failed"]
                },
                "failed_causes": [
                    x["cause_id"] for x in cases if x["outcome"] == "failed"
                ],
            },
            ensure_ascii=True,
        )
    )
    return 1 if any(x["outcome"] == "failed" for x in cases) else 0


if __name__ == "__main__":
    raise SystemExit(main())
