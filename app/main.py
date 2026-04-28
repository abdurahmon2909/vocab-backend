from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.security import validate_telegram
from app.websocket.handlers import handle_websocket

app = FastAPI(
    title="Vocabulary Mini App API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.websocket("/ws")
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


@app.get("/")
async def root():
    return {"status": "running", "service": "vocab-backend"}


@app.get("/health")
async def health():
    return {"status": "healthy"}