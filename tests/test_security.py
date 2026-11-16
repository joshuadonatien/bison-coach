"""Tests for the admin key and Twilio signature checks.

We compute a real Twilio signature with a made-up auth token, the same way Twilio's
servers would, so we can test both the 'genuine' and 'forged' cases offline."""
import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from app import main, store
from app.messaging import ConsoleSender
from app.models import Student

FAKE_TOKEN = "fake-auth-token-for-tests"
PHONE = "+12025550170"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "sec.db"))
    monkeypatch.setattr(main, "sender", ConsoleSender())
    store.save(Student(phone=PHONE, opted_in=True))
    return TestClient(main.app)


# ---- admin key ----

def test_send_daily_rejects_missing_key(client):
    assert client.post("/send-daily").status_code == 401


def test_send_daily_rejects_wrong_key(client):
    assert client.post("/send-daily", headers={"X-Admin-Key": "nope"}).status_code == 401


def test_send_daily_accepts_right_key(client):
    r = client.post("/send-daily", headers={"X-Admin-Key": "test-admin-key"})
    assert r.status_code == 200 and r.json()["sent"] == 1


def test_admin_endpoints_fail_closed_without_configured_key(client, monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY")
    assert client.post(f"/send/{PHONE}", headers={"X-Admin-Key": ""}).status_code == 503


def test_students_api_needs_admin_key(client):
    assert client.post("/students", json={"phone": "+12025550171"}).status_code == 401


# ---- Twilio signature ----

def sign(url: str, params: dict) -> str:
    return RequestValidator(FAKE_TOKEN).compute_signature(url, params)


def test_inbound_accepts_genuine_twilio_request(client, monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", FAKE_TOKEN)
    params = {"From": PHONE, "Body": "STOP"}
    sig = sign("http://testserver/inbound", params)
    r = client.post("/inbound", data=params, headers={"X-Twilio-Signature": sig})
    assert r.status_code == 200
    assert store.get(PHONE).opted_in is False


def test_inbound_rejects_forged_request(client, monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", FAKE_TOKEN)
    r = client.post("/inbound", data={"From": PHONE, "Body": "STOP"},
                    headers={"X-Twilio-Signature": "forged"})
    assert r.status_code == 403
    assert store.get(PHONE).opted_in is True  # the fake STOP did nothing


def test_inbound_rejects_tampered_body(client, monkeypatch):
    """A signature for one message can't be reused with a different message."""
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", FAKE_TOKEN)
    sig = sign("http://testserver/inbound", {"From": PHONE, "Body": "LIKE"})
    r = client.post("/inbound", data={"From": PHONE, "Body": "STOP"},
                    headers={"X-Twilio-Signature": sig})
    assert r.status_code == 403


def test_inbound_uses_public_base_url_behind_tunnel(client, monkeypatch):
    """Twilio signs the public https URL; the app sees http://testserver."""
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", FAKE_TOKEN)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://bison.example.ngrok.app/")
    params = {"From": PHONE, "Body": "HELP"}
    sig = sign("https://bison.example.ngrok.app/inbound", params)
    assert client.post("/inbound", data=params, headers={"X-Twilio-Signature": sig}).status_code == 200
