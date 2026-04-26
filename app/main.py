from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings

app = FastAPI(
    title="Vocabulary Mini App API",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 🔥 VAQTINCHA HAMMA DOMENGA RUXSAT
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API router - PREFIX tekshiruvi
app.include_router(router)

@app.get("/")
async def root():
    return {"status": "running", "service": "vocab-backend"}

@app.get("/health")
async def health():
    return {"status": "healthy"}