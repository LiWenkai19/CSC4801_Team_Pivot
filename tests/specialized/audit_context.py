"""Portable execution context shared by specialized test tools."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time

SRC = Path(os.environ["AUDIT_SOURCE_ROOT"])
OUT = Path(os.environ["SLOT_AUDIT_OUT"])
PYTHON = Path(sys.executable)
SHA = os.environ.get("GAP_SHA", "working-tree")
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def save(name, value):
    (OUT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


def run(name, args, env, cwd=None, timeout=240):
    log = OUT / "logs" / (name + ".txt")
    log.parent.mkdir(exist_ok=True)
    start = time.monotonic()
    with log.open("w", encoding="utf-8") as stream:
        try:
            code = subprocess.run(
                list(map(str, args)),
                cwd=cwd or SRC / "backend",
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                creationflags=FLAGS,
                timeout=timeout,
            ).returncode
        except subprocess.TimeoutExpired:
            code = 124
    result = {
        "name": name,
        "args": list(map(str, args)),
        "cwd": str(cwd or SRC / "backend"),
        "exit_code": code,
        "seconds": round(time.monotonic() - start, 3),
        "log": str(log),
    }
    save(name + "-command.json", result)
    print(
        json.dumps({"phase": name, "exit_code": code, "seconds": result["seconds"]}),
        flush=True,
    )
    return result
