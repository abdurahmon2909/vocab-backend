import uuid

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List


@dataclass
class Player:
    user_id: int
    nickname: str
    xp: int
    level: int
    socket_id: str
    photo_url: str | None = None
    is_ready: bool = False
    score: int = 0
    xp_gain: int = 0
    current_word: dict | None = None
    answers: List[dict] = field(default_factory=list)
    finished_at: datetime | None = None
    is_connected: bool = True
    left_at: datetime | None = None
    surrendered: bool = False
    forfeited: bool = False


@dataclass
class DuelRoom:
    room_id: str
    player1: Player
    player2: Player | None = None
    status: str = "waiting"
    current_word: dict | None = None
    question_number: int = 0
    total_questions: int = 20
    time_per_question: int = 10
    start_time: datetime | None = None
    winner: int | None = None
    questions: List[dict] = field(default_factory=list)
    final_sent: bool = False
    finish_reason: str | None = None


@dataclass
class TeamFightRoom:
    room_id: str
    team_a: List[Player] = field(default_factory=list)
    team_b: List[Player] = field(default_factory=list)
    team_a_score: int = 0
    team_b_score: int = 0
    status: str = "waiting"
    current_word: dict | None = None
    question_number: int = 0
    total_questions: int = 20
    time_per_question: int = 10
    start_time: datetime | None = None
    winning_team: str | None = None
    questions: List[dict] = field(default_factory=list)


class RoomManager:
    def __init__(self):
        self.duels: Dict[str, DuelRoom] = {}
        self.finished_duels: Dict[str, dict] = {}
        self.finished_duels_created_at: Dict[str, datetime] = {}
        self.finished_duels_ttl = timedelta(minutes=30)
        self.duel_queue: List[Player] = []
        self.online_users: Dict[int, Player] = {}
        self.duel_invites: Dict[int, int] = {}
        self.team_fights: Dict[str, TeamFightRoom] = {}
        self.team_fight_queue: Dict[str, List[Player]] = {
            "team_a": [],
            "team_b": [],
        }

    def cleanup_finished_duels(self) -> None:
        now = datetime.now()

        for room_id, created_at in list(self.finished_duels_created_at.items()):
            if now - created_at > self.finished_duels_ttl:
                self.finished_duels_created_at.pop(room_id, None)
                self.finished_duels.pop(room_id, None)

    def cleanup_user_everywhere(self, user_id: int) -> None:
        self.remove_online_user(user_id)
        self.duel_queue = [p for p in self.duel_queue if p.user_id != user_id]
        self.team_fight_queue["team_a"] = [
            p for p in self.team_fight_queue["team_a"] if p.user_id != user_id
        ]
        self.team_fight_queue["team_b"] = [
            p for p in self.team_fight_queue["team_b"] if p.user_id != user_id
        ]

    def add_online_user(self, player: Player):
        player.is_connected = True
        player.left_at = None
        self.online_users[player.user_id] = player

    def remove_online_user(self, user_id: int):
        self.online_users.pop(user_id, None)
        self.duel_invites.pop(user_id, None)
        for target_id, from_user_id in list(self.duel_invites.items()):
            if from_user_id == user_id:
                self.duel_invites.pop(target_id, None)

    def player_to_dict(self, player: Player | None):
        if not player:
            return None

        return {
            "user_id": player.user_id,
            "nickname": player.nickname,
            "xp": player.xp,
            "level": player.level,
            "photo_url": player.photo_url,
            "score": player.score,
            "answered": len(player.answers),
            "finished": bool(player.finished_at),
            "is_connected": player.is_connected,
            "surrendered": player.surrendered,
            "forfeited": player.forfeited,
        }

    def is_user_in_active_duel(self, user_id: int) -> bool:
        for room in self.duels.values():
            if room.status != "active":
                continue

            if room.player1 and room.player1.user_id == user_id:
                return True

            if room.player2 and room.player2.user_id == user_id:
                return True

        return False

    def get_online_duel_users(self, current_user_id: int):
        users = []

        for player in self.online_users.values():
            if player.user_id == current_user_id:
                continue

            users.append({
                **self.player_to_dict(player),
                "busy": self.is_user_in_active_duel(player.user_id),
            })

        users.sort(key=lambda x: (x.get("busy", False), -(x.get("xp") or 0)))
        return users

    def create_duel_invite(self, from_user_id: int, target_user_id: int) -> dict:
        if from_user_id == target_user_id:
            return {"ok": False, "reason": "self_invite"}

        from_player = self.online_users.get(from_user_id)
        target_player = self.online_users.get(target_user_id)

        if not from_player:
            return {"ok": False, "reason": "sender_offline"}

        if not target_player:
            return {"ok": False, "reason": "target_offline"}

        if self.is_user_in_active_duel(from_user_id):
            return {"ok": False, "reason": "sender_busy"}

        if self.is_user_in_active_duel(target_user_id):
            return {"ok": False, "reason": "target_busy"}

        self.duel_invites[target_user_id] = from_user_id
        return {"ok": True, "from_player": from_player, "target_player": target_player}

    def reject_duel_invite(self, user_id: int, from_user_id: int | None = None):
        current_from_user_id = self.duel_invites.get(user_id)

        if from_user_id is None or current_from_user_id == from_user_id:
            self.duel_invites.pop(user_id, None)
            return current_from_user_id

        return None

    async def accept_duel_invite(self, user_id: int, from_user_id: int) -> dict:
        current_from_user_id = self.duel_invites.get(user_id)

        if current_from_user_id != from_user_id:
            return {"ok": False, "reason": "invite_expired"}

        player1 = self.online_users.get(from_user_id)
        player2 = self.online_users.get(user_id)

        if not player1 or not player2:
            return {"ok": False, "reason": "user_offline"}

        if self.is_user_in_active_duel(from_user_id) or self.is_user_in_active_duel(user_id):
            return {"ok": False, "reason": "user_busy"}

        self.duel_invites.pop(user_id, None)
        room_id = await self.create_duel_room(player1, player2)

        return {"ok": True, "room_id": room_id}

    async def join_duel_queue(self, player: Player) -> str | None:
        if self.is_user_in_active_duel(player.user_id):
            return None

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

        for p in [player1, player2]:
            p.score = 0
            p.xp_gain = 0
            p.answers = []
            p.finished_at = None
            p.surrendered = False
            p.forfeited = False
            p.is_connected = True
            p.left_at = None

        await self.leave_duel_queue(player1.user_id)
        await self.leave_duel_queue(player2.user_id)

        room = DuelRoom(
            room_id=room_id,
            player1=player1,
            player2=player2,
            status="active",
            start_time=datetime.now(),
            total_questions=20,
            time_per_question=10,
        )

        self.duels[room_id] = room
        print(f"⚔️ Duel room created: {room_id}")
        return room_id

    async def set_duel_questions(self, room_id: str, questions: List[dict]):
        room = self.duels.get(room_id)

        if room:
            room.questions = questions[:20]
            room.total_questions = min(20, len(room.questions))

            if room.questions:
                room.current_word = room.questions[0]

    def _get_duel_players(self, room: DuelRoom, user_id: int):
        if room.player1 and room.player1.user_id == user_id:
            return room.player1, room.player2

        if room.player2 and room.player2.user_id == user_id:
            return room.player2, room.player1

        return None, None

    def _progress_payload(self, room_id: str, player: Player, opponent: Player):
        return {
            "type": "progress",
            "room_id": room_id,
            "player_id": player.user_id,
            "opponent_id": opponent.user_id,
            "player_score": player.score,
            "opponent_score": opponent.score,
            "player_answered": len(player.answers),
            "opponent_answered": len(opponent.answers),
            "player_finished": bool(player.finished_at),
            "opponent_finished": bool(opponent.finished_at),
            "player_xp": player.xp_gain,
            "opponent_xp": opponent.xp_gain,
            "opponent_profile": self.player_to_dict(opponent),
            "opponent_left": opponent.forfeited,
            "opponent_surrendered": opponent.surrendered,
        }

    async def submit_duel_answer(
        self,
        room_id: str,
        user_id: int,
        answer: str,
        is_correct: bool,
        xp_gain: int,
        question_index: int,
        time_left: float,
    ):
        if room_id in self.finished_duels:
            return {
                "type": "finished",
                "result": self.finished_duels[room_id],
            }

        room = self.duels.get(room_id)

        if not room or room.status != "active" or not room.player2:
            return None

        player, opponent = self._get_duel_players(room, user_id)

        if not player or not opponent or player.finished_at or player.surrendered or player.forfeited:
            return None

        already_answered = any(
            a.get("question_index") == question_index for a in player.answers
        )

        if already_answered:
            return None

        current_word = None

        if 0 <= question_index < len(room.questions):
            current_word = room.questions[question_index]

        if is_correct:
            player.score += 1

        player.xp_gain += max(0, int(xp_gain or 0))

        player.answers.append(
            {
                "question_index": question_index,
                "word_id": current_word.get("word_id") if current_word else None,
                "answer": answer,
                "is_correct": is_correct,
                "xp_gain": xp_gain,
                "time_left": time_left,
            }
        )

        next_index = question_index + 1
        is_player_finished = next_index >= room.total_questions or next_index >= len(room.questions)

        if is_player_finished:
            player.finished_at = datetime.now()

        if opponent.forfeited or opponent.surrendered:
            return {
                "type": "finished",
                "result": await self.finish_duel(room_id),
            }

        if room.player1.finished_at and room.player2.finished_at:
            return {
                "type": "finished",
                "result": await self.finish_duel(room_id),
            }

        return self._progress_payload(room_id, player, opponent)

    async def mark_player_finished(self, room_id: str, user_id: int):
        if room_id in self.finished_duels:
            return {
                "type": "finished",
                "result": self.finished_duels[room_id],
            }

        room = self.duels.get(room_id)

        if not room or room.status != "active" or not room.player2:
            return None

        player, opponent = self._get_duel_players(room, user_id)

        if not player or not opponent:
            return None

        if not player.finished_at:
            player.finished_at = datetime.now()

        if opponent.forfeited or opponent.surrendered:
            return {
                "type": "finished",
                "result": await self.finish_duel(room_id),
            }

        if room.player1.finished_at and room.player2.finished_at:
            return {
                "type": "finished",
                "result": await self.finish_duel(room_id),
            }

        return self._progress_payload(room_id, player, opponent)

    async def surrender_duel(self, room_id: str, user_id: int):
        if room_id in self.finished_duels:
            return {
                "type": "finished",
                "result": self.finished_duels[room_id],
            }

        room = self.duels.get(room_id)

        if not room or room.status != "active" or not room.player2:
            return None

        player, opponent = self._get_duel_players(room, user_id)

        if not player or not opponent:
            return None

        player.surrendered = True
        player.finished_at = datetime.now()
        room.winner = opponent.user_id
        room.finish_reason = "surrender"

        return {
            "type": "finished",
            "result": await self.finish_duel(room_id),
        }

    async def handle_disconnect(self, user_id: int):
        for room_id, room in list(self.duels.items()):
            if room.status != "active" or not room.player2:
                continue

            player, opponent = self._get_duel_players(room, user_id)

            if not player or not opponent:
                continue

            player.is_connected = False
            player.left_at = datetime.now()
            player.forfeited = True
            player.finished_at = datetime.now()
            room.winner = opponent.user_id
            room.finish_reason = "opponent_left"

            if opponent.finished_at:
                return {
                    "type": "finished",
                    "result": await self.finish_duel(room_id),
                    "opponent_id": opponent.user_id,
                }

            return {
                "type": "opponent_left",
                "room_id": room_id,
                "left_user_id": user_id,
                "opponent_id": opponent.user_id,
                "opponent_profile": self.player_to_dict(player),
            }

        return None

    async def finish_duel(self, room_id: str):
        if room_id in self.finished_duels:
            return self.finished_duels[room_id]

        room = self.duels.get(room_id)

        if not room:
            return self.finished_duels.get(room_id)

        if room.final_sent:
            return self.finished_duels.get(room_id)

        room.final_sent = True
        room.status = "finished"

        p1 = room.player1
        p2 = room.player2

        if not p1.finished_at:
            p1.finished_at = datetime.now()

        if not p2.finished_at:
            p2.finished_at = datetime.now()

        if room.winner is None:
            if p1.score > p2.score:
                room.winner = p1.user_id
            elif p2.score > p1.score:
                room.winner = p2.user_id
            else:
                if p1.finished_at < p2.finished_at:
                    room.winner = p1.user_id
                elif p2.finished_at < p1.finished_at:
                    room.winner = p2.user_id
                else:
                    room.winner = None

        result = {
            "event": "duel_finished",
            "room_id": room_id,
            "winner": room.winner,
            "finish_reason": room.finish_reason,
            "player1_id": p1.user_id,
            "player2_id": p2.user_id,
            "scores": {
                "player1": p1.score,
                "player2": p2.score,
            },
            "answered": {
                "player1": len(p1.answers),
                "player2": len(p2.answers),
            },
            "xp": {
                "player1": p1.xp_gain,
                "player2": p2.xp_gain,
            },
            "surrendered": {
                "player1": p1.surrendered,
                "player2": p2.surrendered,
            },
            "forfeited": {
                "player1": p1.forfeited,
                "player2": p2.forfeited,
            },
            "finished_at": {
                "player1": p1.finished_at.isoformat() if p1.finished_at else None,
                "player2": p2.finished_at.isoformat() if p2.finished_at else None,
            },
        }

        self.finished_duels[room_id] = result
        self.finished_duels_created_at[room_id] = datetime.now()
        self.duels.pop(room_id, None)
        self.cleanup_finished_duels()

        return result

    async def leave_duel_queue(self, user_id: int):
        self.duel_queue = [p for p in self.duel_queue if p.user_id != user_id]

    async def join_team_queue(self, player: Player, team: str | None = None) -> dict:
        for t in ["team_a", "team_b"]:
            for p in self.team_fight_queue[t]:
                if p.user_id == player.user_id:
                    return {"status": "already_in_queue", "team": t}

        if not team:
            team = (
                "team_a"
                if len(self.team_fight_queue["team_a"]) <= len(self.team_fight_queue["team_b"])
                else "team_b"
            )

        self.team_fight_queue[team].append(player)

        if len(self.team_fight_queue["team_a"]) >= 2 and len(self.team_fight_queue["team_b"]) >= 2:
            room_id = await self.create_team_fight_room()
            return {"status": "ready", "room_id": room_id}

        return {
            "status": "waiting",
            "team": team,
            "queue_size": len(self.team_fight_queue[team]),
        }

    async def create_team_fight_room(self) -> str:
        room_id = f"team_{uuid.uuid4().hex[:8]}"

        room = TeamFightRoom(
            room_id=room_id,
            team_a=self.team_fight_queue["team_a"][:5],
            team_b=self.team_fight_queue["team_b"][:5],
            status="active",
            start_time=datetime.now(),
            total_questions=20,
            time_per_question=10,
        )

        self.team_fight_queue["team_a"] = self.team_fight_queue["team_a"][5:]
        self.team_fight_queue["team_b"] = self.team_fight_queue["team_b"][5:]

        self.team_fights[room_id] = room
        return room_id

    async def set_team_fight_questions(self, room_id: str, questions: List[dict]):
        room = self.team_fights.get(room_id)

        if room:
            room.questions = questions[:20]
            room.total_questions = min(20, len(room.questions))

            if room.questions:
                room.current_word = room.questions[0]

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

        player.answers.append(
            {
                "word_id": room.current_word.get("word_id") if room.current_word else None,
                "answer": answer,
                "is_correct": is_correct,
                "xp_gain": xp_gain if is_correct else 0,
            }
        )

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
                    "scores": {
                        "team_a": room.team_a_score,
                        "team_b": room.team_b_score,
                    },
                }

            if room.question_number < len(room.questions):
                room.current_word = room.questions[room.question_number]

            return {
                "event": "next_question",
                "question": room.current_word,
                "question_number": room.question_number + 1,
                "total_questions": room.total_questions,
                "scores": {
                    "team_a": room.team_a_score,
                    "team_b": room.team_b_score,
                },
            }

        return {
            "event": "waiting_teammates",
            "team_a_answered": team_a_answered,
            "team_b_answered": team_b_answered,
            "team_a_total": len(room.team_a),
            "team_b_total": len(room.team_b),
        }

    async def leave_team_queue(self, user_id: int):
        self.team_fight_queue["team_a"] = [
            p for p in self.team_fight_queue["team_a"] if p.user_id != user_id
        ]
        self.team_fight_queue["team_b"] = [
            p for p in self.team_fight_queue["team_b"] if p.user_id != user_id
        ]


room_manager = RoomManager()
