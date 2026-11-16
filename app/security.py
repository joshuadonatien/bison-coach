"""Request checks that keep strangers from abusing the server once it's public.

1. require_admin: /send and /send-daily need the header  X-Admin-Key: <ADMIN_API_KEY>.
   If ADMIN_API_KEY isn't set, those endpoints refuse everything ("fail closed"), so
   forgetting the variable on a deploy can't leave them open.
2. verify_twilio: when TWILIO_AUTH_TOKEN is set (i.e. real SMS is on), /inbound only
   accepts requests carrying a valid X-Twilio-Signature. Twilio signs each webhook with
   your auth token, so a faked "STOP" or "YES" from someone else gets rejected.
   Without the token we're in console-only dev mode and the check is skipped.

Environment variables are read on every request (not at import) so tests can change them.
"""
import os
import secrets

from fastapi import Header, HTTPException, Request


def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("ADMIN_API_KEY")
    if not expected:
        raise HTTPException(503, "Server misconfigured: set ADMIN_API_KEY")
    # compare_digest takes the same time whether the first or last character is wrong,
    # so an attacker can't guess the key one character at a time by timing responses.
    if not x_admin_key or not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(401, "Missing or wrong X-Admin-Key")


def _public_url(request: Request) -> str:
    """The exact URL Twilio called. Behind ngrok or a cloud host the app may see
    http://internal-host/... while Twilio signed https://public-host/..., so set
    PUBLIC_BASE_URL (e.g. https://abc123.ngrok.app) to the address Twilio uses."""
    base = os.getenv("PUBLIC_BASE_URL")
    if not base:
        return str(request.url)
    url = base.rstrip("/") + request.url.path
    return f"{url}?{request.url.query}" if request.url.query else url


async def verify_twilio(request: Request) -> None:
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not token:
        return  # dev mode: no real SMS, nothing to protect yet
    from twilio.request_validator import RequestValidator

    form = await request.form()
    signature = request.headers.get("X-Twilio-Signature", "")
    if not RequestValidator(token).validate(_public_url(request), dict(form), signature):
        raise HTTPException(403, "Invalid Twilio signature")
