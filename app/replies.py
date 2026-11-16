"""Handle inbound text replies (SWAP, LIKE, SKIP, STOP). This is the feedback loop."""
from .models import Student


def handle_reply(student: Student, text: str, last_meal: str | None = None,
                 last_workout: str | None = None) -> tuple[Student, str]:
    word = text.strip().upper()
    if word == "STOP":
        student.opted_in = False
        return student, "You're unsubscribed. Text START any time to rejoin."
    if word == "START":
        student.opted_in = True
        return student, "Welcome back! Your next message is on the way."
    if word == "LIKE":
        for item in (last_meal, last_workout):
            if item and item not in student.liked:
                student.liked.append(item)
        return student, "Got it, I'll suggest more like that."
    if word in ("SKIP", "SWAP"):
        for item in (last_meal, last_workout):
            if item and item not in student.skipped:
                student.skipped.append(item)
        return student, "No problem, I'll pick something different next time."
    return student, "Reply SWAP, LIKE or STOP."
