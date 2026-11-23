"""Run historical suites on a new local PG cluster; never use a supplied DB URL."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BROWSER = ROOT / "frontend/tests/specialized"
GROUPS = {
    "slots": ["test_slots_*.py"],
    "booking": ["test_booking_*.py"],
    "matching": [
        "test_applications_jobs.py",
        "test_failure_replays.py",
        "test_matching_*.py",
        "test_replacement_and_text.py",
    ],
    "auth": ["test_auth_*.py"],
    "targeted": ["test_targeted.py"],
    "remaining": ["test_remaining_paths.py"],
    "performance": ["test_performance.py"],
}
BROWSER_SCRIPTS = [
    "auth_browser_checks",
    "auth_browser_focused",
    "probe_existing_helpers",
    "gap_browser_checks",
    "browser_followup",
    "frontend_smoke",
    "frontend_changed_pages",
]


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def npm_command(node):
    cli = Path(node).parent / "node_modules/npm/bin/npm-cli.js"
    return [node, str(cli)] if cli.exists() else [shutil.which("npm") or "npm"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "suite",
        choices=[
            *GROUPS,
            "functional",
            "browser",
            "render",
            "mutation",
            "delivery",
            "all",
        ],
    )
    parser.add_argument("--pg-bin", type=Path, default=os.environ.get("PG_BIN"))
    parser.add_argument(
        "--out",
        type=Path,
        help="Artifacts outside the checkout; default: new system temporary directory",
    )
    parser.add_argument(
        "--browser-script",
        choices=BROWSER_SCRIPTS,
        help="Run one browser module rather than all seven",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Collect backend/app statement/branch coverage; install coverage first",
    )
    args = parser.parse_args()
    out = (args.out or Path(tempfile.mkdtemp(prefix="csc4801-specialized-"))).resolve()
    if out.is_relative_to(ROOT):
        parser.error(
            "Artifacts must be outside the checkout (logs can contain synthetic session tokens)"
        )
    if out.exists() and any(out.iterdir()):
        parser.error(
            "Use a new or empty --out directory; old evidence must not be overwritten"
        )
    out.mkdir(parents=True, exist_ok=True)
    for name in ["logs", "temp", "screenshots"]:
        (out / name).mkdir(exist_ok=True)
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(
            (
                "APP_",
                "DATABASE_",
                "COOKIE_",
                "CSRF_",
                "SESSION_",
                "CANDIDATE_TEST_",
                "EMPLOYER_TEST_",
            )
        ):
            env.pop(key)
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    env.update(
        APP_NAME="Isolated specialized tests",
        COOKIE_SECURE="false",
        PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONHASHSEED="4801",
        PYTHONPATH=os.pathsep.join(
            [str(ROOT / "backend"), str(HERE), env.get("PYTHONPATH", "")]
        ),
        TEMP=str(out / "temp"),
        TMP=str(out / "temp"),
        SLOT_AUDIT_OUT=str(out),
        GAP_OUT=str(out),
        AUDIT_SOURCE_ROOT=str(ROOT),
        CSC4801_ISOLATED_AUDIT="1",
        GAP_SHA=sha,
        UI_OUT=str(out),
        UI_SOURCE=str(ROOT / "frontend"),
        UI_DIST=str(ROOT / "frontend/dist"),
        UI_PYTHON=sys.executable,
        UI_EXPIRE_TOOL=str(HERE / "expire_test_sessions.py"),
    )
    env["DATABASE_URL"] = "postgresql+psycopg://audit@127.0.0.1:1/slots_test"
    for key in ("AUDIT_SOURCE_ROOT", "SLOT_AUDIT_OUT", "GAP_SHA"):
        os.environ[key] = env[key]
    import audit_context as context

    source_files = list((ROOT / "backend/app").rglob("*.py")) + list(
        (ROOT / "frontend/src").rglob("*")
    )
    before = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in source_files
        if p.is_file()
    }
    context.save(
        "manifest.json",
        {
            "sha": sha,
            "suite": args.suite,
            "source_root": str(ROOT),
            "source_file_hashes": before,
            "git_status_at_start": subprocess.check_output(
                ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
            ),
            "docker_excluded": True,
            "repairs": [],
            "browser_scripts": args.browser_script or BROWSER_SCRIPTS,
        },
    )
    print("Artifacts:", out, flush=True)
    steps = []
    started = False
    pg_ctl = None
    try:
        needs_pg = args.suite != "render"
        if needs_pg:
            exe = ".exe" if os.name == "nt" else ""
            bindir = args.pg_bin
            if bindir is None:
                found = shutil.which("initdb" + exe)
                if not found:
                    parser.error(
                        "Install PostgreSQL server tools and set PG_BIN or --pg-bin; no existing service is used"
                    )
                bindir = Path(found).parent
            bindir = Path(bindir).resolve()
            pg_ctl = bindir / ("pg_ctl" + exe)
            data = out / ("pg-data-" + str(port()))
            pg_port = port()
            env["DATABASE_URL"] = (
                f"postgresql+psycopg://audit@127.0.0.1:{pg_port}/slots_test"
            )
            result = context.run(
                "pg-init",
                [
                    bindir / ("initdb" + exe),
                    "-D",
                    data,
                    "-U",
                    "audit",
                    "--auth=trust",
                    "--encoding=UTF8",
                    "--locale=C",
                ],
                env,
                out,
                60,
            )
            if result["exit_code"]:
                return 2
            result = context.run(
                "pg-start",
                [
                    pg_ctl,
                    "-D",
                    data,
                    "-l",
                    out / "postgres.log",
                    "-o",
                    f"-h 127.0.0.1 -p {pg_port} -F -c timezone=Asia/Shanghai",
                    "-w",
                    "start",
                ],
                env,
                out,
                30,
            )
            started = (data / "postmaster.pid").exists()
            if result["exit_code"]:
                return 2
            started = True
            import psycopg

            with psycopg.connect(
                host="127.0.0.1",
                port=pg_port,
                user="audit",
                dbname="postgres",
                autocommit=True,
            ) as db:
                db.execute("CREATE DATABASE slots_test")
            if context.run(
                "migrate", [sys.executable, "-m", "alembic", "upgrade", "head"], env
            )["exit_code"]:
                return 2

        python_suites = (
            list(GROUPS)
            if args.suite == "all"
            else list(GROUPS)[:-1]
            if args.suite == "functional"
            else [args.suite]
            if args.suite in GROUPS
            else []
        )
        for group in python_suites:
            files = sorted({p for pattern in GROUPS[group] for p in HERE.glob(pattern)})
            invocation = [sys.executable, "-m", "pytest"]
            if args.coverage:
                env["COVERAGE_FILE"] = str(out / (".coverage." + group))
                invocation = [
                    sys.executable,
                    "-m",
                    "coverage",
                    "run",
                    "--branch",
                    "--source=" + str(ROOT / "backend/app"),
                    "-m",
                    "pytest",
                ]
            invocation += [
                *files,
                "--rootdir=" + str(ROOT),
                "-q",
                "-ra",
                "--tb=short",
                "-p",
                "no:cacheprovider",
                "--junitxml=" + str(out / (group + ".xml")),
            ]
            steps.append(
                context.run(
                    group, invocation, env, ROOT, 480 if group == "performance" else 240
                )
            )

        if args.suite in {"mutation", "all"}:
            steps.append(
                context.run(
                    "mutation",
                    [sys.executable, HERE / "mutation_checks.py"],
                    env,
                    HERE,
                    240,
                )
            )
        if args.suite in {"delivery", "all"}:
            steps.append(
                context.run(
                    "delivery",
                    [sys.executable, HERE / "delivery_checks.py"],
                    env,
                    timeout=240,
                )
            )
        if args.suite in {"browser", "render", "all"}:
            node = os.environ.get("NODE_BINARY") or shutil.which("node")
            if not node:
                raise RuntimeError(
                    "Install Node and frontend dependencies before browser/render modes"
                )
            if args.suite in {"browser", "all"}:
                build = context.run(
                    "frontend-build",
                    [*npm_command(node), "run", "build"],
                    env,
                    ROOT / "frontend",
                    120,
                )
                if build["exit_code"]:
                    return 2
                api_port = port()
                env["UI_API_PORT"] = str(api_port)
                log = (out / "logs/backend.txt").open("w", encoding="utf-8")
                backend = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(api_port),
                        "--log-level",
                        "warning",
                    ],
                    cwd=ROOT / "backend",
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=context.FLAGS,
                )
                try:
                    for _ in range(200):
                        if backend.poll() is not None:
                            raise RuntimeError(
                                "Backend exited; inspect logs/backend.txt"
                            )
                        try:
                            with urllib.request.urlopen(
                                f"http://127.0.0.1:{api_port}/openapi.json", timeout=1
                            ):
                                break
                        except OSError:
                            time.sleep(0.1)
                    else:
                        raise RuntimeError("Backend startup timeout")
                    for script in (
                        [args.browser_script]
                        if args.browser_script
                        else BROWSER_SCRIPTS
                    ):
                        env.update(UI_STAGE_MODE=script, UI_RESULT_PREFIX=script)
                        steps.append(
                            context.run(
                                script,
                                [node, BROWSER / (script + ".mjs")],
                                env,
                                BROWSER,
                                480,
                            )
                        )
                finally:
                    backend.terminate()
                    try:
                        backend.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        backend.kill()
                        backend.wait(timeout=5)
                    log.close()
                    context.save(
                        "backend-stopped.json", {"stopped": backend.poll() is not None}
                    )
            if args.suite in {"render", "all"}:
                for script in ["render_contracts", "render_all"]:
                    steps.append(
                        context.run(
                            script,
                            [node, BROWSER / (script + ".mjs")],
                            env,
                            BROWSER,
                            90,
                        )
                    )
        return 1 if any(step["exit_code"] for step in steps) else 0
    finally:
        stopped = not started
        if started:
            stopped = (
                context.run(
                    "pg-stop",
                    [pg_ctl, "-D", data, "-m", "fast", "-w", "stop"],
                    env,
                    out,
                    30,
                )["exit_code"]
                == 0
            )
        changes = [
            name
            for name, value in before.items()
            if hashlib.sha256(Path(name).read_bytes()).hexdigest() != value
        ]
        context.save(
            "summary.json",
            {
                "sha": sha,
                "steps": steps,
                "business_source_changes": changes,
                "pg_stopped": stopped,
                "repairs": [],
            },
        )
        if changes or not stopped:
            raise RuntimeError(
                "Source integrity or PG cleanup failed; inspect summary.json"
            )


if __name__ == "__main__":
    raise SystemExit(main())
