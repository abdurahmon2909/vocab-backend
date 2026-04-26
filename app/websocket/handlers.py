import json

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.models import User, UserXP
from app.services.test_service import TestService
from app.websocket.room_manager import room_manager, Player


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[str(user_id)] = websocket
        print(f"✅ User {user_id} connected")

    def disconnect(self, user_id: int):
        if str(user_id) in self.active_connections:
            del self.active_connections[str(user_id)]
        print(f"❌ User {user_id} disconnected")

    async def send_personal_message(self, message: dict, user_id: int):
        websocket = self.active_connections.get(str(user_id))
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"❌ Send error to {user_id}: {e}")

    async def broadcast_to_room(self, message: dict, room_id: str, exclude_user_id: int | None = None):
        room = room_manager.duels.get(room_id)

        if room:
            if room.player1 and room.player1.user_id != exclude_user_id:
                await self.send_personal_message(message, room.player1.user_id)

            if room.player2 and room.player2.user_id != exclude_user_id:
                await self.send_personal_message(message, room.player2.user_id)

            return

        team_room = room_manager.team_fights.get(room_id)

        if team_room:
            for player in team_room.team_a + team_room.team_b:
                if player.user_id != exclude_user_id:
                    await self.send_personal_message(message, player.user_id)


manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket, user_id: int):
    await manager.connect(websocket, user_id)

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
            nickname=user.nickname or user.first_name or "Learner",
            xp=xp or 0,
            level=0,
            socket_id=str(user_id),
        )

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            event = message.get("event")

            print(f"📩 Received: {event} from {user_id}")

            if event == "join_duel":
                room_id = await room_manager.join_duel_queue(player)

                if room_id:
                    async with SessionLocal() as db:
                        questions = await TestService.build_random_questions(db, limit=20)
                        await room_manager.set_duel_questions(room_id, questions)

                    await manager.broadcast_to_room(
                        {
                            "event": "duel_started",
                            "room_id": room_id,
                            "questions": questions,
                            "total_questions": 20,
                            "time_per_question": 10,
                        },
                        room_id,
                    )
                else:
                    await manager.send_personal_message(
                        {
                            "event": "duel_queue",
                            "status": "waiting",
                        },
                        user_id,
                    )

            elif event == "join_team":
                team = message.get("team")
                result = await room_manager.join_team_queue(player, team)

                if result.get("status") == "ready":
                    room_id = result["room_id"]

                    async with SessionLocal() as db:
                        questions = await TestService.build_random_questions(db, limit=20)
                        await room_manager.set_team_fight_questions(room_id, questions)

                    await manager.broadcast_to_room(
                        {
                            "event": "team_fight_started",
                            "room_id": room_id,
                            "questions": questions,
                            "total_questions": 20,
                            "time_per_question": 10,
                            "team_a": [
                                {"user_id": p.user_id, "nickname": p.nickname}
                                for p in room_manager.team_fights[room_id].team_a
                            ],
                            "team_b": [
                                {"user_id": p.user_id, "nickname": p.nickname}
                                for p in room_manager.team_fights[room_id].team_b
                            ],
                        },
                        room_id,
                    )
                else:
                    await manager.send_personal_message(
                        {
                            "event": "team_queue",
                            "status": result["status"],
                            "team": result.get("team"),
                        },
                        user_id,
                    )

            elif event == "submit_answer":
                room_id = message.get("room_id")
                room_type = message.get("room_type")
                answer = message.get("answer")
                is_correct = bool(message.get("is_correct"))
                question_index = int(message.get("question_index", 0))
                time_left = float(message.get("time_left", 0))
                xp_gain = 10 if is_correct else 2

                if room_type == "duel":
                    result = await room_manager.submit_duel_answer(
                        room_id=room_id,
                        user_id=user_id,
                        answer=answer,
                        is_correct=is_correct,
                        xp_gain=xp_gain,
                        question_index=question_index,
                        time_left=time_left,
                    )

                    if result:
                        if result.get("event") == "duel_finished":
                            await manager.broadcast_to_room(result, room_id)
                        else:
                            await manager.send_personal_message(result, user_id)

                elif room_type == "team":
                    result = await room_manager.submit_team_answer(
                        room_id,
                        user_id,
                        answer,
                        is_correct,
                        xp_gain,
                    )

                    if result:
                        await manager.broadcast_to_room(result, room_id, user_id)

            elif event == "leave_queue":
                queue_type = message.get("queue_type")

                if queue_type == "duel":
                    await room_manager.leave_duel_queue(user_id)
                elif queue_type == "team":
                    await room_manager.leave_team_queue(user_id)

                await manager.send_personal_message(
                    {
                        "event": "left_queue",
                        "queue_type": queue_type,
                    },
                    user_id,
                )

    except WebSocketDisconnect:
        manager.disconnect(user_id)
        await room_manager.leave_duel_queue(user_id)
        await room_manager.leave_team_queue(user_id)