"""Run the local app with reusable development accounts."""

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
FRONTEND = ROOT / "frontend"
sys.path.insert(0, str(BACKEND))

# Keep these separate from the old accounts that used random passwords.
CANDIDATE_EMAIL = "local-candidate@example.com"
EMPLOYER_EMAIL = "local-employer@example.com"
DEV_PASSWORD = "dev-local-only"


def port_available(port: int) -> bool:
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            print(
                f"WARNING: could not stop process tree {process.pid}: {error}",
                flush=True,
            )
            process.terminate()
    else:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        print(f"WARNING: process {process.pid} did not stop.", flush=True)


def main() -> int:
    if not (BACKEND / ".env").is_file() and not os.environ.get("DATABASE_URL"):
        print("Missing backend/.env or DATABASE_URL; configure the backend first.")
        return 1
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        print("npm is unavailable.")
        return 1
    if (
        not (FRONTEND / "node_modules" / ".bin" / "vite.cmd").exists()
        and os.name == "nt"
    ):
        print("Install frontend dependencies with npm install first.")
        return 1
    for port in (8000, 5173):
        if not port_available(port):
            print(f"Port {port} is already in use; no accounts were created.")
            return 1

    from sqlalchemy.exc import IntegrityError
    from sqlmodel import Session

    from app.db.session import engine
    from app.users.model import Role
    from app.users.schema import UserCreate
    from app.users.service import create_user, get_user_by_email

    if os.name == "nt":
        signal.signal(signal.SIGBREAK, signal.default_int_handler)

    processes = []
    result = 0
    accounts = (
        (CANDIDATE_EMAIL, Role.Candidate),
        (EMPLOYER_EMAIL, Role.Employer),
    )
    try:
        with Session(engine) as session:
            for email, role in accounts:
                if get_user_by_email(session, email) is not None:
                    continue
                try:
                    create_user(
                        session,
                        UserCreate(email=email, role=role, password=DEV_PASSWORD),
                    )
                except (IntegrityError, ValueError):
                    # Another launch may have created the account in the meantime.
                    session.rollback()
                    if get_user_by_email(session, email) is None:
                        raise

        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        use_reload_console = (
            os.name == "nt" and os.environ.get("UVICORN_RELOAD") == "true"
        )
        backend_flags = flags
        backend_startup = None
        if use_reload_console:
            # Uvicorn uses Ctrl+C to stop its worker on reload. Give it its own
            # console so that signal can reach the worker without stopping the launcher.
            backend_flags = subprocess.CREATE_NEW_CONSOLE
            backend_startup = subprocess.STARTUPINFO()
            backend_startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            backend_startup.wShowWindow = subprocess.SW_HIDE

        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
                cwd=BACKEND,
                creationflags=backend_flags,
                startupinfo=backend_startup,
                stdin=subprocess.DEVNULL if use_reload_console else None,
                stdout=sys.stdout if use_reload_console else None,
                stderr=sys.stderr if use_reload_console else None,
            )
        )
        processes.append(
            subprocess.Popen(
                [
                    npm,
                    "run",
                    "dev",
                    "--",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "5173",
                    "--strictPort",
                ],
                cwd=FRONTEND,
                creationflags=flags,
            )
        )
        print(
            "\nLocal development accounts (see the start.bat account guide):",
            flush=True,
        )
        for email, role in accounts:
            print(f"  {role.value}: {email}", flush=True)
        print("Frontend: http://127.0.0.1:5173/", flush=True)
        print(
            "Press Ctrl+C here to stop both servers. Development accounts persist.\n",
            flush=True,
        )
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        print("A server exited; stopping the other server.", flush=True)
        result = 1
    except KeyboardInterrupt:
        print("\nStopping servers...", flush=True)
    except Exception as error:
        print(f"Startup failed: {error}", flush=True)
        result = 1
    finally:
        for process in reversed(processes):
            stop_process(process)
        engine.dispose()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
