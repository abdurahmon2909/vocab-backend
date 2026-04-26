import os


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


class Settings:
    def __init__(self):
        self.DATABASE_URL = normalize_database_url(self.require("DATABASE_URL"))
        self.BOT_TOKEN = self.require("BOT_TOKEN")
        self.FRONTEND_ORIGINS = self.require("FRONTEND_ORIGINS").split(",")

    @staticmethod
    def require(key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise RuntimeError(f"{key} environment variable is required")
        return value


settings = Settings()