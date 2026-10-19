"""Run the local app with two accounts that belong only to this launch."""

import os
import secrets
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

CANDIDATE_EMAIL = "dev-candidate@example.com"
EMPLOYER_EMAIL = "dev-employer@example.com"


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

    from sqlalchemy import delete
    from sqlmodel import Session

    from app.db.session import engine
    from app.users.model import (
        CandidateProfile,
        CandidateSkill,
        EmployerProfile,
        Role,
        User,
    )
    from app.users.schema import UserCreate
    from app.users.service import create_user, get_user_by_email

    if os.name == "nt":
        signal.signal(signal.SIGBREAK, signal.default_int_handler)

    created = []
    processes = []
    result = 0
    accounts = (
        (CANDIDATE_EMAIL, Role.Candidate, secrets.token_urlsafe(18)),
        (EMPLOYER_EMAIL, Role.Employer, secrets.token_urlsafe(18)),
    )
    try:
        with Session(engine) as session:
            for email, _, _ in accounts:
                if get_user_by_email(session, email) is not None:
                    raise RuntimeError(
                        f"{email} already exists; no existing accounts will be changed."
                    )
            for email, role, password in accounts:
                user = create_user(
                    session, UserCreate(email=email, role=role, password=password)
                )
                created.append(user.id)

        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
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
                creationflags=flags,
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
            "\nTemporary accounts (valid only while this window is running):",
            flush=True,
        )
        for email, role, password in accounts:
            print(f"  {role.value}: {email} / {password}", flush=True)
        print("Frontend: http://127.0.0.1:5173/", flush=True)
        print(
            "Press Ctrl+C here to stop both servers and remove the accounts.",
            flush=True,
        )
        print(
            "Forced termination or power loss cannot run automatic cleanup.\n",
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
        if created:
            try:
                with Session(engine) as session:
                    for user_id in created:
                        session.execute(
                            delete(CandidateSkill).where(
                                CandidateSkill.candidate_id == user_id
                            )
                        )
                        session.execute(
                            delete(CandidateProfile).where(
                                CandidateProfile.user_id == user_id
                            )
                        )
                        session.execute(
                            delete(EmployerProfile).where(
                                EmployerProfile.user_id == user_id
                            )
                        )
                        session.execute(delete(User).where(User.id == user_id))
                    session.commit()
                print("Temporary accounts and their profiles removed.", flush=True)
            except Exception as error:
                print(f"WARNING: account cleanup failed: {error}", flush=True)
                print(
                    f"Manually review account IDs: {', '.join(map(str, created))}",
                    flush=True,
                )
                result = 1
        engine.dispose()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
