"""Message writer. Uses an LLM when ANTHROPIC_API_KEY is set, otherwise a template.

The LLM never chooses the meal or workout; it only words the message. Output is
length-checked and falls back to the template on any problem.
"""
import os

from .models import Recommendation, Student

MAX_SMS_CHARS = 320

SYSTEM_PROMPT = (
    "You write short, friendly text messages for a Howard University student wellness "
    "assistant. Use ONLY the meal and workout provided. Give general wellness "
    "suggestions, never medical advice, and never suggest extreme dieting. "
    "Keep it under 280 characters and end with: Reply SWAP for other options."
)


def template_message(student: Student, rec: Recommendation) -> str:
    return (
        f"Hi {student.name}! Café pick today: {rec.meal}. "
        f"At Burr Gymnasium: {rec.workout} ({rec.workout_minutes} min). "
        "Reply SWAP for other options."
    )


def write_message(student: Student, rec: Recommendation) -> str:
    fallback = template_message(student, rec)
    if not os.getenv("ANTHROPIC_API_KEY"):
        return fallback
    try:
        import anthropic  # optional dependency

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=os.getenv("COACH_MODEL", "claude-haiku-5-5"),
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"Student name: {student.name}. Goal: {student.goal}. "
                    f"Meal: {rec.meal}. Workout: {rec.workout} ({rec.workout_minutes} min)."
                ),
            }],
        )
        text = resp.content[0].text.strip()
        if rec.meal in text and rec.workout in text and len(text) <= MAX_SMS_CHARS:
            return text
    except Exception:
        pass
    return fallback
