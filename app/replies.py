"""Handle inbound text replies. This is the consent + feedback loop.

Consent words:  YES / START (opt in), STOP and the standard carrier synonyms (opt out), HELP.
Feedback words: LIKE, SWAP / SKIP.
"""
from .models import Student

# Carriers and Twilio treat all of these as "stop texting me", so we must too.
STOP_WORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"}
START_WORDS = {"YES", "START", "UNSTOP"}
HELP_WORDS = {"HELP", "INFO"}

CONFIRM_PROMPT = (
    "Bison Coach (Howard student project): reply YES to get a daily café meal + "
    "Burr Gym workout tip. Msg & data rates may apply. Reply STOP to cancel, HELP for help."
)
HELP_TEXT = (
    "Bison Coach sends 1 daily wellness tip (general advice, not medical). "
    "Reply SWAP for other options, LIKE to see more like it, STOP to cancel."
)


def handle_reply(student: Student, text: str) -> tuple[Student, str]:
    """Update the student based on their reply and return (student, text to send back)."""
    word = text.strip().upper()
    if word in STOP_WORDS:
        student.opted_in = False
        return student, "You're unsubscribed from Bison Coach. Text START any time to rejoin."
    if word in START_WORDS:
        student.opted_in = True
        return student, "You're in! Your first Bison Coach tip comes with the next daily send."
    if word in HELP_WORDS:
        return student, HELP_TEXT
    if not student.opted_in:
        # Don't act on feedback from someone who hasn't confirmed; remind them how to join.
        return student, CONFIRM_PROMPT

    last = (student.last_meal, student.last_workout)
    if word == "LIKE":
        for item in last:
            if item and item not in student.liked:
                student.liked.append(item)
        return student, "Got it, I'll suggest more like that."
    if word in ("SKIP", "SWAP"):
        for item in last:
            if item and item not in student.skipped:
                student.skipped.append(item)
        return student, "No problem, I'll pick something different next time."
    return student, "Reply SWAP, LIKE, HELP or STOP."
