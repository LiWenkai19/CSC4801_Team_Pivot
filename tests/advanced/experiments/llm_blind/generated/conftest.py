"""Harness for the blind-generated experiment tests.

This file contains no expected values. It only makes the generated tests runnable
without a real database and without reading the developer ``.env``: it puts the
backend on ``sys.path``, fixes the same harmless environment as ``tests/unit``,
and forbids real engine connections.

The experiment owner wrote this file together with the contracts, before the
generated tests existed and before any implementation review.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BACKEND = ROOT / "backend"

for entry in (str(BACKEND), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

os.environ.setdefault("APP_NAME", "LLM blind test experiment")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://unit:unit@127.0.0.1:1/unit_not_a_database",
)


@pytest.fixture(autouse=True)
def no_database_connections(monkeypatch):
    """A generated test that reaches a real engine fails instead of connecting."""

    from sqlalchemy.engine import Engine

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Blind-generated unit tests must use a session double, not a database"
        )

    monkeypatch.setattr(Engine, "connect", forbidden)
