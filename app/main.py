from xml.sax.saxutils import escape

from fastapi import FastAPI, Form, HTTPException, Response

from . import store
from .llm import write_message
from .messaging import Sender, default_sender
from .models import Message, Student
from .recommender import recommend
from .replies import CONFIRM_PROMPT, handle_reply

app = FastAPI(title="Bison Coach")
sender: Sender = default_sender()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/students")
def sign_up(student: Student) -> Student:
    """Create or update a profile, then text a confirmation request.

    Consent can only come from the student's own phone (replying YES), never from this
    form, so we ignore any opted_in value sent here.
    """
    existing = store.get(student.phone)
    if existing:
        # Updating preferences: keep their consent status and feedback history.
        student.opted_in = existing.opted_in
        student.liked, student.skipped = existing.liked, existing.skipped
        student.last_meal, student.last_workout = existing.last_meal, existing.last_workout
    else:
        student.opted_in = False
    store.save(student)
    if not student.opted_in:
        sender.send(Message(to=student.phone, body=CONFIRM_PROMPT))
    return student


def _send_tip(student: Student) -> Message:
    """Pick a meal + workout, word it, send it, and remember what we sent."""
    rec = recommend(student)
    msg = Message(to=student.phone, body=write_message(student, rec))
    sender.send(msg)
    student.last_meal, student.last_workout = rec.meal, rec.workout
    store.save(student)
    return msg


@app.post("/send/{phone}")
def send_now(phone: str) -> Message:
    student = store.get(phone)
    if not student:
        raise HTTPException(404, "Unknown student")
    if not student.opted_in:
        raise HTTPException(409, "Student has not opted in")
    return _send_tip(student)


@app.post("/send-daily")
def send_daily() -> dict:
    """Call this from a scheduler once a day. One failed text doesn't stop the rest."""
    sent, failed = 0, 0
    for student in store.all_opted_in():
        try:
            _send_tip(student)
            sent += 1
        except Exception as exc:  # e.g. Twilio rejects one number
            print(f"[send-daily] failed for {student.phone}: {exc}")
            failed += 1
    return {"sent": sent, "failed": failed}


def _twiml(reply: str) -> Response:
    """Twilio expects XML ("TwiML") back; <Message> is the text it replies with."""
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{escape(reply)}</Message></Response>'
    return Response(content=xml, media_type="application/xml")


@app.post("/inbound")
def inbound(From: str = Form(...), Body: str = Form("")) -> Response:
    """Webhook for incoming texts. Twilio posts form fields named From and Body."""
    student = store.get(From)
    if not student:
        return _twiml("Hi! This number isn't signed up for Bison Coach yet.")
    student, reply = handle_reply(student, Body)
    store.save(student)
    return _twiml(reply)
