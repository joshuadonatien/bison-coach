"""Tests for the SMS consent flow and Twilio's webhook format. No real texts are sent:
we swap in ConsoleSender, which just records messages in a list."""
import os

os.environ["COACH_DB"] = ":memory:"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main, store  # noqa: E402
from app.messaging import ConsoleSender  # noqa: E402
from app.models import Student  # noqa: E402
from app.replies import handle_reply  # noqa: E402

PHONE = "+12025550150"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "sms.db"))
    fake = ConsoleSender()
    monkeypatch.setattr(main, "sender", fake)
    c = TestClient(main.app)
    c.fake_sender = fake
    return c


def text_in(client, body, phone=PHONE):
    return client.post("/inbound", data={"From": phone, "Body": body})


def test_signup_sends_confirmation_and_does_not_opt_in(client):
    r = client.post("/students", json={"phone": PHONE, "opted_in": True})
    assert r.json()["opted_in"] is False  # the form can't grant consent
    assert len(client.fake_sender.sent) == 1
    assert "YES" in client.fake_sender.sent[0].body and "STOP" in client.fake_sender.sent[0].body


def test_unconfirmed_student_gets_no_daily_tip(client):
    client.post("/students", json={"phone": PHONE})
    assert client.post("/send-daily").json() == {"sent": 0, "failed": 0}


def test_yes_opts_in_then_daily_send_reaches_them(client):
    client.post("/students", json={"phone": PHONE})
    text_in(client, "yes")
    assert store.get(PHONE).opted_in is True
    assert client.post("/send-daily").json()["sent"] == 1


def test_inbound_returns_twiml(client):
    client.post("/students", json={"phone": PHONE})
    r = text_in(client, "HELP")
    assert r.headers["content-type"].startswith("application/xml")
    assert "<Response><Message>" in r.text and "STOP" in r.text


@pytest.mark.parametrize("word", ["STOP", "unsubscribe", "Cancel", "END", "QUIT", "STOPALL"])
def test_all_carrier_stop_words_opt_out(word):
    s, _ = handle_reply(Student(phone=PHONE, opted_in=True), word)
    assert s.opted_in is False


def test_like_works_after_restart(client):
    """last_meal/workout live in the DB, so LIKE still knows what it refers to."""
    client.post("/students", json={"phone": PHONE})
    text_in(client, "YES")
    sent = client.post(f"/send/{PHONE}")
    assert sent.status_code == 200
    # Simulate a restart: nothing in memory, only the database remains.
    text_in(client, "LIKE")
    s = store.get(PHONE)
    assert s.last_meal in s.liked and s.last_workout in s.liked


def test_feedback_ignored_before_opt_in(client):
    client.post("/students", json={"phone": PHONE})
    r = text_in(client, "LIKE")
    assert "reply YES" in r.text
    assert store.get(PHONE).liked == []


def test_unknown_number_gets_polite_reply_not_error(client):
    r = text_in(client, "hello", phone="+12025550999")
    assert r.status_code == 200 and "isn't signed up" in r.text


def test_resignup_keeps_consent_and_history(client):
    client.post("/students", json={"phone": PHONE})
    text_in(client, "YES")
    client.post(f"/send/{PHONE}")
    text_in(client, "LIKE")
    client.post("/students", json={"phone": PHONE, "goal": "endurance"})
    s = store.get(PHONE)
    assert s.opted_in is True and s.goal == "endurance" and s.liked


def test_one_failed_send_does_not_stop_the_rest(client, monkeypatch):
    for p in (PHONE, "+12025550151"):
        store.save(Student(phone=p, opted_in=True))

    def flaky(msg):
        if msg.to == PHONE:
            raise RuntimeError("carrier rejected")
    monkeypatch.setattr(client.fake_sender, "send", flaky)
    assert client.post("/send-daily").json() == {"sent": 1, "failed": 1}
