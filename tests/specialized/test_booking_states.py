from itertools import product

import pytest

STATES = ("Pending", "Interviewing", "Rejected", "Accepted")


@pytest.mark.parametrize(
    "source,target,already_booked", list(product(STATES, STATES, (False, True)))
)
def test_complete_status_transition_relation_with_and_without_booking(
    client, flow, snapshot, source, target, already_booked
):
    data = flow()
    booking_path = f"/candidate/applications/{data['application_id']}/booking"
    status_path = f"/employer/applications/{data['application_id']}/status"
    old_booking = None
    if already_booked:
        made = client.post(
            booking_path,
            headers=data["candidate"]["headers"],
            json={"slot_id": data["slot"]["id"]},
        )
        assert made.status_code == 201, made.text
        old_booking = made.json()
    for version, state in enumerate((source, target), start=data["version"]):
        changed = client.patch(
            status_path, headers=data["owner"]["headers"], json={"version": version, "status": state}
        )
        assert changed.status_code == 200 and changed.json()["status"] == state, (
            changed.text
        )
        stored = snapshot()
        assert stored["application"][0]["status"] == state
    before = snapshot()
    detail = client.get(
        f"/candidate/applications/{data['application_id']}",
        headers=data["candidate"]["headers"],
    )
    assert detail.status_code == 200 and detail.json()["status"] == target
    assert detail.json()["booking"] == old_booking
    ours = client.get(
        f"/employer/jobs/{data['job_id']}/applications",
        headers=data["owner"]["headers"],
    )
    assert ours.status_code == 200 and ours.json()[0]["status"] == target
    if already_booked:
        assert ours.json()[0]["booking"]["booking_id"] == old_booking["booking_id"]
        assert client.get(
            "/employer/interview-slots", headers=data["owner"]["headers"]
        ).json() == [{**data["slot"], "is_booked": True}]
    attempted = client.post(
        booking_path,
        headers=data["candidate"]["headers"],
        json={"slot_id": data["slot"]["id"]},
    )
    should_accept = not already_booked and target == "Interviewing"
    assert attempted.status_code == (201 if should_accept else 409), attempted.text
    if not should_accept:
        assert snapshot() == before
    else:
        assert len(snapshot()["booking"]) == 1


def test_existing_booking_survives_live_profile_company_and_job_updates(
    client, flow, snapshot
):
    data = flow()
    result = client.post(
        f"/candidate/applications/{data['application_id']}/booking",
        headers=data["candidate"]["headers"],
        json={"slot_id": data["slot"]["id"]},
    )
    assert result.status_code == 201, result.text
    before = snapshot()
    changes = [
        (
            "/candidate/profile",
            data["candidate"]["headers"],
            {"version": 1, "display_name": "Updated candidate", "skills": ["sql"]},
        ),
        (
            "/employer/company",
            data["owner"]["headers"],
            {"version": 1, "company_name": "Updated company"},
        ),
        (
            f"/employer/jobs/{data['job_id']}",
            data["owner"]["headers"],
            {
                "title": "Updated job",
                "version": 1,
                "description": "Updated description",
                "required_skills": ["sql"],
            },
        ),
    ]
    for path, headers, body in changes:
        response = client.patch(path, headers=headers, json=body)
        assert response.status_code == 200, response.text
    after = snapshot()
    assert (
        after["booking"] == before["booking"]
        and after["application"] == before["application"]
        and after["interview_slot"] == before["interview_slot"]
    )
    apps = client.get("/candidate/applications", headers=data["candidate"]["headers"])
    assert apps.status_code == 200
    assert (
        apps.json()[0]["job_title"] == "Updated job"
        and apps.json()[0]["company_name"] == "Updated company"
    )
    rows = client.get(
        f"/employer/jobs/{data['job_id']}/applications",
        headers=data["owner"]["headers"],
    )
    assert rows.status_code == 200
    assert (
        rows.json()[0]["display_name"] == "Updated candidate"
        and rows.json()[0]["skills"] == ["sql"]
        and rows.json()[0]["match_score"] == 100
    )
    assert rows.json()[0]["booking"]["booking_id"] == result.json()["booking_id"]
    state = snapshot()
    deletion = client.delete(
        f"/employer/jobs/{data['job_id']}", headers=data["owner"]["headers"]
    )
    assert deletion.status_code == 409, deletion.text
    assert snapshot() == state


def test_distinct_applications_of_same_candidate_can_have_independent_bookings(
    client, flow, add_applicant, create_slot, snapshot
):
    from datetime import timedelta
    from conftest import FROZEN

    first = flow()
    job = client.post(
        "/employer/jobs",
        headers=first["owner"]["headers"],
        json={
            "title": "Second job",
            "description": "Synthetic second job",
            "required_skills": [],
        },
    )
    assert job.status_code == 201, job.text
    second = add_applicant(
        first["owner"], job.json()["id"], candidate=first["candidate"]
    )
    slot2 = create_slot(first["owner"], FROZEN + timedelta(days=2))
    for data, slot in ((first, first["slot"]), (second, slot2)):
        result = client.post(
            f"/candidate/applications/{data['application_id']}/booking",
            headers=data["candidate"]["headers"],
            json={"slot_id": slot["id"]},
        )
        assert result.status_code == 201, result.text
    state = snapshot()
    assert (
        len(state["booking"]) == 2
        and len({row["application_id"] for row in state["booking"]}) == 2
        and len({row["slot_id"] for row in state["booking"]}) == 2
    )
