import uuid
from typing import Dict, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Player:
    user_id: int
    nickname: str
    xp: int
    level: int
    socket_id: str
    is_ready: bool = False
    score: int = 0
    current_word: dict = None
    answers: List[dict] = field(default_factory=list)


@dataclass
class DuelRoom:
    room_id: str
    player1: Player
    player2: Player = None
    status: str = "waiting"
    current_word: dict = None
    question_number: int = 0
    total_questions: int = 20
    start_time: datetime = None
    winner: int = None
    questions: List[dict] = field(default_factory=list)


@dataclass
class TeamFightRoom:
    room_id: str
    team_a: List[Player] = field(default_factory=list)
    team_b: List[Player] = field(default_factory=list)
    team_a_score: int = 0
    team_b_score: int = 0
    status: str = "waiting"
    current_word: dict = None
    question_number: int = 0
    total_questions: int = 20
    start_time: datetime = None
    winning_team: str = None
    questions: List[dict] = field(default_factory=list)


class RoomManager:
    def __init__(self):
        self.duels: Dict[str, DuelRoom] = {}
        self.duel_queue: List[Player] = []
        self.team_fights: Dict[str, TeamFightRoom] = {}
        self.team_fight_queue: Dict[str, List[Player]] = {"team_a": [], "team_b": []}

    async def join_duel_queue(self, player: Player) -> str:
        for p in self.duel_queue:
            if p.user_id == player.user_id:
                return None

        self.duel_queue.append(player)
        print(f"🔍 Duel queue: {len(self.duel_queue)} players")

        if len(self.duel_queue) >= 2:
            player1 = self.duel_queue.pop(0)
            player2 = self.duel_queue.pop(0)
            return await self.create_duel_room(player1, player2)

        return None

    async def create_duel_room(self, player1: Player, player2: Player) -> str:
        room_id = f"duel_{uuid.uuid4().hex[:8]}"

        room = DuelRoom(
            room_id=room_id,
            player1=player1,
            player2=player2,
            status="active",
            start_time=datetime.now(),
            total_questions=20
        )

        self.duels[room_id] = room
        print(f"⚔️ Duel room created: {room_id}")
        return room_id

    async def set_duel_questions(self, room_id: str, questions: List[dict]):
        room = self.duels.get(room_id)
        if room:
            room.questions = questions
            if questions:
                room.current_word = questions[0]

    async def submit_duel_answer(self, room_id: str, user_id: int, answer: str, is_correct: bool, xp_gain: int):
        room = self.duels.get(room_id)
        if not room or room.status != "active":
            return None

        player = room.player1 if room.player1.user_id == user_id else room.player2
        opponent = room.player2 if room.player1.user_id == user_id else room.player1

        if not player:
            return None

        if is_correct:
            player.score += 1

        player.answers.append({
            "word_id": room.current_word.get("word_id") if room.current_word else None,
            "answer": answer,
            "is_correct": is_correct,
            "xp_gain": xp_gain if is_correct else 0
        })

        player_answered = len(player.answers) > room.question_number
        opponent_answered = len(opponent.answers) > room.question_number

        if player_answered and opponent_answered:
            room.question_number += 1

            if room.question_number >= room.total_questions or room.question_number >= len(room.questions):
                room.status = "finished"
                if room.player1.score > room.player2.score:
                    room.winner = room.player1.user_id
                elif room.player2.score > room.player1.score:
                    room.winner = room.player2.user_id
                else:
                    room.winner = None

                self.duels.pop(room_id, None)

                return {
                    "event": "duel_finished",
                    "winner": room.winner,
                    "scores": {
                        "player1": room.player1.score,
                        "player2": room.player2.score
                    }
                }

            if room.question_number < len(room.questions):
                room.current_word = room.questions[room.question_number]

            return {
                "event": "next_question",
                "question": room.current_word,
                "question_number": room.question_number + 1,
                "total_questions": room.total_questions
            }

        return {"event": "waiting_opponent"}

    async def leave_duel_queue(self, user_id: int):
        self.duel_queue = [p for p in self.duel_queue if p.user_id != user_id]

    async def join_team_queue(self, player: Player, team: str = None) -> dict:
        for t in ["team_a", "team_b"]:
            for p in self.team_fight_queue[t]:
                if p.user_id == player.user_id:
                    return {"status": "already_in_queue", "team": t}

        if not team:
            team = "team_a" if len(self.team_fight_queue["team_a"]) <= len(
                self.team_fight_queue["team_b"]) else "team_b"

        self.team_fight_queue[team].append(player)
        print(f"👥 Team {team} queue: {len(self.team_fight_queue[team])} players")

        if len(self.team_fight_queue["team_a"]) >= 2 and len(self.team_fight_queue["team_b"]) >= 2:
            room_id = await self.create_team_fight_room()
            return {"status": "ready", "room_id": room_id}

        return {"status": "waiting", "team": team, "queue_size": len(self.team_fight_queue[team])}

    async def create_team_fight_room(self) -> str:
        room_id = f"team_{uuid.uuid4().hex[:8]}"

        room = TeamFightRoom(
            room_id=room_id,
            team_a=self.team_fight_queue["team_a"][:5],
            team_b=self.team_fight_queue["team_b"][:5],
            status="active",
            start_time=datetime.now(),
            total_questions=20
        )

        self.team_fight_queue["team_a"] = self.team_fight_queue["team_a"][5:]
        self.team_fight_queue["team_b"] = self.team_fight_queue["team_b"][5:]

        self.team_fights[room_id] = room
        print(f"👥 Team fight room created: {room_id}")
        return room_id

    async def set_team_fight_questions(self, room_id: str, questions: List[dict]):
        room = self.team_fights.get(room_id)
        if room:
            room.questions = questions
            if questions:
                room.current_word = questions[0]

    async def submit_team_answer(self, room_id: str, user_id: int, answer: str, is_correct: bool, xp_gain: int):
        room = self.team_fights.get(room_id)
        if not room or room.status != "active":
            return None

        player_team = None
        player = None
        for p in room.team_a:
            if p.user_id == user_id:
                player_team = "team_a"
                player = p
                break
        if not player:
            for p in room.team_b:
                if p.user_id == user_id:
                    player_team = "team_b"
                    player = p
                    break

        if not player:
            return None

        if is_correct:
            if player_team == "team_a":
                room.team_a_score += 1
            else:
                room.team_b_score += 1
            player.score += 1

        player.answers.append({
            "word_id": room.current_word.get("word_id") if room.current_word else None,
            "answer": answer,
            "is_correct": is_correct,
            "xp_gain": xp_gain if is_correct else 0
        })

        team_a_answered = len([p for p in room.team_a if len(p.answers) > room.question_number])
        team_b_answered = len([p for p in room.team_b if len(p.answers) > room.question_number])

        min_required_a = max(1, len(room.team_a) // 2)
        min_required_b = max(1, len(room.team_b) // 2)

        if team_a_answered >= min_required_a and team_b_answered >= min_required_b:
            room.question_number += 1

            if room.question_number >= room.total_questions or room.question_number >= len(room.questions):
                room.status = "finished"
                if room.team_a_score > room.team_b_score:
                    room.winning_team = "team_a"
                elif room.team_b_score > room.team_a_score:
                    room.winning_team = "team_b"
                else:
                    room.winning_team = "draw"

                self.team_fights.pop(room_id, None)

                return {
                    "event": "team_fight_finished",
                    "winning_team": room.winning_team,
                    "scores": {"team_a": room.team_a_score, "team_b": room.team_b_score}
                }

            if room.question_number < len(room.questions):
                room.current_word = room.questions[room.question_number]

            return {
                "event": "next_question",
                "question": room.current_word,
                "question_number": room.question_number + 1,
                "total_questions": room.total_questions,
                "scores": {"team_a": room.team_a_score, "team_b": room.team_b_score}
            }

        return {
            "event": "waiting_teammates",
            "team_a_answered": team_a_answered,
            "team_b_answered": team_b_answered,
            "team_a_total": len(room.team_a),
            "team_b_total": len(room.team_b)
        }

    async def leave_team_queue(self, user_id: int):
        self.team_fight_queue["team_a"] = [p for p in self.team_fight_queue["team_a"] if p.user_id != user_id]
        self.team_fight_queue["team_b"] = [p for p in self.team_fight_queue["team_b"] if p.user_id != user_id]


room_manager = RoomManager()