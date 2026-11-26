#!/usr/bin/env python
"""P8: bounded OpenAPI property fuzzing with Schemathesis (ASGI, no port).

Method
------
``schemathesis.openapi.from_asgi`` loads the live FastAPI OpenAPI document and
builds one Hypothesis strategy per operation.  Each generated ``Case`` is sent
through the real in-process ASGI app (no uvicorn, no port, no network) and is
checked with:

* ``not_a_server_error`` - no unclassified 5xx;
* ``status_code_conformance`` - document what the service returns;
* ``response_schema_conformance`` - successful/documentedly-error responses
  match the OpenAPI schemas;
* ``expected_status_matrix`` - a hand-written FP-AUTH-3 oracle (this module).

Three rounds run against the same disposable database:

1. **anonymous** - every operation without credentials.  Every protected
   operation must return 401 (422 is recorded if validation runs before the
   auth dependency, as allowed by the task brief);
2. **candidate** - a real candidate account, own ``/candidate/*`` operations
   plus ``GET /users/me``, and every ``/employer/*`` operation must return 403;
3. **employer** - the symmetric round for a real employer account.

Every unsafe method is capped at 10 examples; reads at 20.  ``--max-examples``
or ``ADVANCED_MAX_EXAMPLES`` can lower both caps.  Hypothesis is deterministic
(``derandomize=True``, no example database, ``deadline=None``) and the
Schemathesis retry/rate-limit machinery is left at its defaults (no concurrent
workers, no network).

Outputs
-------
``$ADVANCED_OUT/apifuzz/report.json`` is the durable, machine-readable report:
per-round operation/request counts, status distributions, failures with
redacted curl commands, and the attribution of every failure to one of
``real_defect`` / ``schema_drift`` / ``test_config``.  ``run.py`` overwrites
``result.json`` with its own receipt, so this file deliberately has a different
name.

Safety
------
The database URL comes from ``ADVANCED_PG_URL`` (started by ``run.py``), is
loopback-only and gets a fresh ``advanced_apifuzz_<random>`` database that is
dropped with ``FORCE`` on exit.  Credentials are never printed: the report
redacts Cookie/CSRF/password/token values, and Schemathesis itself filters
known secret fields.  No real port is opened and no external host is contacted.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
import warnings

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BACKEND = ROOT / "backend"
ADVANCED = HERE.parent

for entry in (str(BACKEND), str(ADVANCED)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from support.pg import validate_loopback_url  # noqa: E402

from hooks import (  # noqa: E402
    REAL_DEFECT,
    SCHEMA_DRIFT,
    TEST_CONFIG,
    classify_failure,
    failure_check_name,
    make_expected_status_check,
    redact_curl,
    redact_text,
)

MODE = "apifuzz"
SEED = 4801
READ_MAX_EXAMPLES = 20
WRITE_MAX_EXAMPLES = 10
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
MAX_EXAMPLES_PER_FAILURE = 3

PUBLIC_EXPECTED: dict[tuple[str, str], frozenset[int]] = {
    ("POST", "/users/register"): frozenset({200, 400, 422}),
    ("POST", "/users/login"): frozenset({200, 400, 401, 422}),
}
ANONYMOUS_PROTECTED = frozenset({401, 422})
WRONG_ROLE = frozenset({403})

# Hand-written from docs/REQUIREMENTS.md (FP-AUTH-3 / FP-SEC-1) and SPEC.md
# "API Routes or Server Actions".  The candidate/employer resources in the
# fuzzing rounds are created by the fixture; path UUIDs are random, so 404/403/
# 422 are the expected outcomes for the synthetic identifiers.
CANDIDATE_EXPECTED: dict[tuple[str, str], frozenset[int]] = {
    ("GET", "/users/me"): frozenset({200}),
    ("GET", "/candidate/profile"): frozenset({200}),
    ("PATCH", "/candidate/profile"): frozenset({200, 409, 422}),
    ("GET", "/candidate/profiles/{candidate_id}"): frozenset({200, 403, 404}),
    ("GET", "/candidate/jobs"): frozenset({200}),
    ("GET", "/candidate/jobs/{job_id}"): frozenset({404}),
    ("POST", "/candidate/jobs/{job_id}/applications"): frozenset({404}),
    ("GET", "/candidate/applications"): frozenset({200}),
    ("GET", "/candidate/applications/{application_id}"): frozenset({404, 403}),
    (
        "GET",
        "/candidate/applications/{application_id}/slots",
    ): frozenset({404, 403, 409}),
    (
        "POST",
        "/candidate/applications/{application_id}/booking",
    ): frozenset({404, 403, 409, 422}),
}
EMPLOYER_EXPECTED: dict[tuple[str, str], frozenset[int]] = {
    ("GET", "/users/me"): frozenset({200}),
    ("GET", "/employer/company"): frozenset({200}),
    ("PATCH", "/employer/company"): frozenset({200, 409, 422}),
    ("GET", "/employer/jobs"): frozenset({200}),
    ("POST", "/employer/jobs"): frozenset({201, 409, 422}),
    ("GET", "/employer/jobs/{job_id}"): frozenset({404}),
    ("PATCH", "/employer/jobs/{job_id}"): frozenset({404, 422}),
    ("DELETE", "/employer/jobs/{job_id}"): frozenset({404, 409}),
    ("GET", "/employer/jobs/{job_id}/applications"): frozenset({404}),
    (
        "PATCH",
        "/employer/applications/{application_id}/status",
    ): frozenset({404, 422}),
    ("GET", "/employer/interview-slots"): frozenset({200}),
    ("POST", "/employer/interview-slots"): frozenset({201, 422}),
    ("DELETE", "/employer/interview-slots/{slot_id}"): frozenset({404}),
}


class InfrastructureError(RuntimeError):
    """The mode cannot obtain its disposable database or app."""


@dataclass(frozen=True)
class Account:
    """A real account created through the public HTTP API."""

    role: str
    session: str
    csrf: str
    user_id: uuid.UUID

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Cookie": f"session={self.session}",
            "X-CSRF-Token": self.csrf,
        }


@dataclass(frozen=True)
class PlannedOperation:
    operation: object
    expected: frozenset[int]
    note: str = ""
    max_examples: int = READ_MAX_EXAMPLES
    anonymous_protected: bool = False

    @property
    def method(self) -> str:
        return str(self.operation.method).upper()

    @property
    def path(self) -> str:
        return str(self.operation.path)

    @property
    def label(self) -> str:
        return f"{self.method} {self.path}"


@dataclass
class RoundPlan:
    name: str
    account: Account | None
    operations: list[PlannedOperation] = field(default_factory=list)


class FailureStore:
    """Aggregate Schemathesis failures without dropping or merging categories."""

    def __init__(self) -> None:
        self.records: dict[tuple, dict] = {}
        self.total = 0
        self.harness_errors = 0
        self.by_category: dict[str, int] = {}
        self.by_check: dict[str, int] = {}
        self.by_round: dict[str, int] = {}

    def _entry(
        self,
        *,
        round_name: str,
        operation: str,
        status: int | None,
        check: str,
        category: str,
    ) -> dict:
        key = (round_name, operation, status, check, category)
        record = self.records.get(key)
        if record is None:
            record = {
                "round": round_name,
                "operation": operation,
                "status": status,
                "check": check,
                "category": category,
                "count": 0,
                "examples": [],
            }
            self.records[key] = record
        return record

    def add_failure(
        self,
        *,
        round_name: str,
        planned: PlannedOperation,
        status: int,
        failure: BaseException,
        category: str,
        case,
    ) -> None:
        check = failure_check_name(failure)
        record = self._entry(
            round_name=round_name,
            operation=planned.label,
            status=status,
            check=check,
            category=category,
        )
        record["count"] += 1
        record["code"] = getattr(failure, "code", None)
        record["title"] = redact_text(getattr(failure, "title", ""))
        record["checks"] = list(getattr(failure, "checks", ()))
        self.total += 1
        self.by_category[category] = self.by_category.get(category, 0) + 1
        self.by_check[check] = self.by_check.get(check, 0) + 1
        self.by_round[round_name] = self.by_round.get(round_name, 0) + 1
        if len(record["examples"]) < MAX_EXAMPLES_PER_FAILURE:
            record["examples"].append(
                {
                    "message": redact_text(str(failure))[:5000],
                    "curl": _curl_for(case),
                }
            )

    def add_harness_error(
        self,
        *,
        round_name: str,
        operation: str,
        message: object,
        case=None,
    ) -> None:
        self.harness_errors += 1
        record = self._entry(
            round_name=round_name,
            operation=operation,
            status=None,
            check="harness",
            category=TEST_CONFIG,
        )
        record["count"] += 1
        record["code"] = None
        record["title"] = "Harness or transport error"
        record["checks"] = []
        self.total += 1
        self.by_category[TEST_CONFIG] = self.by_category.get(TEST_CONFIG, 0) + 1
        self.by_check["harness"] = self.by_check.get("harness", 0) + 1
        self.by_round[round_name] = self.by_round.get(round_name, 0) + 1
        if len(record["examples"]) < MAX_EXAMPLES_PER_FAILURE:
            record["examples"].append(
                {
                    "message": redact_text(str(message))[:5000],
                    "curl": _curl_for(case),
                }
            )

    def category_count(self, category: str) -> int:
        return self.by_category.get(category, 0)

    def as_list(self) -> list[dict]:
        return [
            self.records[key]
            for key in sorted(
                self.records,
                key=lambda item: (
                    str(item[0]),
                    str(item[1]),
                    -1 if item[2] is None else item[2],
                    str(item[3]),
                    str(item[4]),
                ),
            )
        ]


def _curl_for(case) -> str:
    if case is None:
        return ""
    try:
        command = case.as_curl_command()
    except Exception as exc:  # pragma: no cover - defensive
        return f"<curl unavailable: {type(exc).__name__}>"
    return redact_curl(command)


def _git(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.strip()


def _prepare_out(value: Path | None) -> Path:
    if value is None:
        env = os.environ.get("ADVANCED_OUT")
        if env:
            value = Path(env)
    if value is None:
        value = Path(tempfile.mkdtemp(prefix="csc4801-apifuzz-"))
    out = value.expanduser().resolve()
    if out == ROOT or out.is_relative_to(ROOT):
        raise SystemExit(
            f"--out must be outside the checkout: {out}; reports can contain "
            "synthetic session tokens"
        )
    (out / MODE).mkdir(parents=True, exist_ok=True)
    (out / "temp").mkdir(parents=True, exist_ok=True)
    return out


def _effective_cap(cli_value: int | None) -> int | None:
    raw = cli_value
    if raw is None:
        env = os.environ.get("ADVANCED_MAX_EXAMPLES")
        if env:
            try:
                raw = int(env)
            except ValueError as exc:
                raise SystemExit(
                    "ADVANCED_MAX_EXAMPLES must be a positive integer"
                ) from exc
    if raw is None:
        return None
    if raw < 1:
        raise SystemExit("max examples must be a positive integer")
    return raw


def _create_database(pg_url: str) -> tuple[object, str, str, object]:
    """Create one throwaway database and return (admin engine, name, url, source)."""

    validate_loopback_url(pg_url)
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from sqlmodel import create_engine

    source = make_url(pg_url)
    name = f"advanced_apifuzz_{uuid.uuid4().hex[:12]}"
    admin = create_engine(
        source.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    database_url = source.set(database=name).render_as_string(
        hide_password=False
    )
    return admin, name, database_url, source


def _migrate(database_url: str) -> None:
    os.environ["APP_NAME"] = "P8 API property fuzzing"
    os.environ["COOKIE_SECURE"] = "false"
    os.environ["DATABASE_URL"] = database_url

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")


def _import_app():
    from app.db.session import engine
    from app.main import app

    return app, engine


def _make_accounts(app) -> dict[str, Account]:
    """Register one real candidate and one real employer with profiles."""

    from fastapi.testclient import TestClient

    accounts: dict[str, Account] = {}
    with TestClient(app) as client:
        for role in ("candidate", "employer"):
            response = client.post(
                "/users/register",
                json={
                    "email": f"{uuid.uuid4().hex}@example.com",
                    "password": "p8-fuzz-local-only",
                    "role": role,
                },
            )
            assert response.status_code == 200, response.text
            body = response.json()
            session = response.cookies["session"]
            csrf = response.cookies["csrf_token"]
            headers = {
                "Cookie": f"session={session}",
                "X-CSRF-Token": csrf,
            }
            payload = (
                {"display_name": "P8 Candidate", "skills": ["python"]}
                if role == "candidate"
                else {"company_name": "P8 Company"}
            )
            saved = client.post(
                f"/users/{role}/profile", headers=headers, json=payload
            )
            assert saved.status_code == 201, saved.text
            client.cookies.clear()
            accounts[role] = Account(
                role=role,
                session=session,
                csrf=csrf,
                user_id=uuid.UUID(body["user"]["id"]),
            )
    return accounts


def _load_schema(app):
    import schemathesis

    schema = schemathesis.openapi.from_asgi("/openapi.json", app)
    # An application exception must become an observable 500 so the
    # not_a_server_error check can report it instead of the harness crashing.
    schema.raise_app_exceptions = False
    operations = []
    errors = []
    for result in schema.get_all_operations():
        try:
            operations.append(result.ok())
        except Exception as exc:  # Err result
            try:
                errors.append(str(result.err()))
            except Exception:
                errors.append(f"{type(exc).__name__}: {exc}")
    operations.sort(key=lambda item: (item.path, str(item.method)))
    return schema, operations, errors


def _max_examples_for(method: str, cap: int | None) -> int:
    base = WRITE_MAX_EXAMPLES if method in UNSAFE_METHODS else READ_MAX_EXAMPLES
    return min(base, cap) if cap is not None else base


def _plan_rounds(
    operations: list, cap: int | None
) -> tuple[list[RoundPlan], list[str]]:
    errors: list[str] = []
    anonymous: list[PlannedOperation] = []
    candidate: list[PlannedOperation] = []
    employer: list[PlannedOperation] = []

    for operation in operations:
        method = str(operation.method).upper()
        path = str(operation.path)
        key = (method, path)
        if key in PUBLIC_EXPECTED:
            anonymous.append(
                PlannedOperation(
                    operation=operation,
                    expected=PUBLIC_EXPECTED[key],
                    max_examples=_max_examples_for(method, cap),
                )
            )
        else:
            anonymous.append(
                PlannedOperation(
                    operation=operation,
                    expected=ANONYMOUS_PROTECTED,
                    note="401 expected; 422 is recorded if body validation runs before authentication",
                    max_examples=_max_examples_for(method, cap),
                    anonymous_protected=True,
                )
            )

        if path == "/users/me" or path.startswith("/candidate/"):
            expected = CANDIDATE_EXPECTED.get(key)
            if expected is None:
                errors.append(f"no candidate expectation for {method} {path}")
            else:
                candidate.append(
                    PlannedOperation(
                        operation=operation,
                        expected=expected,
                        max_examples=_max_examples_for(method, cap),
                    )
                )
        elif path.startswith("/employer/"):
            candidate.append(
                PlannedOperation(
                    operation=operation,
                    expected=WRONG_ROLE,
                    note="candidate credentials must not reach employer operations",
                    max_examples=_max_examples_for(method, cap),
                )
            )

        if path == "/users/me" or path.startswith("/employer/"):
            expected = EMPLOYER_EXPECTED.get(key)
            if expected is None:
                errors.append(f"no employer expectation for {method} {path}")
            else:
                employer.append(
                    PlannedOperation(
                        operation=operation,
                        expected=expected,
                        max_examples=_max_examples_for(method, cap),
                    )
                )
        elif path.startswith("/candidate/"):
            employer.append(
                PlannedOperation(
                    operation=operation,
                    expected=WRONG_ROLE,
                    note="employer credentials must not reach candidate operations",
                    max_examples=_max_examples_for(method, cap),
                )
            )

    plans = [
        RoundPlan(name="anonymous", account=None, operations=anonymous),
        RoundPlan(name="candidate", account=None, operations=candidate),
        RoundPlan(name="employer", account=None, operations=employer),
    ]
    return plans, errors


def _auth_kwargs(account: Account | None) -> dict:
    if account is None:
        return {}
    return {
        "cookies": {"session": account.session},
        "headers": {"X-CSRF-Token": account.csrf},
    }


def _status_counts(counts: dict[int, int]) -> dict[str, int]:
    return {str(code): counts[code] for code in sorted(counts)}


def _run_operation(
    *,
    round_name: str,
    planned: PlannedOperation,
    account: Account | None,
    store: FailureStore,
    checks: list,
) -> dict:
    from hypothesis import HealthCheck, given, settings
    from schemathesis.core.failures import FailureGroup

    operation = planned.operation
    expected_check = make_expected_status_check(
        planned.expected, label=planned.label
    )
    statuses: dict[int, int] = {}
    requests = 0
    call_errors = 0
    validation_before_auth: dict[str, int] = {}
    started = time.monotonic()

    def execute(case):
        nonlocal requests, call_errors
        try:
            response = case.call()
        except Exception as exc:
            call_errors += 1
            store.add_harness_error(
                round_name=round_name,
                operation=planned.label,
                message=f"{type(exc).__name__}: {exc}",
                case=case,
            )
            return
        requests += 1
        code = int(response.status_code)
        statuses[code] = statuses.get(code, 0) + 1
        if (
            planned.anonymous_protected
            and code == 422
            and round_name == "anonymous"
        ):
            key = "422-before-auth"
            validation_before_auth[key] = validation_before_auth.get(key, 0) + 1
        try:
            case.validate_response(
                response,
                checks=checks,
                additional_checks=[expected_check],
            )
        except FailureGroup as group:
            for failure in group.exceptions:
                category = classify_failure(
                    failure,
                    status_code=code,
                    expected=planned.expected,
                )
                store.add_failure(
                    round_name=round_name,
                    planned=planned,
                    status=code,
                    failure=failure,
                    category=category,
                    case=case,
                )
        except Exception as exc:
            call_errors += 1
            store.add_harness_error(
                round_name=round_name,
                operation=planned.label,
                message=f"response validation raised {type(exc).__name__}: {exc}",
                case=case,
            )

    strategy_ok = True
    try:
        strategy = operation.as_strategy(**_auth_kwargs(account))
        wrapped = settings(
            max_examples=planned.max_examples,
            derandomize=True,
            database=None,
            deadline=None,
            report_multiple_bugs=False,
            print_blob=False,
            suppress_health_check=[
                HealthCheck.too_slow,
                HealthCheck.filter_too_much,
                HealthCheck.data_too_large,
                HealthCheck.large_base_example,
            ],
        )(given(strategy)(execute))
        wrapped()
    except Exception as exc:
        strategy_ok = False
        store.add_harness_error(
            round_name=round_name,
            operation=planned.label,
            message=f"strategy/generation failed: {type(exc).__name__}: {exc}",
        )

    return {
        "operation": planned.label,
        "expected_statuses": sorted(planned.expected),
        "max_examples": planned.max_examples,
        "requests": requests,
        "call_errors": call_errors,
        "status_counts": _status_counts(statuses),
        "validation_before_auth": validation_before_auth,
        "strategy_ok": strategy_ok,
        "seconds": round(time.monotonic() - started, 3),
    }


def _run_round(
    *,
    plan: RoundPlan,
    account: Account | None,
    store: FailureStore,
    checks: list,
) -> dict:
    started = time.monotonic()
    operation_reports = []
    total_requests = 0
    total_call_errors = 0
    statuses: dict[int, int] = {}
    before_auth: dict[str, int] = {}
    for planned in plan.operations:
        result = _run_operation(
            round_name=plan.name,
            planned=planned,
            account=account,
            store=store,
            checks=checks,
        )
        operation_reports.append(result)
        total_requests += result["requests"]
        total_call_errors += result["call_errors"]
        for code, count in result["status_counts"].items():
            statuses[int(code)] = statuses.get(int(code), 0) + count
        for reason, count in result["validation_before_auth"].items():
            before_auth[reason] = before_auth.get(reason, 0) + count

    return {
        "round": plan.name,
        "authenticated_role": account.role if account else None,
        "operation_count": len(plan.operations),
        "operations_with_requests": sum(
            1 for report in operation_reports if report["requests"]
        ),
        "requests": total_requests,
        "call_errors": total_call_errors,
        "status_counts": _status_counts(statuses),
        "validation_before_auth": before_auth,
        "operations": operation_reports,
        "seconds": round(time.monotonic() - started, 3),
    }


def _selfcheck(
    *,
    app,
    engine,
    schema,
    operations: list,
    accounts: dict[str, Account],
    store: FailureStore,
) -> dict:
    """Inject three controlled regressions and prove the oracles go red."""

    from hypothesis import HealthCheck, given, settings
    from requests import Request, Response
    from schemathesis.checks import not_a_server_error
    from schemathesis.core.failures import (
        CustomFailure,
        FailureGroup,
        ServerError,
    )
    from schemathesis.openapi.checks import JsonSchemaError, UndefinedStatusCode
    from schemathesis.specs.openapi.checks import status_code_conformance
    from sqlmodel import Session

    from app.employer import router as employer_router
    from app.users.model import User

    by_key = {
        (str(operation.method).upper(), str(operation.path)): operation
        for operation in operations
    }
    required = {
        "employer_jobs": ("GET", "/employer/jobs"),
        "me": ("GET", "/users/me"),
    }
    missing = [key for key in required.values() if key not in by_key]
    if missing:
        store.add_harness_error(
            round_name="selfcheck",
            operation="load operations",
            message=f"self-check cannot find operations {missing}",
        )
        return {"ok": False, "reason": "missing operations", "missing": missing}

    candidate = accounts["candidate"]
    employer = accounts["employer"]
    with Session(engine) as session:
        candidate_user = session.get(User, candidate.user_id)
        employer_user = session.get(User, employer.user_id)
    if candidate_user is None or employer_user is None:
        store.add_harness_error(
            round_name="selfcheck",
            operation="load accounts",
            message="self-check could not reload the synthetic accounts",
        )
        return {"ok": False, "reason": "missing accounts"}

    settings_obj = settings(
        max_examples=1,
        derandomize=True,
        database=None,
        deadline=None,
        suppress_health_check=list(HealthCheck),
    )
    results: dict[str, dict] = {}
    ok = True

    def build_case(operation, account: Account):
        strategy = operation.as_strategy(**_auth_kwargs(account))
        holder = {}

        @settings_obj
        @given(strategy)
        def draw(case):
            holder.setdefault("case", case)

        draw()
        return holder["case"]

    # 1. A candidate must not receive 200 from an employer-only endpoint.
    employer_jobs = by_key[required["employer_jobs"]]
    dependency = employer_router.require_employer
    original_list_my_jobs = employer_router.service.list_my_jobs
    app.dependency_overrides[dependency] = lambda: candidate_user
    employer_router.service.list_my_jobs = lambda session, user: []
    try:
        case = build_case(employer_jobs, candidate)
        response = case.call()
        detected = False
        try:
            case.validate_response(
                response,
                checks=[not_a_server_error],
                additional_checks=[
                    make_expected_status_check(
                        WRONG_ROLE, label="GET /employer/jobs"
                    )
                ],
            )
        except FailureGroup as group:
            detected = any(
                isinstance(failure, CustomFailure)
                for failure in group.exceptions
            )
        results["wrong_role_matrix"] = {
            "injected": "candidate allowed through employer role dependency",
            "status_after_injection": response.status_code,
            "detected": detected,
        }
        ok = ok and detected
    finally:
        employer_router.service.list_my_jobs = original_list_my_jobs
        app.dependency_overrides.pop(dependency, None)

    # 1b. Restore the real dependency and confirm the same case is 403/clean.
    restored = False
    try:
        case = build_case(employer_jobs, candidate)
        response = case.call()
        try:
            case.validate_response(
                response,
                checks=[not_a_server_error],
                additional_checks=[
                    make_expected_status_check(
                        WRONG_ROLE, label="GET /employer/jobs"
                    )
                ],
            )
            restored = response.status_code == 403
        except FailureGroup:
            restored = False
        results["wrong_role_restored"] = {
            "status_after_restore": response.status_code,
            "clean": restored,
        }
        ok = ok and restored
    except Exception as exc:
        results["wrong_role_restored"] = {
            "status_after_restore": None,
            "clean": False,
            "error": redact_text(f"{type(exc).__name__}: {exc}"),
        }
        ok = False

    # 2. An injected unhandled exception must surface as a 500 failure.
    def boom(session, user):
        raise RuntimeError("P8 self-check injected failure")

    employer_router.service.list_my_jobs = boom
    try:
        case = build_case(employer_jobs, employer)
        response = case.call()
        detected = False
        try:
            case.validate_response(response, checks=[not_a_server_error])
        except FailureGroup as group:
            detected = any(
                isinstance(failure, ServerError)
                for failure in group.exceptions
            )
        results["server_error"] = {
            "injected": "RuntimeError in employer list_my_jobs",
            "status_after_injection": response.status_code,
            "detected": detected,
        }
        ok = ok and detected and response.status_code == 500
    finally:
        employer_router.service.list_my_jobs = original_list_my_jobs

    # 2b. Restore and confirm the endpoint answers without a server error again.
    restored = False
    try:
        case = build_case(employer_jobs, employer)
        response = case.call()
        try:
            case.validate_response(response, checks=[not_a_server_error])
            restored = response.status_code == 200
        except FailureGroup:
            restored = False
        results["server_error_restored"] = {
            "status_after_restore": response.status_code,
            "clean": restored,
        }
        ok = ok and restored
    except Exception as exc:
        results["server_error_restored"] = {
            "status_after_restore": None,
            "clean": False,
            "error": redact_text(f"{type(exc).__name__}: {exc}"),
        }
        ok = False

    # 3. A 200 response that does not match the documented schema must be caught.
    schema_detected = False
    try:
        fake = Response()
        fake.status_code = 200
        fake.headers["Content-Type"] = "application/json"
        fake._content = b'{"detail": "not a UserPublic object"}'
        fake.url = "http://testserver/users/me"
        fake.request = Request("GET", fake.url).prepare()
        fake.encoding = "utf-8"
        me = by_key[required["me"]]
        try:
            me.validate_response(fake)
        except FailureGroup as group:
            schema_detected = any(
                isinstance(failure, JsonSchemaError)
                for failure in group.exceptions
            )
        results["response_schema"] = {
            "injected": "HTTP 200 body without UserPublic fields",
            "detected": schema_detected,
        }
        ok = ok and schema_detected
    except Exception as exc:
        results["response_schema"] = {
            "injected": "HTTP 200 body without UserPublic fields",
            "detected": False,
            "error": redact_text(f"{type(exc).__name__}: {exc}"),
        }
        ok = False

    # 4. The status-code drift oracle must see the undocumented 403.
    drift_detected = False
    try:
        case = build_case(employer_jobs, candidate)
        response = case.call()
        try:
            case.validate_response(response, checks=[status_code_conformance])
        except FailureGroup as group:
            drift_detected = any(
                isinstance(failure, UndefinedStatusCode)
                for failure in group.exceptions
            )
        results["status_code_conformance"] = {
            "injected": "candidate receives 403 from an employer-only route",
            "status": response.status_code,
            "detected": drift_detected,
        }
        ok = ok and drift_detected
    except Exception as exc:
        results["status_code_conformance"] = {
            "status": None,
            "detected": False,
            "error": redact_text(f"{type(exc).__name__}: {exc}"),
        }
        ok = False

    if not ok:
        store.add_harness_error(
            round_name="selfcheck",
            operation="self-check",
            message=f"controlled regression was not detected: {json.dumps(results, default=str)}",
        )
    return {"ok": ok, "seed": SEED, "checks": results}


def _environment(admin, engine) -> dict:
    import fastapi
    import hypothesis
    import schemathesis
    import starlette

    version = None
    try:
        from sqlalchemy import text

        with admin.connect() as connection:
            version = connection.execute(text("SELECT version()")).scalar()
    except Exception:
        version = None
    return {
        "python": sys.version,
        "python_executable": sys.executable,
        "fastapi": fastapi.__version__,
        "starlette": starlette.__version__,
        "hypothesis": hypothesis.__version__,
        "schemathesis": schemathesis.__version__,
        "postgres": version,
    }


def _write_report(folder: Path, payload: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        payload, ensure_ascii=True, indent=2, sort_keys=False, default=str
    )
    (folder / "report.json").write_text(text + "\n", encoding="utf-8")


def _round_failures(store: FailureStore, round_name: str) -> list[dict]:
    return [
        record
        for record in store.as_list()
        if record["round"] == round_name
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="P8 bounded OpenAPI property fuzzing (Schemathesis, in-process ASGI).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="artefact directory outside the checkout; defaults to $ADVANCED_OUT",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=None,
        help="lower both example caps (reads 20, writes 10)",
    )
    parser.add_argument(
        "--no-selfcheck",
        action="store_true",
        help="skip the controlled-regression self-check",
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="return 1 when real_defect or schema_drift failures are reported",
    )
    args = parser.parse_args(argv)

    cap = _effective_cap(args.max_examples)
    out = _prepare_out(args.out)
    folder = out / MODE
    started = time.monotonic()
    started_at = datetime.now(timezone.utc)
    warnings.filterwarnings("ignore", message=".*httpx.*deprecated.*")

    report: dict = {
        "schema": "p8.apifuzz/1",
        "mode": MODE,
        "engine": "schemathesis",
        "transport": "in-process ASGI (app.main.app), no network port",
        "seed": SEED,
        "started_at": started_at.isoformat(),
        "max_examples": {
            "reads": min(READ_MAX_EXAMPLES, cap) if cap else READ_MAX_EXAMPLES,
            "writes": min(WRITE_MAX_EXAMPLES, cap) if cap else WRITE_MAX_EXAMPLES,
            "requested_cap": cap,
        },
        "scope": {},
        "rounds": [],
        "failures": [],
        "attribution": {},
        "selfcheck": {},
        "findings": [],
        "outcome": "error",
        "exit_code": 2,
        "error": None,
        "repo": {
            "sha": _git("rev-parse", "HEAD") or "unknown",
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or "unknown",
            "status": _git("status", "--porcelain=v1"),
        },
        "environment": {},
        "seconds": 0.0,
        "finished_at": None,
    }

    admin = None
    name = None
    engine = None
    store = FailureStore()
    exit_code = 0
    try:
        pg_url = os.environ.get("ADVANCED_PG_URL")
        if not pg_url:
            raise InfrastructureError(
                "ADVANCED_PG_URL is not set; run through "
                "python tests/advanced/run.py apifuzz"
            )
        admin, name, database_url, source = _create_database(pg_url)
        _migrate(database_url)
        app, engine = _import_app()
        report["environment"] = _environment(admin, engine)
        accounts = _make_accounts(app)
        schema, operations, schema_errors = _load_schema(app)
        report["scope"] = {
            "openapi_operations": len(operations),
            "schema_errors": schema_errors,
        }
        for error in schema_errors:
            store.add_harness_error(
                round_name="schema",
                operation="load OpenAPI",
                message=error,
            )

        plans, plan_errors = _plan_rounds(operations, cap)
        for error in plan_errors:
            store.add_harness_error(
                round_name="plan",
                operation="expectation matrix",
                message=error,
            )

        from schemathesis.checks import not_a_server_error
        from schemathesis.specs.openapi.checks import (
            response_schema_conformance,
            status_code_conformance,
        )

        checks = [
            not_a_server_error,
            status_code_conformance,
            response_schema_conformance,
        ]

        round_reports = []
        for plan in plans:
            account = None
            if plan.name == "candidate":
                account = accounts["candidate"]
            elif plan.name == "employer":
                account = accounts["employer"]
            result = _run_round(
                plan=plan,
                account=account,
                store=store,
                checks=checks,
            )
            round_reports.append(result)
            print(
                f"[apifuzz] {plan.name}: ops={result['operation_count']} "
                f"requests={result['requests']} "
                f"statuses={result['status_counts']} "
                f"failures={store.by_round.get(plan.name, 0)} "
                f"seconds={result['seconds']}",
                flush=True,
            )

        selfcheck = {"ok": True, "skipped": True}
        if not args.no_selfcheck:
            selfcheck = _selfcheck(
                app=app,
                engine=engine,
                schema=schema,
                operations=operations,
                accounts=accounts,
                store=store,
            )
            selfcheck["skipped"] = False
            print(
                f"[apifuzz] selfcheck: {'passed' if selfcheck['ok'] else 'FAILED'}",
                flush=True,
            )

        report["rounds"] = []
        for result in round_reports:
            result["failures"] = _round_failures(store, result["round"])
            report["rounds"].append(result)

        report["failures"] = store.as_list()
        report["attribution"] = {
            "total": store.total,
            "real_defect": store.category_count(REAL_DEFECT),
            "schema_drift": store.category_count(SCHEMA_DRIFT),
            "test_config": store.category_count(TEST_CONFIG),
            "by_check": dict(sorted(store.by_check.items())),
        }
        report["selfcheck"] = selfcheck

        real_defects = store.category_count(REAL_DEFECT)
        schema_drift = store.category_count(SCHEMA_DRIFT)
        if real_defects:
            findings = ROOT / "docs" / "advanced_testing" / "findings" / "P8.md"
            report["findings"] = [str(findings.relative_to(ROOT))]
        if store.harness_errors:
            report["outcome"] = "error"
            exit_code = 1
        elif real_defects or schema_drift:
            report["outcome"] = "findings"
            exit_code = 1 if args.fail_on_findings else 0
        else:
            report["outcome"] = "clean"
            exit_code = 0

        if real_defects:
            print(
                f"[apifuzz] WARNING: {real_defects} real defect failure(s); "
                f"see docs/advanced_testing/findings/P8.md",
                flush=True,
            )
        if schema_drift:
            print(
                f"[apifuzz] note: {schema_drift} schema-drift failure(s); "
                "responses are required by FP-AUTH-3 but missing from OpenAPI",
                flush=True,
            )
        if store.harness_errors:
            print(
                f"[apifuzz] ERROR: {store.harness_errors} harness/test-config "
                "failure(s); see report.json",
                flush=True,
            )
    except InfrastructureError as exc:
        report["error"] = redact_text(str(exc))
        report["outcome"] = "error"
        exit_code = 2
        print(f"[apifuzz] infrastructure error: {report['error']}", flush=True)
    except Exception as exc:
        report["error"] = redact_text(f"{type(exc).__name__}: {exc}")
        report["outcome"] = "error"
        exit_code = 2
        print(f"[apifuzz] fatal: {report['error']}", flush=True)
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass
        if admin is not None and name is not None:
            try:
                from sqlalchemy import text

                with admin.connect() as connection:
                    connection.execute(
                        text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
                    )
            except Exception:
                pass
            try:
                admin.dispose()
            except Exception:
                pass

    report["exit_code"] = exit_code
    report["seconds"] = round(time.monotonic() - started, 3)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_report(folder, report)
    print(f"[apifuzz] report: {folder / 'report.json'}", flush=True)
    print(
        f"[apifuzz] outcome={report['outcome']} "
        f"real_defect={report['attribution'].get('real_defect', 0)} "
        f"schema_drift={report['attribution'].get('schema_drift', 0)} "
        f"test_config={report['attribution'].get('test_config', 0)} "
        f"exit={exit_code}",
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
