"""SQLite storage for students. Stores only what the assistant needs."""
import json
import os
import sqlite3

from .models import Student

DB_PATH = os.getenv("COACH_DB", "coach.db")


def _conn(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS students (phone TEXT PRIMARY KEY, data TEXT NOT NULL)")
    return conn


def save(student: Student, path: str | None = None) -> None:
    with _conn(path) as c:
        c.execute(
            "INSERT INTO students (phone, data) VALUES (?, ?) "
            "ON CONFLICT(phone) DO UPDATE SET data = excluded.data",
            (student.phone, student.model_dump_json()),
        )


def get(phone: str, path: str | None = None) -> Student | None:
    with _conn(path) as c:
        row = c.execute("SELECT data FROM students WHERE phone = ?", (phone,)).fetchone()
    return Student(**json.loads(row[0])) if row else None


def all_opted_in(path: str | None = None) -> list[Student]:
    with _conn(path) as c:
        rows = c.execute("SELECT data FROM students").fetchall()
    students = [Student(**json.loads(r[0])) for r in rows]
    return [s for s in students if s.opted_in]
