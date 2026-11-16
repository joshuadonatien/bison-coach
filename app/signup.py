"""Helpers for the public sign-up page: phone cleanup, rate limiting, and the HTML.

The routes themselves live in main.py; this file holds the pieces that are easy to test
on their own.
"""
import re
import time
from collections import defaultdict, deque
from html import escape
from pathlib import Path

STATIC = Path(__file__).resolve().parent / "static"

# Limits (small on purpose: this is a pilot with a handful of people).
SIGNUPS_PER_IP_PER_HOUR = 5
CONFIRM_COOLDOWN_SECONDS = 24 * 60 * 60  # at most one "reply YES" text per number per day


def normalize_us_phone(raw: str) -> str | None:
    """Turn '(202) 555-0123', '202.555.0123' or '+1 202 555 0123' into '+12025550123'.

    Returns None if it isn't a valid-looking US number. (The Twilio trial can only
    text US numbers anyway.) US area codes and exchanges never start with 0 or 1.
    """
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] in "01" or digits[3] in "01":
        return None
    return "+1" + digits


class RateLimiter:
    """Allow at most `limit` events per `window` seconds for each key (e.g. an IP address).

    Kept in memory, so it resets when the server restarts. That's acceptable for a pilot;
    a bigger deployment would store this in a database or use the host's rate limiting.
    """

    def __init__(self, limit: int, window: float) -> None:
        self.limit, self.window = limit, window
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        q = self.events[key]
        while q and now - q[0] > self.window:  # forget events older than the window
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


signup_limiter = RateLimiter(SIGNUPS_PER_IP_PER_HOUR, 60 * 60)


def form_page() -> str:
    return (STATIC / "signup.html").read_text()


def result_page(title: str, message: str) -> str:
    """Small page shown after submitting. We escape text so nothing can inject HTML."""
    return (
        (STATIC / "result.html").read_text()
        .replace("{{title}}", escape(title))
        .replace("{{message}}", escape(message))
    )
