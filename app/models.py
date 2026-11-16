from typing import Literal, Optional

from pydantic import BaseModel, Field

Goal = Literal["general", "muscle", "fat-loss", "endurance"]
Level = Literal["beginner", "intermediate"]


class Student(BaseModel):
    phone: str = Field(description="E.164 phone number, e.g. +12025550123")
    name: str = "Bison"
    goal: Goal = "general"
    level: Level = "beginner"
    vegetarian: bool = False
    opted_in: bool = True
    minutes_available: int = 30
    liked: list[str] = []
    skipped: list[str] = []


class Recommendation(BaseModel):
    meal: str
    workout: str
    workout_minutes: int


class Message(BaseModel):
    to: str
    body: str
    meta: Optional[dict] = None
