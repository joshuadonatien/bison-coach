"""Rule-based recommender. This is the safe baseline and the fallback if the LLM is off.

The LLM (see llm.py) only *phrases* the message around picks made here, so the
suggestions always come from known menu items and workouts.
"""
import json
from pathlib import Path

from .models import Recommendation, Student

DATA = Path(__file__).resolve().parent.parent / "data"


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text())


def pick_meal(student: Student, menu: list[dict]) -> dict:
    items = [i for i in menu if not (student.vegetarian and "vegetarian" not in i["tags"])]
    items = [i for i in items if i["name"] not in student.skipped] or items

    def score(item: dict) -> int:
        s = 0
        if student.goal in ("muscle", "fat-loss") and "high-protein" in item["tags"]:
            s += 3
        if student.goal == "fat-loss" and ("light" in item["tags"] or item["calories"] < 450):
            s += 2
        if student.goal == "endurance" and "high-carb" in item["tags"]:
            s += 3
        if "balanced" in item["tags"]:
            s += 1
        if item["name"] in student.liked:
            s += 2
        return s

    return max(items, key=score)


def pick_workout(student: Student, workouts: list[dict]) -> dict:
    fits = [
        w for w in workouts
        if w["minutes"] <= student.minutes_available
        and (student.level == "intermediate" or w["level"] == "beginner")
        and w["name"] not in student.skipped
    ] or workouts

    def score(w: dict) -> int:
        s = 3 if student.goal in w["goal"] else 0
        if w["name"] in student.liked:
            s += 2
        return s

    return max(fits, key=score)


def recommend(student: Student) -> Recommendation:
    meal = pick_meal(student, _load("cafe_menu.json")["items"])
    workout = pick_workout(student, _load("workouts.json")["workouts"])
    return Recommendation(
        meal=meal["name"], workout=workout["name"], workout_minutes=workout["minutes"]
    )
