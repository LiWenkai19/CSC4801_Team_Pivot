"""Verify the employer branch adds files only inside the employer scope.

The baseline commit is the teammate ``candidate`` branch tip recorded in
docs/EMPLOYER_PROGRESS.md. Modifications, deletions and renames of tracked
files are reported as errors; new files must stay inside the employer scope.

Usage: run from the repository root (``app/``):

    python scripts/check_employer_ownership.py
"""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "c2667bd7805a6f779c6cf90e32aa3b40bc95bdfc"

EMPLOYER_PREFIXES = (
    "backend/app/employer/",
    "backend/employer_tests/",
)
EMPLOYER_FILES = frozenset({
    "backend/app/employer_main.py",
    "pytest.employer.ini",
    "scripts/check_employer_ownership.py",
})


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args]).decode("utf-8")


def allowed(path: str) -> bool:
    """Return whether a newly added path belongs to the employer scope."""
    return (
        path.startswith(EMPLOYER_PREFIXES)
        or path in EMPLOYER_FILES
        or (path.startswith("docs/EMPLOYER_") and path.endswith(".md"))
    )


def diff_entries() -> list[tuple[str, list[str]]]:
    """List (status, paths) pairs for all changes since the baseline commit."""
    entries: list[tuple[str, list[str]]] = []
    for line in git("diff", "--name-status", BASE_COMMIT).splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        entries.append((fields[0], fields[1:]))
    return entries


def main() -> int:
    errors: list[str] = []
    ancestry = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", BASE_COMMIT, "HEAD"]
    )
    if ancestry.returncode:
        errors.append(
            f"HEAD no longer descends from the employer baseline {BASE_COMMIT}; "
            "re-audit the baseline."
        )

    for status, paths in diff_entries():
        code = status[:1]
        if code == "A":
            for path in paths:
                if not allowed(path):
                    errors.append(f"Addition outside the employer scope: {path}")
            continue
        errors.append(
            f"Tracked file changed ({status}) outside the employer scope: "
            + ", ".join(paths)
        )

    for name in git("ls-files", "--others", "--exclude-standard").splitlines():
        if name and not allowed(name):
            errors.append(f"Addition outside the employer scope: {name}")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"Ownership check passed: HEAD descends from {BASE_COMMIT}; "
        "all additions stay in the employer scope."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
