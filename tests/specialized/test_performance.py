from concurrent.futures import ThreadPoolExecutor
import json
import statistics
import time
import uuid

import pytest
import psutil
from sqlalchemy import event, text


def percentiles(xs):
    ys = sorted(xs)
    return {
        "count": len(ys),
        "min_ms": min(ys) * 1000,
        "median_ms": statistics.median(ys) * 1000,
        "p95_ms": ys[max(0, int(0.95 * len(ys)) - 1)] * 1000,
        "max_ms": max(ys) * 1000,
    }


@pytest.mark.parametrize("count", [10, 100, 1000])
def test_listing_scaling_with_exact_rows_and_query_counts(
    client, account, engine, evidence, count
):
    owner = account()
    candidate = account("candidate")
    ids = [uuid.UUID(int=i + 10000) for i in range(count)]
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO job(id,employer_id,title,description,is_deleted,created_at,updated_at) VALUES(:id,:owner,:title,:description,false,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ),
            [
                {
                    "id": i,
                    "owner": uuid.UUID(owner["id"]),
                    "title": f"Job {k:05d}",
                    "description": "Synthetic scaling fixture",
                }
                for k, i in enumerate(ids)
            ],
        )
        c.execute(
            text("INSERT INTO job_skill(job_id,name) VALUES(:id,:name)"),
            [{"id": i, "name": "python"} for i in ids],
        )
    assert (
        client.get("/candidate/jobs", headers=candidate["headers"]).status_code == 200
    )
    queries = []
    times = []

    def observe(*args):
        queries.append(args[2].split()[0])

    event.listen(engine, "before_cursor_execute", observe)
    try:
        for _ in range(5):
            started = time.monotonic()
            r = client.get("/candidate/jobs", headers=candidate["headers"])
            times.append(time.monotonic() - started)
            assert r.status_code == 200
            assert [x["id"] for x in r.json()] == list(map(str, ids))
            assert all(
                x["match_score"] == 100 and x["required_skills"] == ["python"]
                for x in r.json()
            )
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    evidence(
        "scaling",
        {
            "rows": count,
            "timings": percentiles(times),
            "query_count_total": len(queries),
            "query_count_per_request": len(queries) / 5,
            "oracle": "all exact ordered IDs and 100 scores",
            "latency_sla": None,
        },
    )


def test_six_minute_bounded_business_soak(client, account, job, engine, evidence):
    owner = account()
    candidate = account("candidate")
    posting = job(owner, required_skills=["python"])
    process = psutil.Process()
    start = time.monotonic()
    deadline = start + 360
    samples = []
    latencies = []
    codes = {}
    cycles = 0
    write_cycles = 0

    def request(path):
        t = time.monotonic()
        r = client.get(path, headers=candidate["headers"])
        return r, time.monotonic() - t

    with ThreadPoolExecutor(max_workers=4) as pool:
        while time.monotonic() < deadline:
            for r, d in pool.map(
                request,
                [
                    "/candidate/jobs",
                    "/candidate/profile",
                    "/candidate/applications",
                    "/users/me",
                ],
            ):
                codes[str(r.status_code)] = codes.get(str(r.status_code), 0) + 1
                latencies.append(d)
                assert r.status_code == 200, r.text
            cycles += 1
            if cycles % 10 == 0:
                r = client.post(
                    "/employer/jobs",
                    headers=owner["headers"],
                    json={
                        "title": "Disposable soak job",
                        "description": "Normal synthetic write",
                        "required_skills": [],
                    },
                )
                assert r.status_code == 201
                assert (
                    client.delete(
                        "/employer/jobs/" + r.json()["id"], headers=owner["headers"]
                    ).status_code
                    == 204
                )
                write_cycles += 1
            if (
                not samples
                or time.monotonic() - start - samples[-1]["elapsed_seconds"] >= 30
            ):
                samples.append(
                    {
                        "elapsed_seconds": round(time.monotonic() - start, 2),
                        "rss_bytes": process.memory_info().rss,
                        "handles_or_fds": process.num_handles()
                        if hasattr(process, "num_handles")
                        else process.num_fds(),
                        "pool_checked_out": engine.pool.checkedout(),
                        "cycles": cycles,
                    }
                )
                print(json.dumps({"soak": samples[-1]}, ensure_ascii=True), flush=True)
            time.sleep(0.3)
    with engine.connect() as c:
        active_jobs = c.execute(
            text("SELECT count(*) FROM job WHERE NOT is_deleted")
        ).scalar_one()
        deleted_jobs = c.execute(
            text("SELECT count(*) FROM job WHERE is_deleted")
        ).scalar_one()
        assert active_jobs == 1
        assert deleted_jobs == write_cycles
        assert c.execute(text("SELECT count(*) FROM application")).scalar_one() == 0
        assert c.execute(text("SELECT count(*) FROM booking")).scalar_one() == 0
    assert engine.pool.checkedout() == 0
    evidence(
        "soak",
        {
            "budget_seconds": 360,
            "actual_seconds": round(time.monotonic() - start, 2),
            "cycles": cycles,
            "write_delete_pairs": write_cycles,
            "active_jobs": active_jobs,
            "soft_deleted_jobs": deleted_jobs,
            "read_statuses": codes,
            "read_latency": percentiles(latencies),
            "samples": samples,
            "final_pool_checked_out": engine.pool.checkedout(),
            "note": "Bounded local TestClient/real PostgreSQL exercise; not production long-term stability, throughput or capacity proof; memory/latency observational without SLA",
        },
    )
