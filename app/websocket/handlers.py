import json
from datetime import datetime, timedelta

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.models import User, UserXP
from app.services.learning_service import LearningService
from app.services.test_service import TestService
from app.services.xp_service import XPService
from app.services.duel_rating_service import DuelRatingService
from app.websocket.room_manager import Player, room_manager


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

# ELO faqat bitta duel uchun bir marta hisoblanishi kerak.
# finish_duel submit_answer, finish_duel retry yoki disconnect orqali qayta kelishi mumkin.
processed_elo_results: dict[str, dict] = {}
processed_elo_results_created_at: dict[str, datetime] = {}
PROCESSED_ELO_TTL = timedelta(minutes=30)


def cleanup_processed_elo_results() -> None:
    now = datetime.now()

    for key, created_at in list(processed_elo_results_created_at.items()):
        if now - created_at > PROCESSED_ELO_TTL:
            processed_elo_results_created_at.pop(key, None)
            processed_elo_results.pop(key, None)

def _build_elo_key(final_data: dict) -> str:
    room_id = final_data.get("room_id")
    if room_id:
        return f"room:{room_id}"

    p1 = final_data.get("player1_id")
    p2 = final_data.get("player2_id")
    winner = final_data.get("winner")
    scores = final_data.get("scores") or {}
    finished_at = final_data.get("finished_at") or {}

    return (
        f"players:{p1}:{p2}:winner:{winner}:"
        f"scores:{scores.get('player1')}:{scores.get('player2')}:"
        f"finished:{finished_at.get('player1')}:{finished_at.get('player2')}"
    )


async def get_user_duel_profile(user_id: int):
    async with SessionLocal() as db:
        result = await db.execute(
            select(User, UserXP.total_xp)
            .outerjoin(UserXP, UserXP.user_id == User.tg_id)
            .where(User.tg_id == user_id)
        )
        row = result.first()

        if not row:
            rating = await DuelRatingService.get_user_rating_payload(db, user_id)
            return {
                "user_id": user_id,
                "nickname": "Learner",
                "xp": 0,
                "level": 0,
                "rank": None,
                "photo_url": None,
                **rating,
            }

        user, total_xp = row
        total_xp = int(total_xp or 0)
        rating = await DuelRatingService.get_user_rating_payload(db, user_id)

        return {
            "user_id": user_id,
            "nickname": user.nickname or user.first_name or user.username or "Learner",
            "xp": total_xp,
            "level": XPService.level_from_xp(total_xp),
            "rank": rating.get("duel_rank"),
            "photo_url": user.photo_url,
            **rating,
        }
async def enrich_final_data(final_data: dict):
    if not final_data:
        return None

    p1_id = final_data["player1_id"]
    p2_id = final_data["player2_id"]

    p1_profile = await get_user_duel_profile(p1_id)
    p2_profile = await get_user_duel_profile(p2_id)

    return {
        **final_data,
        "profiles": {
            "player1": p1_profile,
            "player2": p2_profile,
        },
    }


def _player_flag(final_data: dict, key: str, player_key: str) -> bool:
    return bool((final_data.get(key) or {}).get(player_key))


async def send_duel_final(final_data: dict):
    if not final_data:
        return

    elo_key = _build_elo_key(final_data)

    # ELO update idempotent: bir duel uchun faqat bir marta yoziladi.
    # Keyingi retry/final chaqiriqlarda oldingi elo_result qayta ishlatiladi.
    if elo_key in processed_elo_results:
        elo_result = processed_elo_results[elo_key]
    else:
        async with SessionLocal() as db:
            elo_result = await DuelRatingService.apply_duel_result(
                db,
                player1_id=final_data["player1_id"],
                player2_id=final_data["player2_id"],
                winner_id=final_data.get("winner"),
            )
            await db.commit()

        processed_elo_results[elo_key] = elo_result
        processed_elo_results_created_at[elo_key] = datetime.now()
        cleanup_processed_elo_results()

        if len(processed_elo_results) > 1000:
            for key in list(processed_elo_results.keys())[:100]:
                processed_elo_results.pop(key, None)
                processed_elo_results_created_at.pop(key, None)

    final_data = {**final_data, "elo_result": elo_result}
    final_data = await enrich_final_data(final_data)

    if not final_data:
        return

    p1_id = final_data["player1_id"]
    p2_id = final_data["player2_id"]

    p1_score = final_data["scores"]["player1"]
    p2_score = final_data["scores"]["player2"]

    p1_answered = final_data["answered"]["player1"]
    p2_answered = final_data["answered"]["player2"]

    p1_xp_gain = final_data["xp"]["player1"]
    p2_xp_gain = final_data["xp"]["player2"]

    p1_profile = final_data["profiles"]["player1"]
    p2_profile = final_data["profiles"]["player2"]
    p1_elo = final_data["elo_result"]["player1"]
    p2_elo = final_data["elo_result"]["player2"]

    # Profile ichida ham ELO delta bo'lsin — frontend final card va badge'lar uchun qulay.
    p1_profile.update(
        {
            "old_elo": p1_elo["old_elo"],
            "elo": p1_elo["new_elo"],
            "elo_change": p1_elo["delta"],
            "rank_title": p1_elo["rank_title"],
            "rank_icon": p1_elo["rank_icon"],
        }
    )
    p2_profile.update(
        {
            "old_elo": p2_elo["old_elo"],
            "elo": p2_elo["new_elo"],
            "elo_change": p2_elo["delta"],
            "rank_title": p2_elo["rank_title"],
            "rank_icon": p2_elo["rank_icon"],
        }
    )

    await manager.send_personal_message(
        {
            **final_data,
            "my_score": p1_score,
            "opponent_score": p2_score,
            "my_answered": p1_answered,
            "opponent_answered": p2_answered,
            "my_xp": p1_xp_gain,
            "opponent_xp": p2_xp_gain,
            "my_profile": p1_profile,
            "opponent_profile": p2_profile,
            "my_elo_delta": p1_elo["delta"],
            "opponent_elo_delta": p2_elo["delta"],
            "my_old_elo": p1_elo["old_elo"],
            "opponent_old_elo": p2_elo["old_elo"],
            "my_new_elo": p1_elo["new_elo"],
            "opponent_new_elo": p2_elo["new_elo"],
            "my_rank_title": p1_elo["rank_title"],
            "my_rank_icon": p1_elo["rank_icon"],
            "opponent_rank_title": p2_elo["rank_title"],
            "opponent_rank_icon": p2_elo["rank_icon"],
            "my_surrendered": _player_flag(final_data, "surrendered", "player1"),
            "opponent_surrendered": _player_flag(final_data, "surrendered", "player2"),
            "my_left": _player_flag(final_data, "forfeited", "player1"),
            "opponent_left": _player_flag(final_data, "forfeited", "player2"),
        },
        p1_id,
    )

    await manager.send_personal_message(
        {
            **final_data,
            "my_score": p2_score,
            "opponent_score": p1_score,
            "my_answered": p2_answered,
            "opponent_answered": p1_answered,
            "my_xp": p2_xp_gain,
            "opponent_xp": p1_xp_gain,
            "my_profile": p2_profile,
            "opponent_profile": p1_profile,
            "my_elo_delta": p2_elo["delta"],
            "opponent_elo_delta": p1_elo["delta"],
            "my_old_elo": p2_elo["old_elo"],
            "opponent_old_elo": p1_elo["old_elo"],
            "my_new_elo": p2_elo["new_elo"],
            "opponent_new_elo": p1_elo["new_elo"],
            "my_rank_title": p2_elo["rank_title"],
            "my_rank_icon": p2_elo["rank_icon"],
            "opponent_rank_title": p1_elo["rank_title"],
            "opponent_rank_icon": p1_elo["rank_icon"],
            "my_surrendered": _player_flag(final_data, "surrendered", "player2"),
            "opponent_surrendered": _player_flag(final_data, "surrendered", "player1"),
            "my_left": _player_flag(final_data, "forfeited", "player2"),
            "opponent_left": _player_flag(final_data, "forfeited", "player1"),
        },
        p2_id,
    )

async def start_duel_room(room_id: str):
    async with SessionLocal() as db:
        questions = await TestService.build_random_questions(db, limit=20)
        await room_manager.set_duel_questions(room_id, questions)

    room = room_manager.duels.get(room_id)

    if not room or not room.player2:
        return

    p1 = room.player1
    p2 = room.player2

    await manager.send_personal_message(
        {
            "event": "duel_started",
            "room_id": room_id,
            "questions": questions,
            "total_questions": room.total_questions,
            "time_per_question": room.time_per_question,
            "my_profile": room_manager.player_to_dict(p1),
            "opponent_profile": room_manager.player_to_dict(p2),
        },
        p1.user_id,
    )

    await manager.send_personal_message(
        {
            "event": "duel_started",
            "room_id": room_id,
            "questions": questions,
            "total_questions": room.total_questions,
            "time_per_question": room.time_per_question,
            "my_profile": room_manager.player_to_dict(p2),
            "opponent_profile": room_manager.player_to_dict(p1),
        },
        p2.user_id,
    )


async def send_online_users(user_id: int):
    await manager.send_personal_message(
        {
            "event": "online_users",
            "users": room_manager.get_online_duel_users(user_id),
        },
        user_id,
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
        xp = int(xp or 0)

        player = Player(
            user_id=user_id,
            nickname=user.nickname or user.first_name or user.username or "Learner",
            xp=xp,
            level=XPService.level_from_xp(xp),
            socket_id=str(user_id),
            photo_url=user.photo_url,
        )

    room_manager.add_online_user(player)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            event = message.get("event")

            print(f"📩 Received: {event} from {user_id}")

            if event == "get_online_users":
                await send_online_users(user_id)

            elif event == "duel_invite":
                target_id = message.get("target_id")

                try:
                    target_id = int(target_id)
                except (TypeError, ValueError):
                    await manager.send_personal_message(
                        {"event": "duel_invite_error", "reason": "invalid_target"},
                        user_id,
                    )
                    continue

                invite_result = room_manager.create_duel_invite(user_id, target_id)

                if not invite_result.get("ok"):
                    reason = invite_result.get("reason")
                    await manager.send_personal_message(
                        {"event": "duel_invite_error", "reason": reason},
                        user_id,
                    )
                    await send_online_users(user_id)
                    continue

                await manager.send_personal_message(
                    {
                        "event": "duel_invite_sent",
                        "target_user": room_manager.player_to_dict(invite_result["target_player"]),
                    },
                    user_id,
                )

                await manager.send_personal_message(
                    {
                        "event": "duel_invite",
                        "from_user": room_manager.player_to_dict(invite_result["from_player"]),
                    },
                    target_id,
                )

            elif event == "duel_reject":
                from_user_id = message.get("from_user_id")

                try:
                    from_user_id = int(from_user_id) if from_user_id is not None else None
                except (TypeError, ValueError):
                    from_user_id = None

                rejected_from_user_id = room_manager.reject_duel_invite(user_id, from_user_id)

                if rejected_from_user_id:
                    await manager.send_personal_message(
                        {
                            "event": "duel_invite_rejected",
                            "target_user_id": user_id,
                        },
                        rejected_from_user_id,
                    )

            elif event == "duel_accept":
                from_user_id = message.get("from_user_id")

                try:
                    from_user_id = int(from_user_id)
                except (TypeError, ValueError):
                    await manager.send_personal_message(
                        {"event": "duel_invite_error", "reason": "invalid_sender"},
                        user_id,
                    )
                    continue

                accept_result = await room_manager.accept_duel_invite(user_id, from_user_id)

                if not accept_result.get("ok"):
                    reason = accept_result.get("reason")
                    await manager.send_personal_message(
                        {"event": "duel_invite_error", "reason": reason},
                        user_id,
                    )
                    await manager.send_personal_message(
                        {"event": "duel_invite_error", "reason": reason},
                        from_user_id,
                    )
                    continue

                await start_duel_room(accept_result["room_id"])

            elif event == "join_duel":
                room_id = await room_manager.join_duel_queue(player)

                if room_id:
                    await start_duel_room(room_id)
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
                answer_session_id = message.get("answer_session_id") or f"{room_type}:{room_id}"

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
                                    "opponent_profile": result.get("opponent_profile"),
                                    "opponent_left": result.get("opponent_left", False),
                                    "opponent_surrendered": result.get("opponent_surrendered", False),
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
                                    "opponent_left": False,
                                    "opponent_surrendered": False,
                                },
                                opponent_id,
                            )

                elif room_type == "team":
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
                            print(f"❌ Team XP save error: {e}")

                    result = await room_manager.submit_team_answer(
                        room_id=room_id,
                        user_id=user_id,
                        answer=answer,
                        is_correct=is_correct,
                        xp_gain=saved_xp,
                    )

                    if result:
                        room = room_manager.team_fights.get(room_id)
                        recipients = []

                        if room:
                            recipients = room.team_a + room.team_b

                        if result.get("event") == "team_fight_finished":
                            recipients = []
                            for connection_user_id in manager.active_connections.keys():
                                try:
                                    recipients.append(Player(
                                        user_id=int(connection_user_id),
                                        nickname="",
                                        xp=0,
                                        level=0,
                                        socket_id=str(connection_user_id),
                                    ))
                                except ValueError:
                                    pass

                        for p in recipients:
                            await manager.send_personal_message(result, p.user_id)

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
                                "opponent_left": result.get("opponent_left", False),
                                "opponent_surrendered": result.get("opponent_surrendered", False),
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

            elif event == "duel_surrender":
                room_id = message.get("room_id")
                result = await room_manager.surrender_duel(room_id, user_id)

                if result and result.get("type") == "finished":
                    await send_duel_final(result["result"])

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
        print(f"WebSocketDisconnect: {user_id}")

    finally:
        manager.disconnect(user_id)
        room_manager.remove_online_user(user_id)

        disconnect_result = await room_manager.handle_disconnect(user_id)

        if disconnect_result:
            if disconnect_result.get("type") == "finished":
                await send_duel_final(disconnect_result["result"])
            elif disconnect_result.get("type") == "opponent_left":
                await manager.send_personal_message(
                    {
                        "event": "opponent_left",
                        "room_id": disconnect_result["room_id"],
                        "left_user_id": disconnect_result["left_user_id"],
                        "opponent_left": True,
                    },
                    disconnect_result["opponent_id"],
                )
