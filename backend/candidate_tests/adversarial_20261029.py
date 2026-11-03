"""Explicit audit diagnostics: passing means observed behavior reproduced, not fixed."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session


@pytest.mark.parametrize("payload", [
    {"skills": ["\x00"]},
    {"resume_text": "\ud800"},
    {"display_name": "\ud800"},
    {"skills": ["\ud800"]},
])
def test_invalid_text_returns_500(flow, payload):
    from app.candidate_main import app

    path = f'/users/candidates/{flow["ids"][0]}/profile'
    original = flow["client"].get(path, headers=flow["headers"][0]).json()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.patch(path, headers={**flow["headers"][0],
                                "Content-Type": "application/json"},
                                content=json.dumps(payload))
    assert response.status_code == 500
    assert flow["client"].get(path, headers=flow["headers"][0]).json() == original
    print("INVALID_TEXT", ascii(payload), response.status_code, "rollback verified")


def test_nul_skill_initial_profile_returns_500(flow):
    from app.candidate_main import app

    response = flow["client"].post('/users/register', json={
        'email': 'nul-audit@example.com', 'password': 'audit-password', 'role': 'candidate'})
    assert response.status_code == 200
    headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
    with TestClient(app, raise_server_exceptions=False) as client:
        result = client.post('/users/candidate/profile', headers=headers,
                             json={'display_name': 'Audit', 'skills': ['\x00']})
    assert result.status_code == 500
    assert flow['client'].get('/users/me', headers=headers).json()['profile_completed'] is False
    print('INITIAL_NUL_SKILL', result.status_code, 'no partial profile')


def test_oauth_domain_case_inconsistent(flow):
    client = flow['client']
    normal = client.post('/users/token', data={
        'username': 'user0@example.com', 'password': 'demo-password'})
    json_login = client.post('/users/login', json={
        'email': 'user0@EXAMPLE.COM', 'password': 'demo-password'})
    form_login = client.post('/users/token', data={
        'username': 'user0@EXAMPLE.COM', 'password': 'demo-password'})
    assert [normal.status_code, json_login.status_code, form_login.status_code] == [200, 200, 401]
    print('DOMAIN_CASE normal/token, uppercase/login, uppercase/token:',
          normal.status_code, json_login.status_code, form_login.status_code)


def test_applications_query_growth(flow):
    from app.candidate.model import Application, Job

    statements = []

    def capture(*args):
        statements.append(args[2])

    def measure():
        statements.clear()
        event.listen(flow['engine'], 'before_cursor_execute', capture)
        try:
            response = flow['client'].get('/candidate/applications', headers=flow['headers'][0])
        finally:
            event.remove(flow['engine'], 'before_cursor_execute', capture)
        assert response.status_code == 200
        return len(response.json()), len(statements)

    small = measure()
    with Session(flow['engine']) as session:
        for i in range(20):
            job = Job(employer_id=flow['ids'][2], title=f'Audit {i}', description='Audit')
            session.add(job)
            session.flush()
            session.add(Application(candidate_id=flow['ids'][0], job_id=job.id))
        session.commit()
    large = measure()
    assert large[0] == small[0] + 20
    assert large[1] >= small[1] + 40
    print('APPLICATION_QUERIES rows/sql:', small, large)


def test_cross_application_time_overlap_allowed(flow):
    from app.candidate.model import Application, ApplicationStatus, Job

    with Session(flow['engine']) as session:
        job = Job(employer_id=flow['ids'][3], title='Other employer', description='Audit')
        session.add(job)
        session.flush()
        application = Application(candidate_id=flow['ids'][0], job_id=job.id,
                                  status=ApplicationStatus.Interviewing)
        session.add(application)
        session.commit()
        second_id = application.id
    client, headers = flow['client'], flow['headers'][0]
    first = client.post(f'/candidate/applications/{flow["applications"][0]}/booking',
                        headers=headers, json={'slot_id': str(flow['slots'][0])})
    second = client.post(f'/candidate/applications/{second_id}/booking',
                         headers=headers, json={'slot_id': str(flow['slots'][1])})
    assert first.status_code == second.status_code == 201
    assert first.json()['starts_at'] == second.json()['starts_at']
    print('OVERLAPPING_INTERVIEWS', first.status_code, second.status_code)
