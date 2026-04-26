from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.websocket import router as ws_router
from app.core.config import settings

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
app.include_router(ws_router)

# Include WebSocket routes
app.include_router(ws_router)


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