import os

os.environ["COACH_DB"] = ":memory:"

from fastapi.testclient import TestClient  # noqa: E402

from app import store  # noqa: E402
from app.llm import template_message  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Student  # noqa: E402
from app.recommender import recommend  # noqa: E402
from app.replies import handle_reply  # noqa: E402


def test_vegetarian_gets_vegetarian_meal():
    rec = recommend(Student(phone="+12025550101", vegetarian=True, goal="muscle"))
    assert rec.meal in {
        "Veggie stir-fry with tofu", "Greek yogurt parfait",
        "Egg-white omelet with spinach", "Pasta with marinara and side salad",
    }


def test_time_limit_respected():
    rec = recommend(Student(phone="+12025550102", minutes_available=15))
    assert rec.workout_minutes <= 15


def test_swap_changes_next_pick():
    s = Student(phone="+12025550103", goal="muscle", opted_in=True)
    first = recommend(s)
    s.last_meal, s.last_workout = first.meal, first.workout
    s, _ = handle_reply(s, "SWAP")
    second = recommend(s)
    assert second.meal != first.meal


def test_stop_opts_out():
    s, _ = handle_reply(Student(phone="+12025550104", opted_in=True), "stop")
    assert s.opted_in is False


def test_message_is_short_and_has_swap():
    s = Student(phone="+12025550105")
    msg = template_message(s, recommend(s))
    assert len(msg) <= 320 and "SWAP" in msg


def test_store_roundtrip(tmp_path):
    db = str(tmp_path / "t.db")
    store.save(Student(phone="+12025550106", name="Jo"), db)
    assert store.get("+12025550106", db).name == "Jo"


def test_api_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "api.db"))
    client = TestClient(app)
    assert client.post("/students", json={"phone": "+12025550107", "name": "Ada"}).status_code == 200
    assert client.post("/send/+12025550107").status_code == 409  # not confirmed yet
    client.post("/inbound", data={"From": "+12025550107", "Body": "YES"})
    r = client.post("/send/+12025550107")
    assert r.status_code == 200 and "Ada" in r.json()["body"]
    assert client.post("/inbound", data={"From": "+12025550107", "Body": "STOP"}).status_code == 200
    assert client.post("/send/+12025550107").status_code == 409
