from fastapi import FastAPI, HTTPException

from . import store
from .llm import write_message
from .messaging import Sender, default_sender
from .models import Message, Student
from .recommender import recommend
from .replies import handle_reply

app = FastAPI(title="Bison Coach")
sender: Sender = default_sender()
_last_sent: dict[str, tuple[str, str]] = {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/students")
def sign_up(student: Student) -> Student:
    store.save(student)
    return student


@app.post("/send/{phone}")
def send_now(phone: str) -> Message:
    student = store.get(phone)
    if not student:
        raise HTTPException(404, "Unknown student")
    if not student.opted_in:
        raise HTTPException(409, "Student has opted out")
    rec = recommend(student)
    msg = Message(to=phone, body=write_message(student, rec))
    sender.send(msg)
    _last_sent[phone] = (rec.meal, rec.workout)
    return msg


@app.post("/send-daily")
def send_daily() -> dict:
    """Call this from a scheduler (cron, GitHub Actions, APScheduler) once a day."""
    count = 0
    for student in store.all_opted_in():
        rec = recommend(student)
        sender.send(Message(to=student.phone, body=write_message(student, rec)))
        _last_sent[student.phone] = (rec.meal, rec.workout)
        count += 1
    return {"sent": count}


@app.post("/inbound")
def inbound(phone: str, text: str) -> dict:
    """Webhook for incoming replies (point Twilio's inbound webhook here)."""
    student = store.get(phone)
    if not student:
        raise HTTPException(404, "Unknown student")
    meal, workout = _last_sent.get(phone, (None, None))
    student, reply = handle_reply(student, text, meal, workout)
    store.save(student)
    return {"reply": reply}
