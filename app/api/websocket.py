from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.security import validate_telegram
from app.websocket.handlers import handle_websocket

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    init_data = websocket.query_params.get("init_data")
    user_id = None

    if init_data:
        try:
            tg = validate_telegram(init_data, settings.BOT_TOKEN)
            user_id = int(tg["id"])
        except Exception:
            await websocket.close(code=1008, reason="Invalid Telegram auth")
            return

    elif settings.DEBUG:
        raw_user_id = websocket.query_params.get("user_id")
        if raw_user_id:
            try:
                user_id = int(raw_user_id)
            except ValueError:
                await websocket.close(code=1008, reason="Invalid user_id")
                return

    if not user_id:
        await websocket.close(code=1008, reason="Missing auth")
        return

    try:
        await handle_websocket(websocket, user_id)
    except WebSocketDisconnect:
        pass