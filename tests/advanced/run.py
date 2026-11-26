"""Run one advanced test mode with isolation and out-of-repo artefacts.

Usage::

    python tests/advanced/run.py <mode> [--out DIR] [--pg-bin DIR] [--max-examples N]

Modes are discovered automatically: every subdirectory of ``tests/advanced/``
except ``support``, ``experiments`` and ``__pycache__`` is a mode.  A mode with
``entry.py`` runs that file as a subprocess; otherwise pytest runs on the
directory.  Empty marker files add behaviour:

* ``SLOW``     - excluded from the ``fast`` pseudo-mode;
* ``NEEDS_DB`` - start a disposable PostgreSQL server for this mode.

Special modes: ``fast`` (all non-SLOW modes), ``all`` (every mode), ``list``
(print discovery and exit).  See ``tests/advanced/README.md`` for the full
contract.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXCLUDED = {"support", "experiments", "__pycache__"}
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def discover_modes() -> dict[str, dict]:
    """Return ``{name: metadata}`` for every mode directory, sorted by name."""

    modes: dict[str, dict] = {}
    for entry in sorted(HERE.iterdir(), key=lambda path: path.name):
        if not entry.is_dir() or entry.name in EXCLUDED:
            continue
        if entry.name.startswith("."):
            continue
        modes[entry.name] = {
            "path": entry,
            "slow": (entry / "SLOW").is_file(),
            "needs_db": (entry / "NEEDS_DB").is_file(),
            "entry": (entry / "entry.py").is_file(),
        }
    return modes


def select_modes(mode: str, modes: dict[str, dict]) -> list[str]:
    if mode == "all":
        return sorted(modes)
    if mode == "fast":
        return sorted(name for name, info in modes.items() if not info["slow"])
    if mode not in modes:
        raise KeyError(mode)
    return [mode]


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


def _prepare_out(value: Path | None, parser: argparse.ArgumentParser) -> Path:
    if value is None:
        out = Path(tempfile.mkdtemp(prefix="csc4801-advanced-")).resolve()
    else:
        out = value.expanduser().resolve()
        if out == ROOT or out.is_relative_to(ROOT):
            parser.error(
                "--out must be outside the checkout: logs and raw test output "
                "can contain synthetic session tokens"
            )
        if out.exists() and not out.is_dir():
            parser.error("--out must be a directory")
        if out.exists() and any(out.iterdir()):
            parser.error(
                "--out must be new or empty; existing evidence is never "
                "overwritten"
            )
        out.mkdir(parents=True, exist_ok=True)
    (out / "temp").mkdir(exist_ok=True)
    return out


def _build_env(out: Path, max_examples: int | None) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(
            ("DATABASE_", "CANDIDATE_TEST_", "EMPLOYER_TEST_")
        )
    }
    env.pop("ADVANCED_MAX_EXAMPLES", None)
    env.pop("ADVANCED_MODE", None)

    pythonpath = [str(ROOT / "backend"), str(HERE)]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    temp = out / "temp"
    env.update(
        {
            "PYTHONHASHSEED": "4801",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": os.pathsep.join(pythonpath),
            "ADVANCED_OUT": str(out),
            "TEMP": str(temp),
            "TMP": str(temp),
            "TMPDIR": str(temp),
        }
    )
    if max_examples is not None:
        env["ADVANCED_MAX_EXAMPLES"] = str(max_examples)
    return env


def _command(
    name: str, info: dict, out: Path
) -> tuple[list[str], Path, Path | None]:
    if info["entry"]:
        return [sys.executable, "entry.py"], info["path"], None
    junit = out / name / "junit.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        str(info["path"]),
        "--rootdir=" + str(ROOT),
        "-q",
        "-ra",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        "--color=no",
        "--junitxml=" + str(junit),
    ]
    return command, ROOT, junit


def _write_json(path: Path, payload) -> None:
    path.write_text(
        json.dumps(
            payload, ensure_ascii=False, indent=2, sort_keys=False, default=str
        )
        + "\n",
        encoding="utf-8",
    )


def run_mode(
    name: str, info: dict, out: Path, env: dict[str, str]
) -> dict:
    folder = out / name
    folder.mkdir(parents=True, exist_ok=True)
    command, cwd, junit = _command(name, info, out)
    log = folder / "run.log"
    mode_env = dict(env)
    mode_env["ADVANCED_MODE"] = name

    started = time.monotonic()
    error: str | None = None
    try:
        with log.open("w", encoding="utf-8") as stream:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=mode_env,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW,
            )
        exit_code = completed.returncode
    except OSError as exc:
        exit_code = 127
        error = f"{type(exc).__name__}: {exc}"
        log.write_text(error + "\n", encoding="utf-8")

    result = {
        "mode": name,
        "kind": "entry" if info["entry"] else "pytest",
        "command": [str(part) for part in command],
        "cwd": str(cwd),
        "exit_code": exit_code,
        "seconds": round(time.monotonic() - started, 3),
        "junit": str(junit) if junit is not None else None,
        "log": str(log),
        "slow": info["slow"],
        "needs_db": info["needs_db"],
        "seed": 4801,
        "max_examples": env.get("ADVANCED_MAX_EXAMPLES"),
    }
    if error is not None:
        result["error"] = error
    _write_json(folder / "result.json", result)
    print(
        f"[{name}] exit={exit_code} seconds={result['seconds']} log={log}",
        flush=True,
    )
    return result


def _write_summary(
    out: Path,
    *,
    sha: str,
    branch: str,
    git_status: str,
    results: list[dict],
    selected: list[str],
    pg: dict,
    max_examples: int | None,
    exit_code: int,
    error: str | None,
) -> None:
    _write_json(
        out / "summary.json",
        {
            "sha": sha,
            "branch": branch,
            "git_status_clean": git_status == "",
            "git_status": git_status,
            "seed": 4801,
            "max_examples": max_examples,
            "python": sys.version,
            "python_executable": sys.executable,
            "argv": sys.argv,
            "modes_requested": selected,
            "pg": pg,
            "results": results,
            "exit_code": exit_code,
            "error": error,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _print_modes(modes: dict[str, dict]) -> None:
    for name, info in modes.items():
        runner = "entry" if info["entry"] else "pytest"
        print(
            f"{name}\tSLOW={'yes' if info['slow'] else 'no'}"
            f"\tNEEDS_DB={'yes' if info['needs_db'] else 'no'}"
            f"\tRUNNER={runner}"
            f"\tFAST={'no' if info['slow'] else 'yes'}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run advanced test modes in isolation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "mode",
        help="mode directory name, or one of: fast, all, list",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="artefacts directory outside the checkout; default: new temp dir",
    )
    parser.add_argument(
        "--pg-bin",
        type=Path,
        default=Path(os.environ["PG_BIN"]) if os.environ.get("PG_BIN") else None,
        help="PostgreSQL server tools directory (default: $PG_BIN or PATH)",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=None,
        help="forwarded to modes as ADVANCED_MAX_EXAMPLES",
    )
    args = parser.parse_args(argv)
    if args.max_examples is not None and args.max_examples < 1:
        parser.error("--max-examples must be a positive integer")

    modes = discover_modes()
    if args.mode == "list":
        _print_modes(modes)
        return 0
    try:
        selected = select_modes(args.mode, modes)
    except KeyError:
        parser.error(
            f"unknown mode {args.mode!r}; choose one of: "
            + ", ".join([*modes, "fast", "all", "list"])
        )

    out = _prepare_out(args.out, parser)
    sha = _git("rev-parse", "HEAD") or "unknown"
    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    git_status = _git("status", "--porcelain=v1")
    env = _build_env(out, args.max_examples)

    external_pg = bool(os.environ.get("ADVANCED_PG_URL"))
    needs_db = any(modes[name]["needs_db"] for name in selected)
    pg = {
        "requested": needs_db,
        "external": external_pg,
        "started": False,
        "mode": "none",
    }
    results: list[dict] = []
    error: str | None = None
    exit_code = 0

    print(f"Artifacts: {out}", flush=True)
    print(f"Commit: {sha} ({branch})", flush=True)
    try:
        if needs_db:
            from support.pg import disposable_postgres

            pg["mode"] = "external" if external_pg else "disposable"
            with disposable_postgres(args.pg_bin) as pg_url:
                env["ADVANCED_PG_URL"] = pg_url
                pg["started"] = not external_pg
                for name in selected:
                    results.append(run_mode(name, modes[name], out, env))
        else:
            for name in selected:
                results.append(run_mode(name, modes[name], out, env))
    except Exception as exc:  # infrastructure failure, not a test failure
        error = f"{type(exc).__name__}: {exc}"
        print(error, file=sys.stderr, flush=True)
        exit_code = 2
    finally:
        if error is None:
            complete = len(results) == len(selected)
            exit_code = (
                0
                if complete
                and all(result["exit_code"] == 0 for result in results)
                else 1
            )
        _write_summary(
            out,
            sha=sha,
            branch=branch,
            git_status=git_status,
            results=results,
            selected=selected,
            pg=pg,
            max_examples=args.max_examples,
            exit_code=exit_code,
            error=error,
        )
        print(f"Summary: {out / 'summary.json'}", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
