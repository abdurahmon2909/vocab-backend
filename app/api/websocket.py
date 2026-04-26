# app/api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.api.deps import get_current_user_ws
from app.websocket.handlers import handle_websocket

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        # Get user from query param or header
        user_id = websocket.query_params.get("user_id")
        if not user_id:
            await websocket.close(code=1008, reason="Missing user_id")
            return

        await handle_websocket(websocket, int(user_id))
    except WebSocketDisconnect:
        pass