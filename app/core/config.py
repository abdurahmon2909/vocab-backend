import os


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def parse_origins(value: str) -> list[str]:
    return [
        origin.strip()
        for origin in value.split(",")
        if origin.strip()
    ]


class Settings:
    def __init__(self):
        self.DATABASE_URL = normalize_database_url(self.require("DATABASE_URL"))
        self.BOT_TOKEN = self.require("BOT_TOKEN")
        self.FRONTEND_ORIGINS = parse_origins(self.require("FRONTEND_ORIGINS"))

        self.ADMIN_IDS = [
            int(item)
            for item in os.getenv("ADMIN_IDS", "").split(",")
            if item.strip()
        ]

        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        self.SECRET_KEY = os.getenv("SECRET_KEY", "")
        self.API_VERSION = os.getenv("API_VERSION", "1.0.0")

        self.BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
        self.WEB_APP_URL = os.getenv("WEB_APP_URL", "").strip()
        self.BOT_INTERNAL_SECRET = os.getenv("BOT_INTERNAL_SECRET", "").strip()

    @staticmethod
    def require(key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise RuntimeError(f"{key} environment variable is required")
        return value


settings = Settings()