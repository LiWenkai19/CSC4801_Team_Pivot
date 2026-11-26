r"""Run the five hand-written mutants against generated and handwritten tests.

The mutants are injected at import time with attribute replacement (see
``mutants.py``); no file under ``backend/app/`` is modified.  Each (mutant, suite)
pair runs in a fresh child process, so test-module imports always see the mutant.

Definition of “killed”: at least one test in the suite fails or errors.
Definition of “survived”: every test in the suite passes.

Usage (from the repository root)::

    python tests/advanced/experiments/llm_blind/mutation/run_mutants.py ^
        --out "$env:TEMP\p10-mutants"

``--out`` must be outside the checkout.  Raw pytest logs and JUnit XML go there;
the matrix is written to ``mutation/results.json``.
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

from mutants import MUTANTS  # noqa: E402

SUITES = {
    "F1": {
        "generated": "tests/advanced/experiments/llm_blind/generated/test_F1.py",
        "handwritten": "tests/unit/test_matching.py",
    },
    "F2": {
        "generated": "tests/advanced/experiments/llm_blind/generated/test_F2.py",
        "handwritten": "tests/unit/test_scheduling.py",
    },
}

BASELINE_SUITES = {
    f"{function}/{suite}": test_file
    for function, targets in SUITES.items()
    for suite, test_file in targets.items()
}


def parse_junit(path: Path):
    cases = []
    for case in ET.parse(path).getroot().iter("testcase"):
        failed = any(case.find(tag) is not None for tag in ("failure", "error"))
        cases.append({"name": case.get("name") or "", "failed": failed})
    return cases


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="artifact directory outside the checkout")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--only", nargs="*", choices=sorted(MUTANTS), default=sorted(MUTANTS)
    )
    args = parser.parse_args(argv)

    out = Path(args.out).resolve()
    try:
        out.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        parser.error("--out must be outside the checkout")
    if out.exists() and any(out.iterdir()):
        parser.error("--out must be new or empty")
    out.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "4801"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "backend"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    results = {
        "experiment": "P10 llm_blind mutation kill matrix",
        "sha": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip(),
        "branch": subprocess.run(
            ["git", "branch", "--show-current"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mutants": {},
        "baseline": {},
        "totals": {},
        "error": None,
    }

    def run_suite(mutant_id, suite_name, test_file, *, label):
        junit = out / f"{label}-{suite_name}.xml"
        log = out / f"{label}-{suite_name}.log"
        command = [
            args.python,
            str(HERE / "apply_and_run.py"),
            "--mutant",
            mutant_id,
            "--test",
            test_file,
            "--junit",
            str(junit),
        ]
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        log.write_text(completed.stdout or "", encoding="utf-8")
        if not junit.is_file():
            raise RuntimeError(f"{label}/{suite_name}: no JUnit XML; see {log}")
        cases = parse_junit(junit)
        failed = [case["name"] for case in cases if case["failed"]]
        return {
            "test_file": test_file,
            "exit_code": completed.returncode,
            "cases": len(cases),
            "failed": len(failed),
            "failed_tests": failed,
            "killed": bool(failed),
            "junit": str(junit),
            "log": str(log),
        }

    infrastructure_error = None
    try:
        for label, test_file in BASELINE_SUITES.items():
            function, suite_name = label.split("/", 1)
            result = run_suite("BASELINE", suite_name, test_file, label=f"baseline-{function}")
            results["baseline"][label] = result
            if result["failed"]:
                raise RuntimeError(
                    f"baseline {label} is not green: {result['failed']} failing test(s)"
                )

        for mutant_id in args.only:
            info = MUTANTS[mutant_id]
            suite_targets = SUITES[info["function"]]
            entry = {
                "description": info["description"],
                "function": info["function"],
                "suites": {},
            }
            for suite_name, test_file in suite_targets.items():
                entry["suites"][suite_name] = run_suite(
                    mutant_id, suite_name, test_file, label=mutant_id
                )
            results["mutants"][mutant_id] = entry
    except Exception as exc:
        infrastructure_error = f"{type(exc).__name__}: {exc}"
        results["error"] = infrastructure_error
    finally:
        results["finished_at"] = datetime.now(timezone.utc).isoformat()

    for suite_name in ("generated", "handwritten"):
        total = 0
        killed = 0
        for entry in results["mutants"].values():
            result = entry["suites"].get(suite_name)
            if result is None:
                continue
            total += 1
            killed += int(result["killed"])
        results["totals"][suite_name] = {"tested": total, "killed": killed}

    results_path = HERE / "results.json"
    results_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "results": str(results_path),
                "out": str(out),
                "totals": results["totals"],
            },
            ensure_ascii=False,
        )
    )
    if infrastructure_error:
        print(infrastructure_error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
