#!/usr/bin/env python
"""P7: quantify how many defects the mandated unit suite can detect.

Design
------
``mutmut==3.7.0`` is pinned for the advanced suite (``tests/advanced/requirements.txt``)
because newer releases need ``click>=8.4.2``.  That version refuses to start on
native Windows::

    To run mutmut on Windows, please use the WSL.
    Native windows support is tracked in https://github.com/boxed/mutmut/issues/397

mutmut 3.x is built on ``os.fork()`` and ``resource.setrlimit()``, so the refusal
is structural rather than cosmetic, and this checkout has no Linux environment
that carries the project's dependency closure (the only WSL distribution is
Docker Desktop's paused VM).  This entry point therefore ships the *documented
fallback* from the task brief: an AST mutator written on top of :mod:`ast`.
``setup.cfg`` next to this file carries the equivalent mutmut configuration so a
POSIX checkout can reproduce the run with ``python -m mutmut run``.

Everything runs inside a throw-away copy of ``backend/`` under
``$ADVANCED_OUT/mutation/work/``.  The repository is only ever read, and a
SHA-256 snapshot of ``backend/app`` (taken before and after the run) proves it:
any difference aborts with a non-zero exit code.

Mutant semantics follow mutmut's vocabulary:

============  ==================================================================
``killed``    the unit suite fails, so the suite detected the defect
``survived``  the unit suite still passes, so the suite missed the defect
``timeout``   the mutant did not finish within ``--timeout`` seconds
``suspicious``the mutant could not be judged (module no longer imports, pytest
              collection error, harness error) - never counted as a kill
============  ==================================================================

Outputs, all under ``$ADVANCED_OUT/mutation/``:

``result.json``
    Detailed machine-readable report (totals, per-file score, survivors,
    suspicious mutants, SHA-256 guard, timings).
``mutation-result.json``
    Identical copy of the above.  ``tests/advanced/run.py`` overwrites
    ``result.json`` with its own mode receipt after this process exits, so this
    copy is the durable one when the mode runs through the runner.
``mutants.json``
    Every mutant the engine generated (id, kind, line, replacement).
``survivors/<id>.diff``
    One unified diff per surviving mutant.
``mutmut-probe.log``
    Evidence for why mutmut itself is not driving this run.
``work/``
    Disposable copies the tests executed in (pristine source, per-worker trees).

Usage::

    python tests/advanced/run.py mutation [--out DIR]
    python tests/advanced/mutation/entry.py --out DIR [--jobs N] [--timeout S]

Extra flags exist for development only (``--list-mutants``, ``--max-mutants``,
``--only``, ``--selfcheck``); the acceptance command needs none of them.
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BACKEND = ROOT / "backend"
REPO_TESTS = ROOT / "tests"
FRONTEND = ROOT / "frontend"

MODE = "mutation"
TEST_TARGET = "tests/unit"
#: Rendered by the disabled React suite; needed because ``tests/unit/test_rendering.py``
#: shells out to Node.  It cannot kill a Python mutant but keeping it makes the
#: measured suite byte-identical to the mandated ``tests/unit`` command.
NODE_DEPENDENT_TEST = "tests/unit/test_rendering.py"

DEFAULT_TIMEOUT = 30.0
SEED = 4801
UNIT_DATABASE_URL = "postgresql+psycopg://unit:unit@127.0.0.1:1/unit_not_a_database"

#: Mutation scope, in report order.  Codes keep mutant ids short and stable.
TARGET_FILES = (
    ("em", "app/employer/matching.py"),
    ("us", "app/users/service.py"),
    ("ca", "app/candidate/service.py"),
    ("es", "app/employer/service.py"),
    ("iv", "app/interview/service.py"),
)

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# --------------------------------------------------------------------------- #
# source text helpers
# --------------------------------------------------------------------------- #


def _detect_column_units() -> str:
    """Return ``"bytes"`` or ``"chars"`` depending on this interpreter's AST.

    CPython reports ``col_offset`` as a UTF-8 byte offset; the probe keeps the
    engine correct on an interpreter that reports code points instead.
    """

    sample = "中文 = 1\n"
    node = ast.parse(sample).body[0].value
    if node.col_offset == 9:  # 3 chars * 3 bytes + " = "
        return "bytes"
    if node.col_offset == 5:  # len("中文") + len(" = ")
        return "chars"
    raise RuntimeError(f"cannot determine AST column units: col_offset={node.col_offset}")


COLUMN_UNITS = _detect_column_units()


class Source:
    """Normalised module text plus the machinery to slice nodes out of it."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.lines = text.splitlines(keepends=True)
        self.starts: list[int] = []
        offset = 0
        for line in self.lines:
            self.starts.append(offset)
            offset += len(line)

    def offset(self, lineno: int, col: int) -> int:
        line = self.lines[lineno - 1]
        if COLUMN_UNITS == "bytes":
            prefix = line.encode("utf-8")[:col].decode("utf-8", "ignore")
            return self.starts[lineno - 1] + len(prefix)
        return self.starts[lineno - 1] + col

    def span(self, node: ast.AST) -> tuple[int, int]:
        return (
            self.offset(node.lineno, node.col_offset),
            self.offset(node.end_lineno, node.end_col_offset),
        )

    def gap(self, left: ast.AST, right: ast.AST) -> tuple[int, int]:
        """Slice between two operands; it holds the operator token."""

        return self.offset(left.end_lineno, left.end_col_offset), self.offset(
            right.lineno, right.col_offset
        )


# --------------------------------------------------------------------------- #
# mutator
# --------------------------------------------------------------------------- #

COMPARISON_FLIPS = {
    ast.Eq: "!=",
    ast.NotEq: "==",
    ast.Lt: ">=",
    ast.LtE: ">",
    ast.Gt: "<=",
    ast.GtE: "<",
    ast.In: "not in",
    ast.NotIn: "in",
    ast.Is: "is not",
    ast.IsNot: "is",
}

#: Operator tokens found between two operands.  ``is not``/``not in`` must be
#: offered before their prefixes, otherwise only the prefix would be replaced.
_COMPARE_TOKEN = re.compile(r"not\s+in|is\s+not|==|!=|<=|>=|<|>|\bin\b|\bis\b")
_FLOORDIV_TOKEN = re.compile(r"//")
_BOOL_TOKEN = re.compile(r"\b(?:and|or)\b")
_INT_LITERAL = re.compile(r"\A(?:0|[1-9][0-9]*)\Z")


@dataclass(frozen=True)
class Mutant:
    """One single-edit defect injected into one module."""

    id: str
    path: str
    kind: str
    lineno: int
    start: int
    end: int
    old: str
    new: str
    note: str

    def apply(self, text: str) -> str:
        return text[: self.start] + self.new + text[self.end :]

    def to_json(self) -> dict:
        payload = asdict(self)
        payload.pop("start")
        payload.pop("end")
        return payload


class _Unsupported(Exception):
    """A candidate site the offset arithmetic could not confirm."""


def _draft(
    source: Source,
    path: str,
    kind: str,
    start: int,
    end: int,
    new: str,
    note: str,
) -> dict:
    return {
        "path": path,
        "kind": kind,
        "lineno": source.text.count("\n", 0, start) + 1,
        "start": start,
        "end": end,
        "old": source.text[start:end],
        "new": new,
        "note": note,
    }


def _operator_slice(
    source: Source, left: ast.AST, right: ast.AST, token: re.Pattern[str]
) -> tuple[int, int]:
    """Locate the operator token between two operands.

    The slice between two operands may contain grouping parentheses (``a + b)``
    style), so the token has to be searched for rather than assumed to fill the
    whole slice.
    """

    start, end = source.gap(left, right)
    match = token.search(source.text, start, end)
    if match is None:
        raise _Unsupported(
            f"no operator token between {getattr(left, 'end_lineno', '?')}:"
            f"{getattr(left, 'end_col_offset', '?')} and "
            f"{getattr(right, 'lineno', '?')}:{getattr(right, 'col_offset', '?')}"
        )
    return match.start(), match.end()


def _mutations(source: Source, path: str) -> tuple[list[dict], list[dict]]:
    """Enumerate every mutation site of one module."""

    tree = ast.parse(source.text, filename=path)
    drafts: list[dict] = []
    unsupported: list[dict] = []

    def attempt(kind: str, start: int, end: int, new: str, note: str) -> None:
        try:
            drafts.append(_draft(source, path, kind, start, end, new, note))
        except _Unsupported as error:  # pragma: no cover - defensive
            unsupported.append({"path": path, "kind": kind, "reason": str(error)})

    def operator(
        left: ast.AST, right: ast.AST, token: re.Pattern[str], kind: str, flip: str, note: str
    ) -> None:
        try:
            start, end = _operator_slice(source, left, right, token)
        except _Unsupported as error:
            unsupported.append({"path": path, "kind": kind, "reason": str(error)})
            return
        attempt(kind, start, end, flip, note)

    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            for index, comparison in enumerate(node.ops):
                flip = COMPARISON_FLIPS.get(type(comparison))
                if flip is None:
                    continue
                operator(
                    operands[index],
                    operands[index + 1],
                    _COMPARE_TOKEN,
                    "compare",
                    flip,
                    f"{type(comparison).__name__} -> {flip}",
                )
        elif isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.FloorDiv):
                operator(
                    node.left,
                    node.right,
                    _FLOORDIV_TOKEN,
                    "floordiv",
                    "/",
                    "floor division -> true division",
                )
        elif isinstance(node, ast.BoolOp):
            word = "and" if isinstance(node.op, ast.And) else "or"
            flip = "or" if word == "and" else "and"
            for index in range(len(node.values) - 1):
                operator(
                    node.values[index],
                    node.values[index + 1],
                    _BOOL_TOKEN,
                    "boolop",
                    flip,
                    f"{word} -> {flip}",
                )
        elif isinstance(node, ast.Constant):
            # ``bool`` is a subclass of ``int`` but is not a numeric literal, and
            # ``return None`` is not an integer either.
            if type(node.value) is not int:
                continue
            start, end = source.span(node)
            if not _INT_LITERAL.match(source.text[start:end]):
                unsupported.append(
                    {
                        "path": path,
                        "kind": "constant",
                        "reason": f"unsupported literal {source.text[start:end]!r}",
                    }
                )
                continue
            for delta in (1, -1):
                attempt(
                    "constant",
                    start,
                    end,
                    str(node.value + delta),
                    f"{node.value} -> {node.value + delta}",
                )
        elif isinstance(node, ast.Raise):
            start, end = source.span(node)
            attempt("raise", start, end, "pass", "raise -> pass")
        elif isinstance(node, ast.Return):
            value = node.value
            if value is None:
                continue
            if isinstance(value, ast.Constant) and value.value is None:
                continue  # already returns None; the edit would be a no-op
            start, end = source.span(value)
            attempt("return", start, end, "None", "return value -> None")

    unique: dict[tuple[int, int, str], dict] = {}
    for draft in drafts:
        unique.setdefault((draft["start"], draft["end"], draft["new"]), draft)
    ordered = sorted(
        unique.values(),
        key=lambda item: (item["lineno"], item["start"], item["kind"], item["new"]),
    )
    return ordered, unsupported


def build_mutants(sources: dict[str, Source]) -> tuple[list[Mutant], list[dict]]:
    """Return ``(mutants, unsupported_sites)`` with stable, readable ids."""

    mutants: list[Mutant] = []
    unsupported: list[dict] = []
    for code, path in TARGET_FILES:
        drafts, rejected = _mutations(sources[path], path)
        unsupported.extend(rejected)
        for index, draft in enumerate(drafts, start=1):
            mutants.append(
                Mutant(
                    id=f"{code}{index:03d}",
                    path=draft["path"],
                    kind=draft["kind"],
                    lineno=draft["lineno"],
                    start=draft["start"],
                    end=draft["end"],
                    old=draft["old"],
                    new=draft["new"],
                    note=draft["note"],
                )
            )
    return mutants, unsupported


def normalise(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_source(path: Path) -> Source:
    return Source(normalise(path.read_text(encoding="utf-8")))


def unified(mutant: Mutant, before: str, after: str) -> str:
    return "".join(
        unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/backend/{mutant.path}",
            tofile=f"b/backend/{mutant.path} ({mutant.id} {mutant.kind})",
            n=3,
        )
    )


# --------------------------------------------------------------------------- #
# repository guards and environment
# --------------------------------------------------------------------------- #


def tree_digest(root: Path) -> tuple[str, dict[str, str]]:
    """SHA-256 of ``root``'s files, keyed by POSIX relative path."""

    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files[path.relative_to(root).as_posix()] = digest
    combined = hashlib.sha256()
    for name in sorted(files):
        combined.update(name.encode("utf-8"))
        combined.update(b"\0")
        combined.update(files[name].encode("ascii"))
    return combined.hexdigest(), files


def unit_environment(worker: Path, out: Path, node_path: Path | None) -> dict[str, str]:
    """The environment ``tests/run_tests.py`` uses for the A-layer unit suite."""

    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("DATABASE_", "CANDIDATE_TEST_", "EMPLOYER_TEST_"))
    }
    for key in ("ADVANCED_OUT", "ADVANCED_MODE", "ADVANCED_MAX_EXAMPLES", "ADVANCED_PG_URL"):
        env.pop(key, None)
    temp = out / "temp"
    env.update(
        {
            "APP_NAME": "Business unit tests",
            "DATABASE_URL": UNIT_DATABASE_URL,
            "COOKIE_SECURE": "false",
            "PYTHONPATH": str(worker / "backend"),
            "PYTHONHASHSEED": str(SEED),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "TEMP": str(temp),
            "TMP": str(temp),
            "TMPDIR": str(temp),
        }
    )
    if node_path is not None:
        # The React escaping test lives in ``frontend/tests``; NODE_PATH lets the
        # copy inside the worker resolve ``typescript``/``react`` from the real
        # checkout without copying (or linking into) node_modules.
        env["NODE_PATH"] = str(node_path)
    return env


def pytest_command(worker: Path, deselect: list[str]) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        TEST_TARGET,
        "-x",
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
        "--color=no",
    ]
    for nodeid in deselect:
        command += ["--deselect", nodeid]
    return command


def node_support() -> Path | None:
    """Return the checkout's ``node_modules`` when the React test can run."""

    modules = FRONTEND / "node_modules"
    if not (modules / "typescript").is_dir():
        return None
    return modules


def remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


# --------------------------------------------------------------------------- #
# execution
# --------------------------------------------------------------------------- #


@dataclass
class Outcome:
    id: str
    status: str
    exit_code: int | None
    seconds: float
    detail: str = ""
    killed_by: list[str] | None = None


def classify(returncode: int, output: str, timeout: bool) -> tuple[str, str]:
    """Map a pytest exit code to a mutmut-style status plus a short reason.

    A mutant that makes the module unimportable fails the suite with exit code 1
    but no failing test, so it is *not* counted as a kill: the suite did not
    judge the behaviour, the module simply never ran.  Such mutants are reported
    as ``suspicious`` and excluded from the score denominator.
    """

    if timeout:
        return "timeout", "no result within the per-mutant timeout"
    if returncode == 0:
        return "survived", ""
    if returncode == 1:
        if any(line.startswith("FAILED ") for line in output.splitlines()):
            return "killed", ""
        first = next(
            (
                line.strip()
                for line in output.splitlines()
                if line.startswith(("ERROR", "E   ", "INTERNALERROR"))
            ),
            "",
        )
        return "suspicious", f"no failing test (collection/import error): {first[:300]}"
    if returncode in (2, 3, 4, 5):
        first = next(
            (
                line.strip()
                for line in output.splitlines()
                if line.startswith(("ERROR", "E   ", "INTERNALERROR"))
            ),
            "",
        )
        return "suspicious", f"pytest exit {returncode}: {first[:300]}"
    return "suspicious", f"unexpected pytest exit {returncode}"


def parse_killed_by(output: str) -> list[str]:
    return [
        line.split(" ", 1)[1].strip()
        for line in output.splitlines()
        if line.startswith("FAILED ") and " " in line
    ]


def prepare_work(
    out: Path, jobs: int, deselect: list[str], node_modules: Path | None
) -> tuple[Path, list[Path]]:
    """Create the pristine copy and one worker tree per parallel slot."""

    work = out / MODE / "work"
    remove_tree(work)
    work.mkdir(parents=True)
    pristine = work / "pristine"
    shutil.copytree(
        BACKEND,
        pristine / "backend",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env"),
    )
    # Normalise line endings once so the offsets below always refer to the same
    # text that the tests import (the checkout itself uses CRLF on Windows).
    for path in (pristine / "backend").rglob("*.py"):
        text = normalise(path.read_text(encoding="utf-8"))
        path.write_text(text, encoding="utf-8", newline="\n")
    (pristine / "tests").mkdir()
    shutil.copy2(REPO_TESTS / "__init__.py", pristine / "tests" / "__init__.py")
    shutil.copytree(
        REPO_TESTS / "unit",
        pristine / "tests" / "unit",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    if node_modules is None:
        # The React test can only fail for environmental reasons here; dropping
        # it keeps every mutant judged by the same, otherwise identical suite.
        deselect.append(NODE_DEPENDENT_TEST)
    else:
        (pristine / "frontend" / "tests").mkdir(parents=True)
        shutil.copy2(
            FRONTEND / "tests" / "rendering.unit.mjs",
            pristine / "frontend" / "tests" / "rendering.unit.mjs",
        )
        shutil.copytree(
            FRONTEND / "src",
            pristine / "frontend" / "src",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    workers: list[Path] = []
    for index in range(jobs):
        worker = work / f"worker-{index:02d}"
        shutil.copytree(pristine, worker)
        workers.append(worker)
    return pristine, workers


def install_mutant(worker: Path, mutant: Mutant, after: str) -> None:
    target = worker / "backend" / mutant.path
    target.write_text(after, encoding="utf-8", newline="\n")


def restore_mutant(pristine: Path, worker: Path, mutant: Mutant) -> None:
    shutil.copy2(pristine / "backend" / mutant.path, worker / "backend" / mutant.path)


def run_suite(
    worker: Path,
    out: Path,
    timeout: float,
    deselect: list[str],
    node_modules: Path | None,
) -> tuple[int | None, str, float, bool]:
    started = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            pytest_command(worker, deselect),
            cwd=worker,
            env=unit_environment(worker, out, node_modules),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        returncode, output = completed.returncode, (completed.stdout or "") + (completed.stderr or "")
    except subprocess.TimeoutExpired:
        timed_out = True
        returncode, output = None, ""
    return returncode, output, round(time.monotonic() - started, 3), timed_out


def baseline_check(
    workers: list[Path],
    out: Path,
    timeout: float,
    deselect: list[str],
    node_modules: Path | None,
) -> dict:
    """The clean suite must pass before any mutant is judged."""

    returncode, output, seconds, timed_out = run_suite(
        workers[0], out, timeout, deselect, node_modules
    )
    passed = 0
    failed = 0
    for line in output.splitlines():
        match = re.search(r"(\d+) passed", line)
        if match:
            passed = int(match.group(1))
        match = re.search(r"(\d+) failed", line)
        if match:
            failed = int(match.group(1))
    return {
        "exit_code": returncode,
        "timed_out": timed_out,
        "seconds": seconds,
        "passed": passed,
        "failed": failed,
        "ok": returncode == 0 and not timed_out and passed > 0 and failed == 0,
        "tail": "\n".join(output.splitlines()[-15:]),
    }


def execute(
    mutant: Mutant,
    after: str,
    pool: queue.Queue[Path],
    pristine: Path,
    out: Path,
    timeout: float,
    deselect: list[str],
    node_modules: Path | None,
    verbose: bool,
) -> Outcome:
    worker = pool.get()
    try:
        try:
            compile(after, f"{mutant.path}::{mutant.id}", "exec")
        except SyntaxError as error:  # pragma: no cover - defensive
            return Outcome(mutant.id, "suspicious", None, 0.0, f"mutant is not valid Python: {error}")
        install_mutant(worker, mutant, after)
        returncode, output, seconds, timed_out = run_suite(
            worker, out, timeout, deselect, node_modules
        )
        restore_mutant(pristine, worker, mutant)
    finally:
        pool.put(worker)
    status, detail = classify(returncode, output, timed_out) if returncode is not None or timed_out else ("suspicious", "no return code")
    killed_by = parse_killed_by(output) if status == "killed" else None
    if verbose:
        print(f"    {mutant.id} {status} {seconds:.2f}s {detail}"[:200], flush=True)
    return Outcome(mutant.id, status, returncode, seconds, detail, killed_by)


# --------------------------------------------------------------------------- #
# engines
# --------------------------------------------------------------------------- #


def probe_mutmut(out: Path) -> dict:
    """Record whether the pinned mutmut can drive this platform."""

    folder = out / MODE
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / "mutmut-probe.log"
    probe = {
        "attempted": True,
        "version": None,
        "platform": sys.platform,
        "usable": False,
        "reason": "",
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "mutmut", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            creationflags=CREATE_NO_WINDOW,
        )
        text = (completed.stdout or "") + (completed.stderr or "")
        probe["version"] = text.strip().splitlines()[0] if text.strip() else ""
        probe["returncode"] = completed.returncode
        if completed.returncode == 0:
            probe.update(
                usable=True,
                reason="mutmut answered --version; run `python -m mutmut run` with this directory's setup.cfg on POSIX",
            )
        else:
            first = next(
                (line for line in text.splitlines() if line.strip()), "no output"
            )
            probe["reason"] = first.strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        probe["reason"] = f"{type(error).__name__}: {error}"
        text = probe["reason"]
    log.write_text(
        f"$ {sys.executable} -m mutmut --version\n{text}\n"
        f"platform={sys.platform} usable={probe['usable']} reason={probe['reason']}\n",
        encoding="utf-8",
    )
    probe["evidence"] = str(log)
    return probe


def mutator_selfcheck() -> dict:
    """A tiny in-memory fixture proving each mutation family fires correctly."""

    sample = normalise(
        "def sample(a, b, skills):\n"
        "    total = a // b\n"
        "    if a < b and b == 2:\n"
        "        return total + 30\n"
        "    if a is not None or b is None:\n"
        "        raise ValueError('x')\n"
        "    return 100\n"
    )
    source = Source(sample)
    drafts, rejected = _mutations(source, "sample.py")
    assert not rejected, rejected
    expected = {
        ("floordiv", "//", "/"),
        ("compare", "<", ">="),
        ("compare", "==", "!="),
        ("boolop", "and", "or"),
        ("boolop", "or", "and"),
        ("compare", "is not", "is"),
        ("raise", "raise ValueError('x')", "pass"),
        ("return", "total + 30", "None"),
        ("return", "100", "None"),
        ("constant", "30", "31"),
        ("constant", "30", "29"),
        ("constant", "100", "101"),
        ("constant", "100", "99"),
        ("constant", "2", "3"),
        ("constant", "2", "1"),
    }
    found = {
        (draft["kind"], draft["old"].strip(), draft["new"].strip())
        for draft in drafts
    }
    missing = expected - found
    if missing:
        raise AssertionError(f"mutator self-check failed, missing {sorted(missing)}")

    # Applying a mutant must change exactly the intended characters.
    applied = 0
    for draft in drafts:
        before = sample
        after = sample[: draft["start"]] + draft["new"] + sample[draft["end"] :]
        if draft["kind"] == "raise":
            continue
        assert after != before, draft
        applied += 1
    return {
        "fixture": "sample.py",
        "candidates": len(drafts),
        "applied": applied,
        "expected_families": len({kind for kind, _, _ in expected}),
        "families": sorted({kind for kind, _, _ in expected}),
    }


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #


def summarise(
    mutants: list[Mutant], outcomes: dict[str, Outcome], started: datetime, seconds: float
) -> dict:
    by_id = {mutant.id: mutant for mutant in mutants}
    per_file: dict[str, dict] = {}
    for _code, path in TARGET_FILES:
        per_file[path] = {
            "mutants": 0,
            "killed": 0,
            "survived": 0,
            "timeout": 0,
            "suspicious": 0,
            "score": None,
        }
    totals = {"mutants": 0, "killed": 0, "survived": 0, "timeout": 0, "suspicious": 0}
    for mutant in mutants:
        bucket = per_file[mutant.path]
        bucket["mutants"] += 1
        totals["mutants"] += 1
        status = outcomes[mutant.id].status
        bucket[status] += 1
        totals[status] += 1
    for bucket in per_file.values():
        judged = bucket["killed"] + bucket["survived"] + bucket["timeout"]
        bucket["score"] = round(bucket["killed"] / judged, 4) if judged else None
    judged = totals["killed"] + totals["survived"] + totals["timeout"]
    totals["judged"] = judged
    totals["score"] = round(totals["killed"] / judged, 4) if judged else None
    totals["score_with_suspicious_as_survivors"] = (
        round(totals["killed"] / totals["mutants"], 4) if totals["mutants"] else None
    )
    survivors = [
        {
            **by_id[key].to_json(),
            "seconds": outcomes[key].seconds,
        }
        for key in sorted(outcomes)
        if outcomes[key].status == "survived"
    ]
    suspicious = [
        {
            **by_id[key].to_json(),
            "exit_code": outcomes[key].exit_code,
            "reason": outcomes[key].detail,
        }
        for key in sorted(outcomes)
        if outcomes[key].status == "suspicious"
    ]
    timeouts = [
        {"id": key, "seconds": outcomes[key].seconds}
        for key in sorted(outcomes)
        if outcomes[key].status == "timeout"
    ]
    killers = {
        key: outcomes[key].killed_by or [] for key in sorted(outcomes) if outcomes[key].status == "killed"
    }
    return {
        "per_file": per_file,
        "totals": totals,
        "survivors": survivors,
        "suspicious": suspicious,
        "timeouts": timeouts,
        "killed_by": killers,
        "started_at": started.isoformat(),
        "seconds": round(seconds, 3),
    }


def write_json(path: Path, payload) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False, default=str)
        + "\n",
        encoding="utf-8",
    )


def git(*args: str) -> str:
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
    except (OSError, subprocess.TimeoutExpired):  # pragma: no cover - defensive
        return ""
    return completed.stdout.strip()


def prepare_out(value: Path | None) -> Path:
    env = os.environ.get("ADVANCED_OUT")
    if value is None and env:
        value = Path(env)
    if value is None:
        raise SystemExit(
            "set ADVANCED_OUT or pass --out; artefacts must live outside the checkout"
        )
    out = value.expanduser().resolve()
    if out == ROOT or out.is_relative_to(ROOT):
        raise SystemExit(f"--out must be outside the checkout: {out}")
    (out / "temp").mkdir(parents=True, exist_ok=True)
    return out


def default_jobs() -> int:
    return max(1, (os.cpu_count() or 2) - 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AST mutation testing for the mandated unit suite (P7).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--out", type=Path, help="artefact directory; defaults to $ADVANCED_OUT")
    parser.add_argument("--jobs", type=int, default=None, help="parallel mutants (CPU-1 by default)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="seconds per mutant")
    parser.add_argument("--label", default="run", help="name recorded in the report")
    parser.add_argument("--only", action="append", default=None, help="limit to these module paths")
    parser.add_argument("--max-mutants", type=int, default=None, help="debug: stop after N mutants")
    parser.add_argument("--list-mutants", action="store_true", help="print the mutant list and exit")
    parser.add_argument("--selfcheck", action="store_true", help="only run the mutator self-check")
    parser.add_argument("--verbose", action="store_true", help="print one line per mutant")
    args = parser.parse_args(argv)

    if args.selfcheck:
        print(json.dumps(mutator_selfcheck(), indent=2))
        return 0

    sources: dict[str, Source] = {}
    for _code, path in TARGET_FILES:
        sources[path] = read_source(BACKEND / path)
    mutants, unsupported = build_mutants(sources)
    if args.only:
        wanted = set(args.only)
        mutants = [mutant for mutant in mutants if mutant.path in wanted]
    if args.max_mutants is not None:
        mutants = mutants[: args.max_mutants]

    if args.list_mutants:
        for mutant in mutants:
            print(
                f"{mutant.id}\t{mutant.path}:{mutant.lineno}\t{mutant.kind}\t"
                f"{mutant.old.strip()!r} -> {mutant.new.strip()!r}"
            )
        print(f"# {len(mutants)} mutants", file=sys.stderr)
        return 0

    out = prepare_out(args.out)
    folder = out / MODE
    folder.mkdir(parents=True, exist_ok=True)
    (out / "temp").mkdir(exist_ok=True)

    started = datetime.now(timezone.utc)
    clock = time.monotonic()
    before_digest, before_files = tree_digest(BACKEND / "app")
    git_before = git("status", "--porcelain=v1")

    jobs = max(1, args.jobs or default_jobs())
    mutmut = probe_mutmut(out)
    node_modules = node_support()
    deselect: list[str] = []
    pristine, workers = prepare_work(out, jobs, deselect, node_modules)
    baseline = baseline_check(workers, out, args.timeout, deselect, node_modules)
    if not baseline["ok"]:
        write_json(
            folder / "result.json",
            {
                "mode": MODE,
                "engine": "ast",
                "error": "clean suite failed in the disposable worker; refusing to judge mutants",
                "baseline": baseline,
            },
        )
        print(json.dumps({"error": "clean baseline failed", "baseline": baseline}, ensure_ascii=False))
        return 1

    print(
        f"mutants={len(mutants)} jobs={jobs} timeout={args.timeout}s "
        f"baseline={baseline['passed']} passed in {baseline['seconds']}s "
        f"node={'yes' if node_modules else 'no'} deselect={deselect}",
        flush=True,
    )

    pool: queue.Queue[Path] = queue.Queue()
    for worker in workers:
        pool.put(worker)
    prefix = {mutant.id: sources[mutant.path].text for mutant in mutants}
    outcomes: dict[str, Outcome] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = {
            executor.submit(
                execute,
                mutant,
                prefix[mutant.id][: mutant.start]
                + mutant.new
                + prefix[mutant.id][mutant.end :],
                pool,
                pristine,
                out,
                args.timeout,
                deselect,
                node_modules,
                args.verbose,
            ): mutant
            for mutant in mutants
        }
        for future in concurrent.futures.as_completed(futures):
            outcome = future.result()
            outcomes[outcome.id] = outcome
            done = len(outcomes)
            if done % 25 == 0 or done == len(mutants):
                print(f"    progress {done}/{len(mutants)}", flush=True)

    report = summarise(mutants, outcomes, started, time.monotonic() - clock)
    after_digest, after_files = tree_digest(BACKEND / "app")
    git_after = git("status", "--porcelain=v1")

    # Keep the pristine copy as evidence of exactly what was mutated, but drop
    # the per-worker duplicates: they are pure scratch space.
    for worker in workers:
        remove_tree(worker)

    survivor_dir = folder / "survivors"
    survivor_dir.mkdir(exist_ok=True)
    for path in survivor_dir.glob("*.diff"):
        path.unlink()
    by_id = {mutant.id: mutant for mutant in mutants}
    for survivor in report["survivors"]:
        mutant = by_id[survivor["id"]]
        text = prefix[mutant.id]
        (survivor_dir / f"{mutant.id}.diff").write_text(
            unified(mutant, text, mutant.apply(text)), encoding="utf-8", newline="\n"
        )
    write_json(folder / "mutants.json", [mutant.to_json() for mutant in mutants])

    payload = {
        "schema": "p7.mutation/1",
        "mode": MODE,
        "engine": "ast",
        "label": args.label,
        "mutmut": mutmut,
        "repo": {
            "root": str(ROOT),
            "sha": git("rev-parse", "HEAD") or "unknown",
            "branch": git("rev-parse", "--abbrev-ref", "HEAD") or "unknown",
            "status_clean": git_before == "",
            "status": git_before,
        },
        "guard": {
            "path": "backend/app",
            "before": before_digest,
            "after": after_digest,
            "unchanged": before_digest == after_digest,
            "changed_files": sorted(
                name
                for name in set(before_files) | set(after_files)
                if before_files.get(name) != after_files.get(name)
            ),
            "git_status_after": git_after,
        },
        "config": {
            "test_selection": TEST_TARGET,
            "deselected": deselect,
            "node_modules": str(node_modules) if node_modules else None,
            "jobs": jobs,
            "timeout_seconds": args.timeout,
            "seed": SEED,
            "target_files": [path for _code, path in TARGET_FILES],
            "operators": ["compare", "floordiv", "boolop", "constant", "raise", "return"],
        },
        "work": {
            "root": str(folder / "work"),
            "pristine": str(pristine),
            "workers_removed": True,
        },
        "baseline": {key: value for key, value in baseline.items() if key != "tail"},
        "unsupported_sites": unsupported,
        **report,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(folder / "result.json", payload)
    write_json(folder / "mutation-result.json", payload)

    print(
        json.dumps(
            {
                "label": args.label,
                "totals": report["totals"],
                "per_file": {
                    path: bucket["score"] for path, bucket in report["per_file"].items()
                },
                "survivors": [item["id"] for item in report["survivors"]],
                "suspicious": [item["id"] for item in report["suspicious"]],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    if before_digest != after_digest:
        print(
            "backend/app changed during the run; refusing to report a score",
            file=sys.stderr,
        )
        return 3
    return 0 if not unsupported else 4


if __name__ == "__main__":
    raise SystemExit(main())
