#!/usr/bin/env python
"""P11: branch coverage of ``backend/app`` across four independent suites.

The task brief asks for one coverage number per suite plus a combined number,
so every suite gets its own coverage data file:

======================  =====================================================
group                   what runs
======================  =====================================================
``unit``                ``tests/unit`` (the mandatory suite, same environment
                        as ``tests/run_tests.py``)
``integration``         ``backend/tests`` against the throwaway PostgreSQL
                        supplied through ``ADVANCED_PG_URL``
``stateful``            the P2 Hypothesis state machine
``differential``        the P6 Python-versus-SQL oracles
``intramorphic``        the P9 metamorphic/intramorphic workflows
======================  =====================================================

Every group is executed with::

    python -m coverage run --branch --source=backend/app \
        --data-file=<out>/coverage/.coverage.<group> -m pytest <target>

and then reported with ``coverage json``.  The per-group data files are merged
with the coverage API and written as ``coverage-summary.json`` plus
``coverage.xml`` under ``$ADVANCED_OUT/coverage/``.  Neither file is named
``result.json`` because ``tests/advanced/run.py`` overwrites that name with its
own mode receipt.

The script only reports what it measured.  A red group is still measured and
reported (a failing suite is evidence, not a reason to hide the number), but the
exit code becomes non-zero so ``run.py`` records the failure.

Usage::

    python tests/advanced/run.py coverage [--out DIR] [--max-examples N]

Environment (set by ``run.py``): ``ADVANCED_OUT``, ``ADVANCED_PG_URL``,
``PYTHONPATH``, ``PYTHONHASHSEED=4801``.  A direct invocation is possible when
``ADVANCED_OUT`` and ``ADVANCED_PG_URL`` are already exported.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BACKEND = ROOT / "backend"
ADVANCED = ROOT / "tests" / "advanced"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

MODE = "coverage"
SEED = 4801
SOURCE = "backend/app"

#: Deterministic order; the report uses the same order.
GROUPS = (
    {
        "name": "unit",
        "target": "tests/unit",
        "kind": "unit",
        "timeout": 900,
        "description": "mandatory unit suite (tests/unit)",
    },
    {
        "name": "integration",
        "target": "backend/tests",
        "kind": "integration",
        "timeout": 1800,
        "description": "real PostgreSQL integration suite (backend/tests)",
    },
    {
        "name": "stateful",
        "target": "tests/advanced/stateful",
        "kind": "advanced",
        "timeout": 900,
        "description": "P2 booking lifecycle state machine",
    },
    {
        "name": "differential",
        "target": "tests/advanced/differential",
        "kind": "advanced",
        "timeout": 1200,
        "description": "P6 Python versus SQL differential oracle",
    },
    {
        "name": "intramorphic",
        "target": "tests/advanced/intramorphic",
        "kind": "advanced",
        "timeout": 900,
        "description": "P9 metamorphic and intramorphic workflows",
    },
)

UNIT_ENVIRONMENT = {
    "APP_NAME": "Business unit tests",
    "DATABASE_URL": (
        "postgresql+psycopg://unit:unit@127.0.0.1:1/unit_not_a_database"
    ),
    "COOKIE_SECURE": "false",
}


def _prepare_output() -> Path:
    base = os.environ.get("ADVANCED_OUT")
    if not base:
        raise SystemExit(
            "ADVANCED_OUT is not set; run through "
            "python tests/advanced/run.py coverage"
        )
    folder = Path(base) / MODE
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "work").mkdir(exist_ok=True)
    return folder


def _base_environment() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(
            ("DATABASE_", "CANDIDATE_TEST_", "EMPLOYER_TEST_")
        )
    }
    env.pop("ADVANCED_MODE", None)
    env.pop("ADVANCED_OUT", None)
    env.pop("COVERAGE_FILE", None)
    pythonpath = [str(BACKEND), str(ADVANCED)]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env.update(
        {
            "PYTHONHASHSEED": str(SEED),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": os.pathsep.join(pythonpath),
        }
    )
    return env


def _group_environment(
    group: dict, folder: Path, base: dict[str, str]
) -> dict[str, str]:
    env = dict(base)
    env["ADVANCED_OUT"] = str(folder / "work")
    env["ADVANCED_MODE"] = group["name"]
    if group["kind"] == "unit":
        env.update(UNIT_ENVIRONMENT)
    elif group["kind"] == "integration":
        pg_url = os.environ.get("ADVANCED_PG_URL")
        if not pg_url:
            raise RuntimeError("ADVANCED_PG_URL is not set")
        env["CANDIDATE_TEST_DATABASE_URL"] = pg_url
        env["EMPLOYER_TEST_DATABASE_URL"] = pg_url
    else:
        pg_url = os.environ.get("ADVANCED_PG_URL")
        if not pg_url:
            raise RuntimeError("ADVANCED_PG_URL is not set")
        env["ADVANCED_PG_URL"] = pg_url
    return env


def _junit_counts(path: Path) -> dict:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return {"tests": None, "failures": None, "errors": None, "skipped": None}
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        for key in totals:
            value = suite.get(key)
            totals[key] += int(value) if value is not None else 0
    return totals


def _totals(data: dict) -> dict:
    totals = data.get("totals", {})
    statements = int(totals.get("num_statements", 0))
    covered = int(totals.get("covered_lines", 0))
    branches = int(totals.get("num_branches", 0))
    covered_branches = int(totals.get("covered_branches", 0))
    return {
        "statements": statements,
        "covered_statements": covered,
        "statement_pct": (
            round(100.0 * covered / statements, 2) if statements else 100.0
        ),
        "branches": branches,
        "covered_branches": covered_branches,
        "branch_pct": (
            round(100.0 * covered_branches / branches, 2)
            if branches
            else None
        ),
        "percent_covered": totals.get("percent_covered"),
    }


def _coverage_json(data_file: Path, target: Path) -> dict:
    from coverage import Coverage

    cov = Coverage(data_file=str(data_file))
    cov.load()
    cov.json_report(outfile=str(target), pretty_print=False)
    return json.loads(target.read_text(encoding="utf-8"))


def _run_group(
    group: dict, folder: Path, base: dict[str, str]
) -> dict:
    data_file = folder / f".coverage.{group['name']}"
    junit = folder / f"junit-{group['name']}.xml"
    report = folder / f"{group['name']}-coverage.json"
    log = folder / f"{group['name']}.log"
    command = [
        sys.executable,
        "-m",
        "coverage",
        "run",
        "--branch",
        f"--source={SOURCE}",
        f"--data-file={data_file}",
        "-m",
        "pytest",
        str(ROOT / group["target"]),
        "--rootdir=" + str(ROOT),
        "-q",
        "-ra",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        "--color=no",
        f"--junitxml={junit}",
    ]
    started = time.monotonic()
    error = None
    try:
        env = _group_environment(group, folder, base)
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=group["timeout"],
            creationflags=CREATE_NO_WINDOW,
        )
        exit_code = completed.returncode
        output = (completed.stdout or "") + (completed.stderr or "")
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        output = (
            f"timeout after {group['timeout']} seconds\n"
            + stdout
            + stderr
        )
        error = f"TimeoutExpired: {group['timeout']}s"
    except OSError as exc:
        exit_code = 127
        output = f"{type(exc).__name__}: {exc}\n"
        error = output.strip()
    log.write_text(output, encoding="utf-8")

    seconds = round(time.monotonic() - started, 3)
    if data_file.is_file():
        try:
            data = _coverage_json(data_file, report)
            summary = _totals(data)
            coverage_error = None
        except Exception as exc:  # coverage data unreadable
            summary = None
            coverage_error = f"{type(exc).__name__}: {exc}"
    else:
        summary = None
        coverage_error = "coverage data file was not produced"

    record = {
        "name": group["name"],
        "description": group["description"],
        "target": group["target"],
        "kind": group["kind"],
        "command": [str(part) for part in command],
        "exit_code": exit_code,
        "seconds": seconds,
        "junit": str(junit),
        "log": str(log),
        "data_file": str(data_file) if data_file.is_file() else None,
        "coverage_json": str(report) if report.is_file() else None,
        "counts": _junit_counts(junit),
        "summary": summary,
        "coverage_error": coverage_error,
    }
    if error is not None:
        record["error"] = error
    print(
        f"[coverage] {group['name']}: exit={exit_code} "
        f"seconds={seconds} "
        f"statement={summary['statement_pct'] if summary else 'n/a'}% "
        f"branch={summary['branch_pct'] if summary else 'n/a'}%",
        flush=True,
    )
    return record


def _relativise_xml(path: Path) -> None:
    """Replace this checkout's absolute prefix with relative paths.

    ``coverage.xml`` is an artefact people download from CI; leaving the
    runner's absolute workspace path in it makes the file machine-specific.
    The data files themselves stay absolute so the coverage API can resolve
    them regardless of the process working directory.
    """

    text = path.read_text(encoding="utf-8")
    root_posix = ROOT.as_posix()
    text = text.replace(root_posix + "/", "")
    text = text.replace(root_posix.replace("/", ".") + ".", "")
    path.write_text(text, encoding="utf-8")


def _combine(
    folder: Path, groups: list[dict]
) -> tuple[dict | None, str | None]:
    from coverage import Coverage

    data_files = [
        Path(group["data_file"])
        for group in groups
        if group.get("data_file")
    ]
    if not data_files:
        return None, "no coverage data files were produced"
    combined_file = folder / ".coverage"
    if combined_file.exists():
        combined_file.unlink()
    try:
        cov = Coverage(data_file=str(combined_file))
        cov.combine([str(path) for path in data_files], keep=True)
        cov.save()
        cov.json_report(
            outfile=str(folder / "coverage-total.json"), pretty_print=False
        )
        cov.xml_report(outfile=str(folder / "coverage.xml"))
        _relativise_xml(folder / "coverage.xml")
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    total = json.loads(
        (folder / "coverage-total.json").read_text(encoding="utf-8")
    )
    return _totals(total), None


def main(argv: list[str] | None = None) -> int:
    del argv  # run.py passes positional mode arguments elsewhere
    # Coverage stores relative paths; report them from the project root.
    os.chdir(ROOT)
    folder = _prepare_output()
    base = _base_environment()
    started = time.monotonic()
    started_at = datetime.now(timezone.utc)
    groups: list[dict] = []
    infrastructure_error = None
    try:
        for group in GROUPS:
            groups.append(_run_group(group, folder, base))
    except Exception as exc:  # e.g. missing ADVANCED_PG_URL
        infrastructure_error = f"{type(exc).__name__}: {exc}"
        print(infrastructure_error, file=sys.stderr, flush=True)

    combined, combine_error = (
        _combine(folder, groups) if groups else (None, "no groups ran")
    )
    unit = next((group for group in groups if group["name"] == "unit"), None)
    unit_branch = unit["summary"]["branch_pct"] if unit and unit["summary"] else None
    unit_gate = (
        int(unit_branch // 5) * 5 if unit_branch is not None else None
    )
    failed = [group["name"] for group in groups if group["exit_code"] != 0]
    if infrastructure_error is not None or combine_error is not None:
        exit_code = 2
    elif failed:
        exit_code = 1
    else:
        exit_code = 0

    payload = {
        "schema": "p11.coverage/1",
        "mode": MODE,
        "seed": SEED,
        "source": SOURCE,
        "branch": True,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "seconds": round(time.monotonic() - started, 3),
        "python": sys.version,
        "python_executable": sys.executable,
        "unit_branch_gate": unit_gate,
        "groups": groups,
        "combined": combined,
        "combine_error": combine_error,
        "failed_groups": failed,
        "exit_code": exit_code,
        "error": infrastructure_error,
    }
    (folder / "coverage-summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        f"[coverage] combined statement="
        f"{combined['statement_pct'] if combined else 'n/a'}% "
        f"branch={combined['branch_pct'] if combined else 'n/a'}% "
        f"unit_branch_gate={unit_gate}",
        flush=True,
    )
    print(f"[coverage] summary: {folder / 'coverage-summary.json'}", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
