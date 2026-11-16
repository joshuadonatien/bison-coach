import time
from xml.sax.saxutils import escape

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import store
from .llm import write_message
from .messaging import Sender, default_sender
from .models import Message, Student
from .recommender import recommend
from .replies import CONFIRM_PROMPT, handle_reply
from .security import require_admin, verify_twilio
from .signup import (
    CONFIRM_COOLDOWN_SECONDS, STATIC, form_page, normalize_us_phone, result_page, signup_limiter,
)

app = FastAPI(title="Bison Coach")
sender: Sender = default_sender()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _maybe_send_confirmation(student: Student) -> None:
    """Text the "reply YES" prompt, at most once per cooldown period per number."""
    if student.opted_in:
        return
    now = time.time()
    if student.confirm_sent_at and now - student.confirm_sent_at < CONFIRM_COOLDOWN_SECONDS:
        return
    sender.send(Message(to=student.phone, body=CONFIRM_PROMPT))
    student.confirm_sent_at = now


def _register(student: Student, update_existing: bool) -> Student:
    """Create a profile (opted out until they reply YES) and send the confirmation text.

    Consent can only come from the student's own phone, never from a form, so any
    opted_in value sent in is ignored.
    """
    existing = store.get(student.phone)
    if existing and not update_existing:
        student = existing  # public form: never let a stranger change someone's profile
    elif existing:
        # Admin update of preferences: keep consent status and feedback history.
        student.opted_in, student.confirm_sent_at = existing.opted_in, existing.confirm_sent_at
        student.liked, student.skipped = existing.liked, existing.skipped
        student.last_meal, student.last_workout = existing.last_meal, existing.last_workout
    else:
        student.opted_in, student.confirm_sent_at = False, None
    _maybe_send_confirmation(student)
    store.save(student)
    return student


@app.post("/students", dependencies=[Depends(require_admin)])
def sign_up(student: Student) -> Student:
    """Admin/testing API. The public way in is the /signup form below."""
    return _register(student, update_existing=True)


# ---------- public sign-up page ----------

app.mount("/static", StaticFiles(directory=STATIC), name="static")

SIGNUP_DONE = (
    "Check your phone: we texted you from Bison Coach. Reply YES to start getting tips. "
    "If no text arrives in a few minutes, double-check your number and try again later."
)


@app.get("/", response_class=HTMLResponse)
def signup_form() -> str:
    return form_page()


def _page(title: str, message: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(result_page(title, message), status_code=status)


@app.post("/signup", response_class=HTMLResponse)
def signup_submit(
    request: Request,
    name: str = Form(""),
    phone: str = Form(""),
    goal: str = Form("general"),
    level: str = Form("beginner"),
    minutes_available: str = Form("30"),
    vegetarian: str | None = Form(None),
    consent: str | None = Form(None),
    age_confirm: str | None = Form(None),
    website: str = Form(""),  # honeypot
) -> HTMLResponse:
    if website:
        # A bot filled the hidden field. Pretend it worked so it doesn't adapt; do nothing.
        return _page("Thanks!", SIGNUP_DONE)
    ip = request.client.host if request.client else "unknown"
    if not signup_limiter.allow(ip):
        return _page("Slow down", "Too many sign-ups from this network. Try again in an hour.", 429)
    if consent != "yes" or age_confirm != "yes":
        return _page("Almost there", "Please confirm you're 18+ and agree to receive texts.", 400)
    e164 = normalize_us_phone(phone)
    if not e164:
        return _page("Check your number", "Please enter a valid 10-digit US mobile number.", 400)
    clean_name = name.strip()[:40]
    if not clean_name:
        return _page("Almost there", "Please enter your first name.", 400)
    try:
        student = Student(
            phone=e164, name=clean_name, goal=goal, level=level,
            minutes_available=int(minutes_available), vegetarian=vegetarian == "yes",
        )
    except (ValidationError, ValueError):
        return _page("Something's off", "Please use the options on the form.", 400)
    _register(student, update_existing=False)
    # Same message whether or not the number was already signed up, so the page can't be
    # used to find out who uses Bison Coach.
    return _page("Thanks!", SIGNUP_DONE)


def _send_tip(student: Student) -> Message:
    """Pick a meal + workout, word it, send it, and remember what we sent."""
    rec = recommend(student)
    msg = Message(to=student.phone, body=write_message(student, rec))
    sender.send(msg)
    student.last_meal, student.last_workout = rec.meal, rec.workout
    store.save(student)
    return msg


@app.post("/send/{phone}", dependencies=[Depends(require_admin)])
def send_now(phone: str) -> Message:
    student = store.get(phone)
    if not student:
        raise HTTPException(404, "Unknown student")
    if not student.opted_in:
        raise HTTPException(409, "Student has not opted in")
    return _send_tip(student)


@app.post("/send-daily", dependencies=[Depends(require_admin)])
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


@app.post("/inbound", dependencies=[Depends(verify_twilio)])
def inbound(From: str = Form(...), Body: str = Form("")) -> Response:
    """Webhook for incoming texts. Twilio posts form fields named From and Body."""
    student = store.get(From)
    if not student:
        return _twiml("Hi! This number isn't signed up for Bison Coach yet.")
    student, reply = handle_reply(student, Body)
    store.save(student)
    return _twiml(reply)
