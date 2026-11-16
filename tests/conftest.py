"""Shared test setup. pytest loads this file automatically before any test file.

We use fake, test-only values here. Real keys live only in environment variables on the
machine running the server, never in the code.
"""
import os

import pytest

ADMIN_KEY = "test-admin-key"
os.environ["COACH_DB"] = ":memory:"
# Make sure a real Twilio account on this laptop can't be used by tests.
# Same for a real database: tests use throwaway SQLite files unless TEST_DATABASE_URL is set.
for var in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER", "PUBLIC_BASE_URL",
            "DATABASE_URL"):
    os.environ.pop(var, None)


@pytest.fixture(autouse=True)
def admin_key(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)


@pytest.fixture(autouse=True)
def reset_signup_rate_limit():
    from app.signup import signup_limiter
    signup_limiter.events.clear()
