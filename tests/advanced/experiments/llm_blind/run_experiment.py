r"""Run the P10 blind-generated experiment and collect machine-readable results.

The generated test files are frozen in a commit *before* this runner is used.
The runner only executes them and records outcomes; it contains no expected
values and no implementation imports.

Usage (from the repository root, Windows PowerShell example)::

    python tests/advanced/experiments/llm_blind/run_experiment.py ^
        --out "$env:TEMP\p10-llm-blind" ^
        --node-modules "D:\path\to\frontend\node_modules"

``--out`` must be outside the checkout.  The summary is written to
``results.json`` beside this file; raw logs and JUnit XML stay under ``--out``.

Exit code 0 means "the experiment ran and was recorded", even when some generated
tests fail: failures are the experiment's data.  Infrastructure errors (missing
test file, node, pytest, XML) return 2.  Add ``--fail-on-test-failure`` to get 1
when any generated test fails.
"""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
GENERATED = HERE / "generated"
DEFAULT_RESULTS = HERE / "results.json"

FUNCTIONS = {
    "F1": {
        "kind": "pytest",
        "file": GENERATED / "test_F1.py",
        "description": "app.employer.matching.match_score",
    },
    "F2": {
        "kind": "pytest",
        "file": GENERATED / "test_F2.py",
        "description": "app.candidate.service.book",
    },
    "F3": {
        "kind": "node",
        "file": GENERATED / "test_F3.mjs",
        "description": "SkillTagPicker HTML escaping",
    },
}


def _child_text(node, tag):
    child = node.find(tag)
    if child is None:
        return None
    return (child.get("message") or child.text or "").strip() or None


def parse_junit(path: Path):
    tree = ET.parse(path)
    root = tree.getroot()
    cases = []
    for case in root.iter("testcase"):
        status = "passed"
        message = None
        for tag in ("failure", "error", "skipped"):
            if case.find(tag) is not None:
                status = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                message = _child_text(case, tag)
                break
        cases.append(
            {
                "name": case.get("name") or "",
                "classname": case.get("classname") or "",
                "file": case.get("file") or "",
                "seconds": float(case.get("time") or 0.0),
                "status": status,
                "message": message,
            }
        )
    return cases


def run_command(command, *, cwd, env, log_path: Path):
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(completed.stdout or "", encoding="utf-8")
    return completed.returncode


def python_environment(base):
    env = dict(base)
    env["PYTHONHASHSEED"] = "4801"
    env["PYTHONUTF8"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    backend = ROOT / "backend"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(backend), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    env["APP_NAME"] = "LLM blind test experiment"
    env["COOKIE_SECURE"] = "false"
    env["DATABASE_URL"] = (
        "postgresql+psycopg://unit:unit@127.0.0.1:1/unit_not_a_database"
    )
    return env


def find_node_modules(explicit: str | None) -> Path | None:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("P10_NODE_MODULES"):
        candidates.append(Path(os.environ["P10_NODE_MODULES"]))
    candidates.append(ROOT / "frontend" / "node_modules")
    for candidate in candidates:
        if (candidate / "typescript").is_dir() and (candidate / "react").is_dir():
            return candidate.resolve()
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="artifact directory outside the checkout")
    parser.add_argument(
        "--results",
        default=str(DEFAULT_RESULTS),
        help="summary JSON path (default: experiments/llm_blind/results.json)",
    )
    parser.add_argument(
        "--python", default=sys.executable, help="Python interpreter used for pytest"
    )
    parser.add_argument("--node", default=shutil.which("node") or "node")
    parser.add_argument(
        "--node-modules",
        default=None,
        help="frontend/node_modules directory that contains typescript/react",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        choices=sorted(FUNCTIONS),
        default=sorted(FUNCTIONS),
        help="run only these functions",
    )
    parser.add_argument(
        "--fail-on-test-failure",
        action="store_true",
        help="return 1 if any generated test fails",
    )
    args = parser.parse_args(argv)

    out = Path(args.out).resolve()
    checkout = ROOT.resolve()
    try:
        out.relative_to(checkout)
    except ValueError:
        pass
    else:
        parser.error("--out must be outside the checkout")
    if out.exists() and any(out.iterdir()):
        parser.error("--out must be new or empty")
    out.mkdir(parents=True, exist_ok=True)

    if args.node_modules:
        node_modules = Path(args.node_modules).resolve()
        if not node_modules.is_dir():
            parser.error(f"--node-modules does not exist: {node_modules}")
    else:
        node_modules = find_node_modules(None)

    if "F3" in args.only and node_modules is None:
        parser.error(
            "F3 needs a frontend node_modules with typescript/react; "
            "pass --node-modules or install frontend dependencies"
        )

    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True
    ).stdout

    env = python_environment(os.environ)
    if node_modules is not None:
        env["NODE_PATH"] = os.pathsep.join(
            [str(node_modules), env.get("NODE_PATH", "")]
        ).rstrip(os.pathsep)

    results = {
        "experiment": "P10 llm_blind",
        "description": "LLM-generated tests from contracts, generated before implementation review",
        "sha": sha,
        "branch": branch,
        "git_status": status,
        "seed": 4801,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "python_executable": args.python,
        "node": args.node,
        "node_modules": str(node_modules) if node_modules else None,
        "generated_files": {
            key: str(spec["file"].relative_to(ROOT)) for key, spec in FUNCTIONS.items()
        },
        "runs": {},
    }

    infrastructure_error = None
    try:
        for key in args.only:
            spec = FUNCTIONS[key]
            test_file = spec["file"]
            if not test_file.is_file():
                raise FileNotFoundError(f"generated test missing: {test_file}")
            junit = out / f"{key}-junit.xml"
            log = out / f"{key}.log"
            if spec["kind"] == "pytest":
                command = [
                    args.python,
                    "-m",
                    "pytest",
                    str(test_file),
                    "-v",
                    "--rootdir",
                    str(ROOT),
                    "-p",
                    "no:cacheprovider",
                    f"--junitxml={junit}",
                ]
            else:
                command = [
                    args.node,
                    "--test",
                    "--test-reporter=junit",
                    f"--test-reporter-destination={junit}",
                    str(test_file),
                ]
            started = datetime.now(timezone.utc)
            exit_code = run_command(command, cwd=ROOT, env=env, log_path=log)
            seconds = (datetime.now(timezone.utc) - started).total_seconds()
            if not junit.is_file():
                raise RuntimeError(
                    f"{key}: command produced no JUnit XML (exit {exit_code}); see {log}"
                )
            cases = parse_junit(junit)
            passed = sum(case["status"] == "passed" for case in cases)
            failed = sum(case["status"] in {"failed", "error"} for case in cases)
            results["runs"][key] = {
                "function": spec["description"],
                "kind": spec["kind"],
                "test_file": str(test_file.relative_to(ROOT)),
                "command": command,
                "exit_code": exit_code,
                "seconds": round(seconds, 3),
                "junit": str(junit),
                "log": str(log),
                "summary": {
                    "cases": len(cases),
                    "passed": passed,
                    "failed": failed,
                    "skipped": len(cases) - passed - failed,
                },
                "cases": cases,
            }
    except Exception as exc:  # infrastructure, not a test result
        infrastructure_error = f"{type(exc).__name__}: {exc}"
        results["error"] = infrastructure_error
    finally:
        results["finished_at"] = datetime.now(timezone.utc).isoformat()

    results_path = Path(args.results)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    totals = {
        "cases": sum(run["summary"]["cases"] for run in results["runs"].values()),
        "passed": sum(run["summary"]["passed"] for run in results["runs"].values()),
        "failed": sum(run["summary"]["failed"] for run in results["runs"].values()),
    }
    print(json.dumps({"results": str(results_path), "out": str(out), **totals}, ensure_ascii=False))
    if infrastructure_error:
        print(infrastructure_error, file=sys.stderr)
        return 2
    if args.fail_on_test_failure and totals["failed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
