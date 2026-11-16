"""Tests for the public sign-up page (no admin key used here: it's public)."""
import pytest
from fastapi.testclient import TestClient

from app import main, store
from app.messaging import ConsoleSender
from app.signup import SIGNUPS_PER_IP_PER_HOUR, RateLimiter, normalize_us_phone

GOOD = {
    "name": "Ada", "phone": "(202) 555-0180", "goal": "muscle", "level": "beginner",
    "minutes_available": "30", "vegetarian": "yes", "consent": "yes", "age_confirm": "yes",
}
E164 = "+12025550180"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "signup.db"))
    fake = ConsoleSender()
    monkeypatch.setattr(main, "sender", fake)
    c = TestClient(main.app)
    c.fake_sender = fake
    return c


@pytest.mark.parametrize("raw", ["(202) 555-0180", "202.555.0180", "+1 202 555 0180", "12025550180"])
def test_phone_formats_normalize(raw):
    assert normalize_us_phone(raw) == E164


@pytest.mark.parametrize("raw", ["", "555-0180", "abc", "+44 20 7946 0958", "(012) 555-0180", "202-155-0180"])
def test_bad_phones_rejected(raw):
    assert normalize_us_phone(raw) is None


def test_form_page_loads_with_consent_text(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "STOP" in r.text and "not medical advice" in r.text and "Not an official" in r.text
    assert client.get("/static/style.css").status_code == 200


def test_good_signup_saves_profile_and_texts_once(client):
    r = client.post("/signup", data=GOOD)
    assert r.status_code == 200 and "Reply YES" in r.text
    s = store.get(E164)
    assert s.name == "Ada" and s.goal == "muscle" and s.vegetarian and s.opted_in is False
    assert [m.to for m in client.fake_sender.sent] == [E164]


@pytest.mark.parametrize("missing", ["consent", "age_confirm"])
def test_consent_and_age_required(client, missing):
    data = {k: v for k, v in GOOD.items() if k != missing}
    assert client.post("/signup", data=data).status_code == 400
    assert store.get(E164) is None and client.fake_sender.sent == []


def test_bad_phone_shows_error(client):
    r = client.post("/signup", data={**GOOD, "phone": "12345"})
    assert r.status_code == 400 and "valid 10-digit" in r.text


def test_made_up_goal_rejected(client):
    assert client.post("/signup", data={**GOOD, "goal": "starve"}).status_code == 400


def test_honeypot_pretends_success_but_does_nothing(client):
    r = client.post("/signup", data={**GOOD, "website": "http://spam.example"})
    assert r.status_code == 200
    assert store.get(E164) is None and client.fake_sender.sent == []


def test_repeat_signup_does_not_spam_the_number(client):
    for _ in range(3):
        client.post("/signup", data=GOOD)
    assert len(client.fake_sender.sent) == 1


def test_public_form_cannot_change_existing_profile(client):
    client.post("/signup", data=GOOD)
    r = client.post("/signup", data={**GOOD, "name": "Mallory", "goal": "fat-loss"})
    assert r.status_code == 200  # same message, so it doesn't reveal the number exists
    s = store.get(E164)
    assert s.name == "Ada" and s.goal == "muscle"


def test_per_ip_rate_limit(client):
    for i in range(SIGNUPS_PER_IP_PER_HOUR):
        assert client.post("/signup", data={**GOOD, "phone": f"202555{1000 + i}"}).status_code == 200
    assert client.post("/signup", data={**GOOD, "phone": "2025559999"}).status_code == 429


def test_rate_limiter_window_expires():
    rl = RateLimiter(limit=2, window=60)
    assert rl.allow("ip", now=0) and rl.allow("ip", now=1)
    assert not rl.allow("ip", now=2)
    assert rl.allow("ip", now=62)  # the first two have aged out


def test_name_is_escaped_on_pages(client):
    """Nothing the user types is echoed back, but make sure HTML can't sneak in anyway."""
    r = client.post("/signup", data={**GOOD, "name": "<script>alert(1)</script>"})
    assert "<script>" not in r.text
