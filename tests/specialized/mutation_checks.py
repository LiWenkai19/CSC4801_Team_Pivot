import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET
import audit_context as s

copy = s.OUT / "mutant-source"
if not copy.exists():
    copy.mkdir()
    shutil.copytree(
        s.SRC / "backend/app",
        copy / "app",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
env = dict(os.environ)
env["PYTHONPATH"] = os.pathsep.join([str(copy), str(s.OUT / "python-tools")])
env["PYTHONDONTWRITEBYTECODE"] = "1"
rows = []
mutants = [
    (
        "M01-floor-round",
        "app/employer/matching.py",
        "return (100 * len(candidate & required)) // len(required)",
        "return round(100 * len(candidate & required) / len(required))",
        False,
    ),
    (
        "M02-intersection-union",
        "app/employer/matching.py",
        "candidate & required",
        "candidate | required",
        False,
    ),
    (
        "M03-empty-requirements",
        "app/employer/matching.py",
        "return 100",
        "return 0",
        False,
    ),
    (
        "M04-drop-trim",
        "app/users/service.py",
        "skill.strip().lower()",
        "skill.lower()",
        False,
    ),
    (
        "M05-equal-time-allowed",
        "app/interview/service.py",
        "if starts_at <= utc_now():",
        "if starts_at < utc_now():",
        False,
    ),
    (
        "M06-duration-31",
        "app/interview/service.py",
        "SLOT_LENGTH = timedelta(minutes=30)",
        "SLOT_LENGTH = timedelta(minutes=31)",
        False,
    ),
    (
        "M07-role-comparison",
        "app/users/service.py",
        "if curr_user.role != Role.Candidate:\n        raise HTTPException(",
        "if curr_user.role == Role.Candidate:\n        raise HTTPException(",
        False,
    ),
    (
        "ME01-redundant-int",
        "app/employer/matching.py",
        "return (100 * len(candidate & required)) // len(required)",
        "return int((100 * len(candidate & required)) // len(required))",
        True,
    ),
]


def execute(name):
    xml = s.OUT / (name + ".xml")
    command_file = s.OUT / (name + "-command.json")
    if "--resume" in sys.argv and xml.exists() and command_file.exists():
        result = json.loads(command_file.read_text(encoding="utf-8"))
    else:
        result = s.run(
            name,
            [
                s.PYTHON,
                "-m",
                "pytest",
                Path(__file__).parent / "test_mutation_oracles.py",
                "-q",
                "--tb=short",
                "-p",
                "no:cacheprovider",
                "--junitxml=" + str(xml),
            ],
            env,
            copy,
            40,
        )
    counts = {"failure": 0, "error": 0, "passed": 0}
    failed = []
    if xml.exists():
        for c in ET.parse(xml).getroot().iter("testcase"):
            status = (
                "error"
                if c.find("error") is not None
                else "failure"
                if c.find("failure") is not None
                else "passed"
            )
            counts[status] += 1
            if status != "passed":
                failed.append(c.get("name"))
    return result, counts, failed


baseline, counts, _ = execute("mutation-baseline-strengthened")
assert baseline["exit_code"] == 0 and counts["passed"] == 8
for name, filename, old, new, equivalent in mutants:
    p = copy / filename
    original = p.read_bytes()
    source = original.decode("utf-8").replace("\r\n", "\n")
    assert old in source
    try:
        p.write_text(source.replace(old, new, 1), encoding="utf-8")
        result, counts, failed = execute(name)
        status = (
            "invalid"
            if counts["error"]
            else "equivalent"
            if equivalent and result["exit_code"] == 0
            else "killed"
            if counts["failure"]
            else "survived"
        )
        rows.append(
            {
                "id": name,
                "source": filename,
                "status": status,
                "counts": counts,
                "failing_oracles": failed,
                "equivalent_reason": "int of an existing Python int quotient preserves every output in the specified domain"
                if equivalent
                else None,
                "known_non_equivalent": not equivalent,
            }
        )
    finally:
        p.write_bytes(original)
    assert p.read_bytes() == original
killed = sum(r["status"] == "killed" for r in rows)
survived = sum(r["status"] == "survived" for r in rows)
s.save(
    "mutation-results.json",
    {
        "sha": s.SHA,
        "baseline": {"cases": 8, "passed": 8},
        "mutants": rows,
        "sampled_score": killed / (killed + survived) if killed + survived else None,
        "denominator": "killed + survived; equivalent/invalid excluded",
        "source_restored": True,
        "sample_limit": "Eight hand-selected local mutations, not whole-program mutation adequacy; no changes to original repository",
    },
)
print(
    json.dumps(
        {
            "killed": killed,
            "survived": survived,
            "other": [
                (r["id"], r["status"])
                for r in rows
                if r["status"] not in ["killed", "survived"]
            ],
        },
        ensure_ascii=True,
    )
)

if killed != 7 or survived or any(r["status"] == "invalid" for r in rows):
    raise SystemExit(1)
