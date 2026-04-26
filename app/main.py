from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import WebSocket, WebSocketDisconnect

from app.api.routes import router
from app.core.config import settings
from app.websocket.handlers import handle_websocket

app = FastAPI(
    title="Vocabulary Mini App API",
    version="1.0.0",
    description="Telegram Mini App for learning English vocabulary",
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.FRONTEND_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


# WebSocket endpoint – DIRECTLY in main.py
@app.websocket("/ws")
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


@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "vocab-backend",
        "version": "1.0.0",
        "websocket": "/ws",
        "endpoints": [
            "/api/user",
            "/api/stats",
            "/api/leaderboard",
            "/api/collections",
            "/api/books",
            "/api/units/{unit_id}/words",
            "/api/units/{unit_id}/test",
            "/api/weak-words",
            "/api/weak-words/test",
            "/api/answer",
            "/ws (WebSocket)"
        ]
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}