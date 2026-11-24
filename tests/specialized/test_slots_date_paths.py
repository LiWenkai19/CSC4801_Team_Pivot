"""Cross-entrypoint expansion of the confirmed date representability root cause."""

import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest

PATH = "/employer/interview-slots"


@pytest.mark.parametrize(
    "operation,expected",
    [("delete", 204), ("candidate-availability", 200), ("candidate-booking", 201)],
)
def test_same_accepted_date_across_related_entrypoints(
    client, flow, snapshot, evidence, operation, expected
):
    """截止前最后一个可创建的时段仍可删除、查询和预约。"""
    data = flow(with_slot=False)
    created = client.post(
        PATH,
        headers=data["owner"]["headers"],
        json={"starts_at": "3000-12-31T15:29:59.999999Z"},
    )
    assert created.status_code == 201, created.text
    slot = created.json()
    before = snapshot()
    if operation == "delete":
        result = client.delete(
            PATH + "/" + slot["id"], headers=data["owner"]["headers"]
        )
    elif operation == "candidate-availability":
        result = client.get(
            f"/candidate/applications/{data['application_id']}/slots",
            headers=data["candidate"]["headers"],
        )
    else:
        result = client.post(
            f"/candidate/applications/{data['application_id']}/booking",
            headers=data["candidate"]["headers"],
            json={"slot_id": slot["id"]},
        )
    after = snapshot()
    evidence(
        "shared-path",
        {
            "operation": operation,
            "accepted_slot": slot,
            "status": result.status_code,
            "body": result.text,
            "business_state_unchanged": before == after,
            "state": after,
        },
    )
    if result.status_code == 500:
        assert after == before
    assert result.status_code == expected, result.text


def test_minimal_witness_through_real_http_server(client, account, evidence):
    """真实 HTTP 请求拒绝原复现日期，正常时段仍可查询。"""
    owner = account()
    root = Path(os.environ["SLOT_AUDIT_OUT"])
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    log = (root / "logs/real-http-boundary.txt").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=Path(os.environ["AUDIT_SOURCE_ROOT"]) / "backend",
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if os.name == "nt"
        else 0,
    )
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", timeout=5, trust_env=False
        ) as http:
            for _ in range(80):
                try:
                    if http.get("/openapi.json").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                assert process.poll() is None, "Server exited before readiness"
                time.sleep(0.1)
            else:
                pytest.fail("Real HTTP server readiness timeout")
            normal = http.post(
                PATH,
                headers=owner["headers"],
                json={"starts_at": "2030-05-02T00:00:00Z"},
            )
            before = http.get(PATH, headers=owner["headers"])
            assert normal.status_code == 201 and before.status_code == 200
            created = http.post(
                PATH,
                headers=owner["headers"],
                json={"starts_at": "9999-12-31T15:30:00Z"},
            )
            listed = http.get(PATH, headers=owner["headers"])
            evidence(
                "real-http",
                {
                    "no_business_clock_patch_in_server": True,
                    "normal_create": normal.status_code,
                    "normal_list": before.status_code,
                    "boundary_create": created.status_code,
                    "boundary_slot": created.json(),
                    "list_after_boundary": listed.status_code,
                    "body": listed.text,
                },
            )
            assert created.status_code == 422, created.text
            assert created.json()["detail"] == (
                "Interview slots must end before 3001 in Asia/Shanghai"
            )
            assert listed.status_code == 200, listed.text
            assert listed.json() == before.json()
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        log.close()
