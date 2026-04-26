# app/api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket.handlers import handle_websocket

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time features:
    - Duel (1v1)
    - Team Fight (team battle)
    """
    try:
        # Get user_id from query parameter
        user_id = websocket.query_params.get("user_id")

        if not user_id:
            await websocket.close(code=1008, reason="Missing user_id")
            return

        # Validate user_id is integer
        try:
            user_id_int = int(user_id)
        except ValueError:
            await websocket.close(code=1008, reason="Invalid user_id")
            return

        # Handle WebSocket connection
        await handle_websocket(websocket, user_id_int)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass