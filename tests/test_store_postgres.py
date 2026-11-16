"""Runs the storage code against a real Postgres, only if TEST_DATABASE_URL is set.

Example (uses a throwaway local database, never the production one):
    TEST_DATABASE_URL=postgresql://localhost:5499/coach_test pytest tests/test_store_postgres.py
"""
import os

import pytest

from app import store
from app.models import Student

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="set TEST_DATABASE_URL to run Postgres tests")


@pytest.fixture(autouse=True)
def postgres(monkeypatch):
    import psycopg

    with psycopg.connect(URL) as conn:
        conn.execute("DROP TABLE IF EXISTS students")
    monkeypatch.setenv("DATABASE_URL", URL)


def test_roundtrip_and_update():
    store.save(Student(phone="+12025550190", name="Ada"))
    store.save(Student(phone="+12025550190", name="Ada B", opted_in=True))  # upsert
    s = store.get("+12025550190")
    assert s.name == "Ada B" and s.opted_in is True
    assert store.get("+12025550199") is None


def test_all_opted_in_filters():
    store.save(Student(phone="+12025550191", opted_in=True))
    store.save(Student(phone="+12025550192", opted_in=False))
    assert [s.phone for s in store.all_opted_in()] == ["+12025550191"]


def test_full_api_flow_on_postgres(monkeypatch):
    from fastapi.testclient import TestClient

    from app import main
    from app.messaging import ConsoleSender

    monkeypatch.setattr(main, "sender", ConsoleSender())
    c = TestClient(main.app)
    c.post("/signup", data={"name": "Ada", "phone": "2025550193", "consent": "yes", "age_confirm": "yes"})
    c.post("/inbound", data={"From": "+12025550193", "Body": "YES"})
    r = c.post("/send-daily", headers={"X-Admin-Key": "test-admin-key"})
    assert r.json() == {"sent": 1, "failed": 0}
