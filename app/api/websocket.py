from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket.handlers import handle_websocket

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print("🔌 New WebSocket connection request")
    try:
        user_id = websocket.query_params.get("user_id")
        print(f"User ID from query: {user_id}")

        if not user_id:
            print("❌ No user_id provided")
            await websocket.close(code=1008, reason="Missing user_id")
            return

        try:
            user_id_int = int(user_id)
            print(f"✅ Valid user_id: {user_id_int}")
        except ValueError:
            print(f"❌ Invalid user_id: {user_id}")
            await websocket.close(code=1008, reason="Invalid user_id")
            return

        await handle_websocket(websocket, user_id_int)

    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass