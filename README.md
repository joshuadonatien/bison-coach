# Bison Coach

A zero-click fitness and nutrition assistant for Howard University students. It texts
students what to eat at the campus café and which workout to do at Burr Gymnasium, with no
app to open. (Working name. Sample data only until real menu and gym data is available.)

## Architecture

Data (menu, workouts, profiles) -> Recommender (rules) -> Message writer (LLM, optional) -> Delivery (SMS)
-> Replies (SWAP / LIKE / SKIP / STOP) -> profile updates.

The recommender picks from known menu items and workouts. The LLM only phrases the message,
and its output is checked before sending, so the assistant can't invent food or exercises.
It gives general wellness suggestions, not medical advice.

## Run it

```bash
pip install -r requirements.txt
pytest
uvicorn app.main:app --reload
```

Try it (prints the "SMS" to the console):

```bash
curl -X POST localhost:8000/students -H 'content-type: application/json' \
  -d '{"phone":"+12025550123","name":"Joshua","goal":"muscle"}'   # texts a "reply YES" prompt
curl -X POST localhost:8000/inbound -d From=+12025550123 -d Body=YES   # simulate the student's reply
curl -X POST localhost:8000/send/+12025550123 -H "X-Admin-Key: $ADMIN_API_KEY"
```

## Configuration (environment variables)

Never put keys or phone numbers in code. Copy `.env.example`, fill it in, and `export` the
values in your shell (the `.env` file is git-ignored).

| Variable | Needed for | Notes |
|---|---|---|
| `ADMIN_API_KEY` | `/send`, `/send-daily` | Any long random string. Send it as header `X-Admin-Key`. Without it those endpoints refuse all requests. |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` | Real SMS | When the auth token is set, `/inbound` rejects requests without a valid Twilio signature. |
| `PUBLIC_BASE_URL` | Real SMS behind ngrok/cloud | The public address Twilio calls, e.g. `https://abc123.ngrok.app`. Needed for signatures to match. |
| `ANTHROPIC_API_KEY` | LLM-written messages | Optional; falls back to a template. |

## Turning on the real services

- LLM-written messages: `pip install anthropic` and set `ANTHROPIC_API_KEY`.
- Real SMS: set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`.
  Point Twilio's inbound webhook at `/inbound`. Students are only texted tips after they reply
  YES to the confirmation text; STOP (and carrier synonyms) opts them out.
- Daily sends: call `POST /send-daily` (with `X-Admin-Key`) from cron or a scheduler.

## Roadmap

1. Prototype with sample data (this repo).
2. Pilot with a few classmates.
3. Personalize from reply feedback; tighten safety rules.
4. Explore live café and gym data with campus dining and athletics.
