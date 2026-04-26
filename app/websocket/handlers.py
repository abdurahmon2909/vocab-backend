import json

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.models import User, UserXP
from app.services.test_service import TestService
from app.services.learning_service import LearningService
from app.websocket.room_manager import room_manager, Player


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[str(user_id)] = websocket
        print(f"✅ User {user_id} connected")

    def disconnect(self, user_id: int):
        self.active_connections.pop(str(user_id), None)
        print(f"❌ User {user_id} disconnected")

    async def send_personal_message(self, message: dict, user_id: int):
        websocket = self.active_connections.get(str(user_id))
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"❌ Send error to {user_id}: {e}")


manager = ConnectionManager()


async def send_duel_final(final_data: dict):
    if not final_data:
        return

    p1_id = final_data["player1_id"]
    p2_id = final_data["player2_id"]

    p1_score = final_data["scores"]["player1"]
    p2_score = final_data["scores"]["player2"]

    p1_xp = final_data["xp"]["player1"]
    p2_xp = final_data["xp"]["player2"]

    await manager.send_personal_message(
        {
            **final_data,
            "my_score": p1_score,
            "opponent_score": p2_score,
            "my_answered": final_data["answered"]["player1"],
            "opponent_answered": final_data["answered"]["player2"],
            "my_xp": p1_xp,
            "opponent_xp": p2_xp,
        },
        p1_id,
    )

    await manager.send_personal_message(
        {
            **final_data,
            "my_score": p2_score,
            "opponent_score": p1_score,
            "my_answered": final_data["answered"]["player2"],
            "opponent_answered": final_data["answered"]["player1"],
            "my_xp": p2_xp,
            "opponent_xp": p1_xp,
        },
        p2_id,
    )


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

                    room = room_manager.duels.get(room_id)

                    if room:
                        for p in [room.player1, room.player2]:
                            await manager.send_personal_message(
                                {
                                    "event": "duel_started",
                                    "room_id": room_id,
                                    "questions": questions,
                                    "total_questions": 20,
                                    "time_per_question": 10,
                                },
                                p.user_id,
                            )
                else:
                    await manager.send_personal_message(
                        {
                            "event": "duel_queue",
                            "status": "waiting",
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

                word_id = message.get("word_id")
                unit_id = message.get("unit_id")
                mode = message.get("mode") or "duel_test"
                correct_answer = message.get("correct_answer")

                saved_xp = 0

                if room_type == "duel":
                    if word_id and unit_id:
                        try:
                            async with SessionLocal() as db:
                                res = await LearningService.process_answer(
                                    db=db,
                                    user_id=user_id,
                                    word_id=int(word_id),
                                    unit_id=int(unit_id),
                                    mode=mode,
                                    is_correct=is_correct,
                                    user_answer=answer,
                                    correct_answer=correct_answer,
                                )
                                saved_xp = int(res.get("xp_gain", 0))
                        except Exception as e:
                            print(f"❌ XP save error: {e}")

                    result = await room_manager.submit_duel_answer(
                        room_id=room_id,
                        user_id=user_id,
                        answer=answer,
                        is_correct=is_correct,
                        xp_gain=saved_xp,
                        question_index=question_index,
                        time_left=time_left,
                    )

                    if result:
                        if result.get("type") == "finished":
                            await send_duel_final(result["result"])

                        elif result.get("type") == "progress":
                            player_id = result["player_id"]
                            opponent_id = result["opponent_id"]

                            await manager.send_personal_message(
                                {
                                    "event": "answer_saved",
                                    "my_score": result["player_score"],
                                    "opponent_score": result["opponent_score"],
                                    "my_answered": result["player_answered"],
                                    "opponent_answered": result["opponent_answered"],
                                    "opponent_finished": result["opponent_finished"],
                                    "my_xp": result["player_xp"],
                                    "opponent_xp": result["opponent_xp"],
                                },
                                player_id,
                            )

                            await manager.send_personal_message(
                                {
                                    "event": "duel_progress",
                                    "my_score": result["opponent_score"],
                                    "opponent_score": result["player_score"],
                                    "my_answered": result["opponent_answered"],
                                    "opponent_answered": result["player_answered"],
                                    "opponent_finished": result["player_finished"],
                                    "my_xp": result["opponent_xp"],
                                    "opponent_xp": result["player_xp"],
                                },
                                opponent_id,
                            )

            elif event == "finish_duel":
                room_id = message.get("room_id")
                result = await room_manager.mark_player_finished(room_id, user_id)

                if result:
                    if result.get("type") == "finished":
                        await send_duel_final(result["result"])

                    elif result.get("type") == "progress":
                        player_id = result["player_id"]
                        opponent_id = result["opponent_id"]

                        await manager.send_personal_message(
                            {
                                "event": "player_finished",
                                "my_score": result["player_score"],
                                "opponent_score": result["opponent_score"],
                                "my_answered": result["player_answered"],
                                "opponent_answered": result["opponent_answered"],
                                "opponent_finished": result["opponent_finished"],
                                "my_xp": result["player_xp"],
                                "opponent_xp": result["opponent_xp"],
                            },
                            player_id,
                        )

                        await manager.send_personal_message(
                            {
                                "event": "duel_progress",
                                "my_score": result["opponent_score"],
                                "opponent_score": result["player_score"],
                                "my_answered": result["opponent_answered"],
                                "opponent_answered": result["player_answered"],
                                "opponent_finished": result["player_finished"],
                                "my_xp": result["opponent_xp"],
                                "opponent_xp": result["player_xp"],
                            },
                            opponent_id,
                        )

            elif event == "join_team":
                team = message.get("team")
                result = await room_manager.join_team_queue(player, team)

                if result.get("status") == "ready":
                    room_id = result["room_id"]

                    async with SessionLocal() as db:
                        questions = await TestService.build_random_questions(db, limit=20)
                        await room_manager.set_team_fight_questions(room_id, questions)

                    room = room_manager.team_fights.get(room_id)

                    if room:
                        for p in room.team_a + room.team_b:
                            await manager.send_personal_message(
                                {
                                    "event": "team_fight_started",
                                    "room_id": room_id,
                                    "questions": questions,
                                    "total_questions": 20,
                                    "time_per_question": 10,
                                    "team_a": [
                                        {"user_id": x.user_id, "nickname": x.nickname}
                                        for x in room.team_a
                                    ],
                                    "team_b": [
                                        {"user_id": x.user_id, "nickname": x.nickname}
                                        for x in room.team_b
                                    ],
                                },
                                p.user_id,
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