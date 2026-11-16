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
    # False until the student texts YES back. We never send tips without that consent.
    opted_in: bool = False
    minutes_available: int = 30
    liked: list[str] = []
    skipped: list[str] = []
    # What we sent last, so a later LIKE/SWAP reply knows what it refers to.
    # Saved in the database so it survives a server restart.
    last_meal: Optional[str] = None
    last_workout: Optional[str] = None


class Recommendation(BaseModel):
    meal: str
    workout: str
    workout_minutes: int


class Message(BaseModel):
    to: str
    body: str
    meta: Optional[dict] = None
