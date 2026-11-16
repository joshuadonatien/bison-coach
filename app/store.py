"""Student storage. Stores only what the assistant needs.

- If DATABASE_URL is set (e.g. Render Postgres), we use Postgres.
- Otherwise we use a local SQLite file (COACH_DB, default coach.db): handy on a laptop
  and in tests, but cloud hosts like Render's free tier wipe local files, so don't rely
  on SQLite there.

Each student is one row: their phone number plus their whole profile as JSON text.
The SQL below works the same in both databases; only the "?" vs "%s" placeholder differs.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .models import Student

DB_PATH = os.getenv("COACH_DB", "coach.db")
CREATE_TABLE = "CREATE TABLE IF NOT EXISTS students (phone TEXT PRIMARY KEY, data TEXT NOT NULL)"


@contextmanager
def _cursor(path: str | None = None) -> Iterator[tuple[object, str]]:
    """Open a connection, yield (cursor, placeholder), commit, and always close.

    An explicit `path` forces SQLite (used by tests)."""
    url = None if path else os.getenv("DATABASE_URL")
    if url:
        import psycopg  # only needed in the cloud

        with psycopg.connect(url) as conn:  # commits on success, closes at the end
            cur = conn.cursor()
            cur.execute(CREATE_TABLE)
            yield cur, "%s"
    else:
        conn = sqlite3.connect(path or DB_PATH)
        try:
            with conn:  # commits on success, rolls back on error
                conn.execute(CREATE_TABLE)
                yield conn.cursor(), "?"
        finally:
            conn.close()


def save(student: Student, path: str | None = None) -> None:
    with _cursor(path) as (cur, p):
        cur.execute(
            f"INSERT INTO students (phone, data) VALUES ({p}, {p}) "
            "ON CONFLICT (phone) DO UPDATE SET data = excluded.data",
            (student.phone, student.model_dump_json()),
        )


def get(phone: str, path: str | None = None) -> Student | None:
    with _cursor(path) as (cur, p):
        cur.execute(f"SELECT data FROM students WHERE phone = {p}", (phone,))
        row = cur.fetchone()
    return Student(**json.loads(row[0])) if row else None


def all_opted_in(path: str | None = None) -> list[Student]:
    with _cursor(path) as (cur, _):
        cur.execute("SELECT data FROM students")
        rows = cur.fetchall()
    students = [Student(**json.loads(r[0])) for r in rows]
    return [s for s in students if s.opted_in]
