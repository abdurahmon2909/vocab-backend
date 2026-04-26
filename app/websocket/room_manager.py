# app/websocket/room_manager.py
import asyncio
import random
import uuid
from typing import Dict, List, Set
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
    status: str = "waiting"  # waiting, active, finished
    current_word: dict = None
    question_number: int = 0
    total_questions: int = 5
    start_time: datetime = None
    winner: int = None


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
    total_questions: int = 10
    start_time: datetime = None
    winning_team: str = None


class RoomManager:
    def __init__(self):
        self.duels: Dict[str, DuelRoom] = {}
        self.duel_queue: List[Player] = []
        self.team_fights: Dict[str, TeamFightRoom] = {}
        self.team_fight_queue: Dict[str, List[Player]] = {"team_a": [], "team_b": []}

    # ============ DUEL METHODS ============
    async def join_duel_queue(self, player: Player) -> str:
        """Join duel queue, returns room_id if matched"""
        self.duel_queue.append(player)

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
            status="active"
        )

        self.duels[room_id] = room
        return room_id

    async def submit_duel_answer(self, room_id: str, user_id: int, answer: str, is_correct: bool, xp_gain: int):
        room = self.duels.get(room_id)
        if not room or room.status != "active":
            return None

        player = room.player1 if room.player1.user_id == user_id else room.player2
        opponent = room.player2 if room.player1.user_id == user_id else room.player1

        if is_correct:
            player.score += 1

        player.answers.append({
            "word_id": room.current_word.get("word_id") if room.current_word else None,
            "answer": answer,
            "is_correct": is_correct,
            "xp_gain": xp_gain if is_correct else 0
        })

        # Check if both answered
        both_answered = len(room.player1.answers) > room.question_number and len(
            room.player2.answers) > room.question_number

        if both_answered:
            room.question_number += 1
            if room.question_number >= room.total_questions:
                room.status = "finished"
                room.winner = room.player1.user_id if room.player1.score > room.player2.score else room.player2.user_id
                return {"event": "duel_finished", "winner": room.winner,
                        "scores": {"player1": room.player1.score, "player2": room.player2.score}}

            return {"event": "next_question", "question_number": room.question_number + 1}

        return {"event": "waiting_opponent"}

    async def leave_duel_queue(self, user_id: int):
        self.duel_queue = [p for p in self.duel_queue if p.user_id != user_id]

    # ============ TEAM FIGHT METHODS ============
    async def join_team_queue(self, player: Player, team: str = None) -> dict:
        """Join team fight queue, returns room_id if team is full"""
        if not team:
            # Auto-assign to smaller team
            team = "team_a" if len(self.team_fight_queue["team_a"]) <= len(
                self.team_fight_queue["team_b"]) else "team_b"

        self.team_fight_queue[team].append(player)

        # Check if both teams have enough players (min 2 per team)
        if len(self.team_fight_queue["team_a"]) >= 2 and len(self.team_fight_queue["team_b"]) >= 2:
            return await self.create_team_fight_room()

        return {"status": "waiting", "team": team, "queue_size": len(self.team_fight_queue[team])}

    async def create_team_fight_room(self) -> str:
        room_id = f"team_{uuid.uuid4().hex[:8]}"

        room = TeamFightRoom(
            room_id=room_id,
            team_a=self.team_fight_queue["team_a"][:5],  # Max 5 per team
            team_b=self.team_fight_queue["team_b"][:5],
            status="active"
        )

        # Remove used players from queue
        self.team_fight_queue["team_a"] = self.team_fight_queue["team_a"][5:]
        self.team_fight_queue["team_b"] = self.team_fight_queue["team_b"][5:]

        self.team_fights[room_id] = room
        return room_id

    async def submit_team_answer(self, room_id: str, user_id: int, answer: str, is_correct: bool, xp_gain: int):
        room = self.team_fights.get(room_id)
        if not room or room.status != "active":
            return None

        # Find player and team
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

        # Count how many have answered (minimum 50% of team)
        team_a_answered = len([p for p in room.team_a if len(p.answers) > room.question_number])
        team_b_answered = len([p for p in room.team_b if len(p.answers) > room.question_number])

        min_required = min(2, min(len(room.team_a), len(room.team_b))) // 2 + 1

        if team_a_answered >= min_required and team_b_answered >= min_required:
            room.question_number += 1
            if room.question_number >= room.total_questions:
                room.status = "finished"
                room.winning_team = "team_a" if room.team_a_score > room.team_b_score else "team_b"
                return {
                    "event": "team_fight_finished",
                    "winning_team": room.winning_team,
                    "scores": {"team_a": room.team_a_score, "team_b": room.team_b_score}
                }

            return {"event": "next_question", "question_number": room.question_number + 1}

        return {"event": "waiting_teammates"}

    async def leave_team_queue(self, user_id: int):
        self.team_fight_queue["team_a"] = [p for p in self.team_fight_queue["team_a"] if p.user_id != user_id]
        self.team_fight_queue["team_b"] = [p for p in self.team_fight_queue["team_b"] if p.user_id != user_id]


room_manager = RoomManager()