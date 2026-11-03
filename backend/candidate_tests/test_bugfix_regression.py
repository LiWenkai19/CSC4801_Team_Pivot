"""Regression cases for the candidate workspace audit fixes."""
from audit_reproduction import (
    test_recommendation_query_count_is_batched as test_recommendation_query_count_is_batched,
    test_register_unique_race_maps_to_duplicate_error as test_register_unique_race_maps_to_duplicate_error,
    test_secure_sql_logging_hides_synthetic_resume as test_secure_sql_logging_hides_synthetic_resume,
)


def test_candidate_entrypoint_uses_safe_database():
    from app.main import app
    from app.db.session import get_safe_db
    from app.db.session import get_db

    # Other test fixtures may temporarily replace this dependency; verify the
    # actual entrypoint in a fresh interpreter instead of depending on test order.
    import subprocess
    import sys

    code = (
        "from app.main import app; "
        "from app.db.session import get_safe_db; "
        "from app.db.session import get_db; "
        "assert app.dependency_overrides[get_db] is get_safe_db"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
    assert app is not None and get_safe_db is not None and get_db is not None


def test_recommendations_cover_more_than_one_batch(flow):
    from sqlalchemy import event
    from sqlmodel import Session
    from app.candidate.model import Job

    with Session(flow["engine"]) as session:
        session.add_all(Job(employer_id=flow["ids"][2], title=f"Batch {i}",
                            description="Synthetic job") for i in range(501))
        session.commit()
    statements = []

    def record(*args):
        statements.append(args[2])

    event.listen(flow["engine"], "before_cursor_execute", record)
    try:
        response = flow["client"].get("/candidate/jobs", headers=flow["headers"][0])
        assert response.status_code == 200
        assert len(response.json()) == 505
        assert len(statements) <= 12
    finally:
        event.remove(flow["engine"], "before_cursor_execute", record)
