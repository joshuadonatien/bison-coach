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
export ADMIN_API_KEY=pick-any-long-random-string
uvicorn app.main:app --reload
```

Try it (without Twilio, each "SMS" is printed in the server console):

1. Open http://localhost:8000/ and sign up with a test number like (202) 555-0123.
   The console shows the "reply YES" text.
2. Simulate the student's replies and the daily send:

```bash
curl -X POST localhost:8000/inbound --data-urlencode From=+12025550123 -d Body=YES   # simulate the reply (urlencode keeps the +)
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
| `DATABASE_URL` | Cloud storage | Postgres connection string. If unset, a local SQLite file (`coach.db`) is used. Render's free tier wipes local files, so the cloud must use Postgres. |
| `ANTHROPIC_API_KEY` | LLM-written messages | Optional; falls back to a template. |

## Turning on the real services

- LLM-written messages: `pip install anthropic` and set `ANTHROPIC_API_KEY`.
- Real SMS: set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`.
  Point Twilio's inbound webhook at `/inbound`. Students are only texted tips after they reply
  YES to the confirmation text; STOP (and carrier synonyms) opts them out.
- Daily sends: call `POST /send-daily` (with `X-Admin-Key`) from cron or a scheduler.

## Deploy to Render (free tier)

`render.yaml` creates a free web service plus a free Postgres database.

1. Render dashboard -> New -> Blueprint -> pick this GitHub repo and the branch to deploy.
2. When asked for the `sync: false` values, leave the Twilio ones blank until you have a
   verified toll-free number. Without them, texts are only printed in Render's logs.
3. After the first deploy, set `PUBLIC_BASE_URL` to the service URL (e.g.
   `https://bison-coach.onrender.com`) and copy the generated `ADMIN_API_KEY` from
   the Environment tab.
4. Check `https://<your-url>/health` returns `{"status":"ok"}` and the sign-up page loads.

Free-tier caveats: the service sleeps after ~15 minutes idle and takes ~1 minute to wake,
and free Postgres databases expire (reportedly ~30 days). Fine for a short pilot.

To run the Postgres tests locally: `TEST_DATABASE_URL=postgresql://... pytest`.

## Roadmap

1. Prototype with sample data (this repo).
2. Pilot with a few classmates.
3. Personalize from reply feedback; tighten safety rules.
4. Explore live café and gym data with campus dining and athletics.
