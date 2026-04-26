from datetime import date, datetime
from pydantic import BaseModel
from typing import Literal


LearningMode = Literal[
    "flashcard",
    "listening",
    "writing",
    "test",
    "weak_flashcard",
    "weak_test",
    "weak_writing",
]


class TelegramUserOut(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None


class MissionOut(BaseModel):
    id: int
    code: str
    title: str
    mission_type: str
    target: int
    progress: int
    xp_reward: int
    is_completed: bool


class UserOut(BaseModel):
    telegram: TelegramUserOut
    xp: int
    level: int
    level_progress: int
    next_level_xp: int
    streak: int
    best_streak: int
    missions: list[MissionOut]


class BookOut(BaseModel):
    id: int
    slug: str
    title: str
    description: str | None = None
    cover_url: str | None = None
    total_units: int
    completed_units: int
    progress_percent: int


class UnitOut(BaseModel):
    id: int
    book_id: int
    unit_number: int
    title: str
    description: str | None = None
    total_words: int
    mastered_words: int
    progress_percent: int
    status: Literal["locked", "in_progress", "completed"]


class WordOut(BaseModel):
    id: int
    unit_id: int
    english: str
    uzbek: str
    definition: str | None = None
    example: str | None = None
    seen_count: int = 0
    correct_count: int = 0
    wrong_count: int = 0
    mastery_score: int = 0


class AnswerIn(BaseModel):
    word_id: int
    unit_id: int
    mode: LearningMode
    is_correct: bool
    user_answer: str | None = None
    correct_answer: str | None = None


class AnswerOut(BaseModel):
    is_correct: bool
    xp_gain: int
    total_xp: int
    level: int
    level_progress: int
    next_level_xp: int
    mastery_score: int
    streak: int
    mission_updates: list[MissionOut]


class TestQuestionOut(BaseModel):
    word_id: int
    unit_id: int
    direction: Literal["en_uz", "uz_en"]
    question: str
    options: list[str]
    correct_answer: str


class StatsOut(BaseModel):
    total_seen: int
    total_correct: int
    total_wrong: int
    weak_words_count: int
    mastered_words_count: int