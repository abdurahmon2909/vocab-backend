from datetime import date, datetime
from pydantic import BaseModel, Field
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
    nickname: str | None = None
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
    display_name: str
    xp: int
    level: int
    level_progress: int
    elo: int = 1000
    rank_title: str = "Silver"
    rank_icon: str = "⚪"
    wins: int = 0
    losses: int = 0
    draws: int = 0
    games_played: int = 0
    next_level_xp: int
    streak: int
    best_streak: int
    missions: list[MissionOut]


class ProfileUpdateIn(BaseModel):
    nickname: str = Field(min_length=2, max_length=40)


class ProfileUpdateOut(BaseModel):
    nickname: str
    display_name: str


class RankOut(BaseModel):
    rank_title: str
    rank_icon: str
    rank_min_elo: int
    rank_max_elo: int | None = None


class LeaderboardUserOut(BaseModel):
    rank: int
    user_id: int
    display_name: str  # 🔥 nickname -> display_name (frontendda shunday ishlatilgan)
    username: str | None = None
    photo_url: str | None = None
    xp: int
    level: int
    level_progress: int  # 🔥 QO'SHILDI
    elo: int = 1000
    rank_title: str = "Silver"
    rank_icon: str = "⚪"
    rank_min_elo: int = 1000
    rank_max_elo: int | None = 1249
    wins: int = 0
    losses: int = 0
    draws: int = 0
    games_played: int = 0
    badge: str
    badge_icon: str
    total_users: int = 0
    is_me: bool = False


class LeaderboardOut(BaseModel):
    me: LeaderboardUserOut | None = None
    top: list[LeaderboardUserOut]
    total_users: int = 0
    ranks: list[RankOut] = []


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
    answer_session_id: str | None = None


class AnswerOut(BaseModel):
    is_correct: bool
    xp_gain: int
    total_xp: int
    level: int
    level_progress: int
    elo: int = 1000
    rank_title: str = "Silver"
    rank_icon: str = "⚪"
    wins: int = 0
    losses: int = 0
    draws: int = 0
    games_played: int = 0
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


class BookOut(BaseModel):
    id: int
    collection_id: int
    slug: str
    title: str
    description: str | None = None

    # 🔥 MUHIM
    cover_url: str | None = None

    total_units: int
    completed_units: int
    progress_percent: int


class StatsOut(BaseModel):
    total_seen: int
    total_correct: int
    total_wrong: int
    weak_words_count: int
    mastered_words_count: int


NicknameUpdateIn = ProfileUpdateIn
