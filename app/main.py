from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.websocket.handlers import handle_websocket

app = FastAPI(
    title="Vocabulary Mini App API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    user_id = websocket.query_params.get("user_id")
    if user_id:
        try:
            await handle_websocket(websocket, int(user_id))
        except WebSocketDisconnect:
            pass
    else:
        await websocket.close()


@app.get("/")
async def root():
    return {"status": "running", "service": "vocab-backend"}


@app.get("/health")
async def health():
    return {"status": "healthy"}