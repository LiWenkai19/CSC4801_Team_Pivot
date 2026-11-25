"""Disposable PostgreSQL server for the advanced suites.

``disposable_postgres()`` never talks to a shared database.  It either:

* honours ``ADVANCED_PG_URL`` (the CI one-shot service) after checking that the
  host is loopback and the backend is PostgreSQL, or
* initialises a brand-new cluster with ``initdb`` in a temporary directory,
  listening on a random loopback port, and stops it when the context exits.

The yielded value is a SQLAlchemy URL string.  Creating databases and running
migrations belongs to ``tests/advanced/conftest.py`` so one cluster can serve a
whole mode without leaking state between runs.

Safety rules (see ``tests/advanced/README.md``):

* only ``127.0.0.1`` / ``localhost`` / ``::1`` are accepted;
* the generated cluster listens on loopback only and uses ``trust`` auth;
* credentials are never printed; errors include the host and the PostgreSQL
  log tail, not the URL password.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time

from sqlalchemy.engine import make_url

__all__ = [
    "PostgresUnavailable",
    "disposable_postgres",
    "is_loopback_url",
    "validate_loopback_url",
]

_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class PostgresUnavailable(RuntimeError):
    """Raised when no permissible PostgreSQL server can be started."""


def _exe(name: str) -> str:
    return name + ".exe" if os.name == "nt" else name


def validate_loopback_url(url: str) -> None:
    """Reject anything that is not PostgreSQL on a loopback host.

    Raises ``ValueError`` with a message that never contains the URL's password.
    """

    try:
        parsed = make_url(url)
    except Exception as exc:  # SQLAlchemy raises ArgumentError for malformed URLs
        raise ValueError("ADVANCED_PG_URL is not a valid SQLAlchemy URL") from exc
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("ADVANCED_PG_URL must use the postgresql backend")
    host = (parsed.host or "").lower()
    if host not in _LOOPBACK:
        raise ValueError(
            f"Refusing non-loopback PostgreSQL host {host!r}; "
            "only 127.0.0.1/localhost/::1 are allowed"
        )


def is_loopback_url(url: str) -> bool:
    """Return whether *url* is PostgreSQL on an accepted loopback host."""

    try:
        validate_loopback_url(url)
    except (TypeError, ValueError):
        return False
    return True


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _server_bin(pg_bin: str | Path | None) -> Path:
    value = pg_bin or os.environ.get("PG_BIN")
    if value:
        candidate = Path(value).expanduser()
        if candidate.is_file():
            # Allow both a directory and the path of initdb itself.
            candidate = candidate.parent
    else:
        found = shutil.which(_exe("initdb"))
        if not found:
            raise PostgresUnavailable(
                "PostgreSQL server tools not found. Set PG_BIN (or pass "
                "run.py --pg-bin) to the directory containing initdb/pg_ctl, "
                "or set ADVANCED_PG_URL to a disposable local PostgreSQL "
                "service."
            )
        candidate = Path(found).parent

    candidate = candidate.resolve()
    missing = [
        name
        for name in (_exe("initdb"), _exe("pg_ctl"), _exe("postgres"))
        if not (candidate / name).is_file()
    ]
    if missing:
        raise PostgresUnavailable(
            f"PG_BIN {candidate} is missing {', '.join(missing)}"
        )
    return candidate


def _run(
    args,
    *,
    timeout: float,
    env: dict[str, str],
    log_path: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run a PostgreSQL server tool.

    ``pg_ctl start`` leaves a background ``postgres`` process that inherits the
    parent's stdout handle.  Capturing that with ``subprocess.PIPE`` would wait
    forever for the server to close the pipe (a real hang observed on Windows),
    so callers that spawn a server pass ``log_path`` and the tool output goes to
    a file instead.
    """

    stream = None
    if log_path is None:
        stdout = subprocess.PIPE
    else:
        stream = log_path.open("w", encoding="utf-8", errors="replace")
        stdout = stream
    try:
        return subprocess.run(
            [str(value) for value in args],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
    finally:
        if stream is not None:
            stream.close()


def _log_tail(path: Path, limit: int = 3000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-limit:]
    except OSError:
        return "<no PostgreSQL log>"


def _wait_until_ready(
    host: str, port: int, user: str, timeout: float
) -> None:
    import psycopg

    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(
                host=host,
                port=port,
                user=user,
                dbname="postgres",
                connect_timeout=2,
            ) as connection:
                connection.execute("SELECT 1")
            return
        except Exception as exc:  # server may still be starting
            last_error = exc
            time.sleep(0.1)
    raise PostgresUnavailable(
        f"PostgreSQL did not accept connections on {host}:{port}: {last_error}"
    )


@contextlib.contextmanager
def disposable_postgres(
    pg_bin: str | Path | None = None,
    *,
    startup_timeout: float = 90.0,
):
    """Yield a SQLAlchemy URL for an isolated PostgreSQL server.

    If ``ADVANCED_PG_URL`` is set, that one-shot service is reused as-is and
    nothing is started or stopped.  Otherwise a temporary cluster is created
    and removed.  Only loopback hosts are accepted in either case.
    """

    external = os.environ.get("ADVANCED_PG_URL")
    if external:
        validate_loopback_url(external)
        yield external
        return

    bindir = _server_bin(pg_bin)
    data = Path(tempfile.mkdtemp(prefix="csc4801-advanced-pg-"))
    log = data / "postgres.log"
    port = _free_port()
    user = "advanced"
    env = dict(os.environ)
    env.pop("PGPASSWORD", None)

    initdb = bindir / _exe("initdb")
    pg_ctl = bindir / _exe("pg_ctl")
    started = False
    try:
        result = _run(
            [
                initdb,
                "-D",
                data,
                "-U",
                user,
                "--auth=trust",
                "--encoding=UTF8",
                "--locale=C",
            ],
            timeout=startup_timeout,
            env=env,
        )
        if result.returncode:
            raise PostgresUnavailable(
                f"initdb failed (exit {result.returncode}):\n"
                f"{result.stdout[-3000:]}"
            )

        start_log = data / "pg_ctl-start.log"
        result = _run(
            [
                pg_ctl,
                "-D",
                data,
                "-l",
                log,
                "-o",
                f"-h 127.0.0.1 -p {port}",
                "-w",
                "-t",
                str(int(startup_timeout)),
                "start",
            ],
            timeout=startup_timeout + 30,
            env=env,
            log_path=start_log,
        )
        # Even a failed pg_ctl may have left a process behind; stop it below.
        started = (data / "postmaster.pid").exists()
        if result.returncode:
            raise PostgresUnavailable(
                f"pg_ctl start failed (exit {result.returncode}):\n"
                f"{_log_tail(start_log)}\n{_log_tail(log)}"
            )

        _wait_until_ready("127.0.0.1", port, user, startup_timeout)
        yield f"postgresql+psycopg://{user}@127.0.0.1:{port}/postgres"
    finally:
        if started:
            try:
                stopped = _run(
                    [
                        pg_ctl,
                        "-D",
                        data,
                        "-m",
                        "fast",
                        "-w",
                        "-t",
                        "60",
                        "stop",
                    ],
                    timeout=90,
                    env=env,
                )
                if stopped.returncode:
                    _run(
                        [
                            pg_ctl,
                            "-D",
                            data,
                            "-m",
                            "immediate",
                            "-w",
                            "-t",
                            "30",
                            "stop",
                        ],
                        timeout=60,
                        env=env,
                    )
            except subprocess.TimeoutExpired:
                pass
        shutil.rmtree(data, ignore_errors=True)
