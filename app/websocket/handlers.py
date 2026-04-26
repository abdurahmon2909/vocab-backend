import json
from typing import Dict
from fastapi import WebSocket, WebSocketDisconnect

from app.db.session import SessionLocal
from app.models.models import User, UserXP
from app.services.test_service import TestService
from app.services.learning_service import LearningService
from app.websocket.room_manager import room_manager, Player


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_socket_map: Dict[int, str] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[str(user_id)] = websocket
        self.user_socket_map[user_id] = str(user_id)
        print(f"✅ User {user_id} connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, user_id: int):
        if str(user_id) in self.active_connections:
            del self.active_connections[str(user_id)]
        if user_id in self.user_socket_map:
            del self.user_socket_map[user_id]
        print(f"❌ User {user_id} disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, user_id: int):
        if str(user_id) in self.active_connections:
            try:
                await self.active_connections[str(user_id)].send_json(message)
                print(f"📨 Sent to {user_id}: {message.get('event')}")
            except Exception as e:
                print(f"Error sending to {user_id}: {e}")

    async def broadcast_to_room(self, message: dict, room_id: str, exclude_user_id: int = None):
        # For duel
        room = room_manager.duels.get(room_id)
        if room:
            if room.player1 and room.player1.user_id != exclude_user_id:
                await self.send_personal_message(message, room.player1.user_id)
            if room.player2 and room.player2.user_id != exclude_user_id:
                await self.send_personal_message(message, room.player2.user_id)
            return

        # For team fight
        team_room = room_manager.team_fights.get(room_id)
        if team_room:
            for player in team_room.team_a + team_room.team_b:
                if player.user_id != exclude_user_id:
                    await self.send_personal_message(message, player.user_id)


manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket, user_id: int):
    await manager.connect(websocket, user_id)

    # Get user info from DB
    async with SessionLocal() as db:
        user_result = await db.execute(
            select(User, UserXP.total_xp)
            .outerjoin(UserXP, UserXP.user_id == User.tg_id)
            .where(User.tg_id == user_id)
        )
        row = user_result.first()

        if not row:
            await websocket.close(code=1008, reason="User not found")
            return

        user, xp = row
        player = Player(
            user_id=user_id,
            nickname=user.nickname or user.first_name or user.username or "Learner",
            xp=xp or 0,
            level=0,
            socket_id=str(user_id)
        )

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            event = message.get("event")

            print(f"📩 Received from {user_id}: {event}")

            if event == "join_duel":
                room_id = await room_manager.join_duel_queue(player)

                if room_id:
                    # Get questions for duel (20 questions)
                    async with SessionLocal() as db:
                        questions = await TestService.build_random_questions(db, limit=20)
                        await room_manager.set_duel_questions(room_id, questions)

                    await manager.broadcast_to_room(
                        {
                            "event": "duel_started",
                            "room_id": room_id,
                            "questions": questions,
                            "total_questions": 20
                        },
                        room_id
                    )
                else:
                    await manager.send_personal_message(
                        {"event": "duel_queue", "status": "waiting"},
                        user_id
                    )

            elif event == "join_team":
                team = message.get("team")
                result = await room_manager.join_team_queue(player, team)

                if result.get("status") == "ready":
                    room_id = result["room_id"]
                    # Get questions for team fight (20 questions)
                    async with SessionLocal() as db:
                        questions = await TestService.build_random_questions(db, limit=20)
                        await room_manager.set_team_fight_questions(room_id, questions)

                    await manager.broadcast_to_room(
                        {
                            "event": "team_fight_started",
                            "room_id": room_id,
                            "questions": questions,
                            "total_questions": 20,
                            "team_a": [{"user_id": p.user_id, "nickname": p.nickname} for p in
                                       room_manager.team_fights[room_id].team_a],
                            "team_b": [{"user_id": p.user_id, "nickname": p.nickname} for p in
                                       room_manager.team_fights[room_id].team_b]
                        },
                        room_id
                    )
                else:
                    await manager.send_personal_message(
                        {
                            "event": "team_queue",
                            "status": result["status"],
                            "team": result.get("team"),
                            "queue_size": result.get("queue_size", 0)
                        },
                        user_id
                    )

            elif event == "submit_answer":
                room_id = message.get("room_id")
                room_type = message.get("room_type")
                answer = message.get("answer")
                word_id = message.get("word_id")
                unit_id = message.get("unit_id")
                mode = message.get("mode")
                is_correct = message.get("is_correct")

                xp_gain = LearningService.xp_for_answer(is_correct, mode)

                if room_type == "duel":
                    result = await room_manager.submit_duel_answer(room_id, user_id, answer, is_correct, xp_gain)
                    if result:
                        await manager.broadcast_to_room(result, room_id, user_id)

                elif room_type == "team":
                    result = await room_manager.submit_team_answer(room_id, user_id, answer, is_correct, xp_gain)
                    if result:
                        await manager.broadcast_to_room(result, room_id, user_id)

            elif event == "leave_queue":
                queue_type = message.get("queue_type")
                if queue_type == "duel":
                    await room_manager.leave_duel_queue(user_id)
                elif queue_type == "team":
                    await room_manager.leave_team_queue(user_id)

                await manager.send_personal_message(
                    {"event": "left_queue", "queue_type": queue_type},
                    user_id
                )

    except WebSocketDisconnect:
        manager.disconnect(user_id)
        await room_manager.leave_duel_queue(user_id)
        await room_manager.leave_team_queue(user_id)