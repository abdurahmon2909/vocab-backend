import os


class Settings:
    def __init__(self):
        self.DATABASE_URL = self.require("DATABASE_URL")
        self.BOT_TOKEN = self.require("BOT_TOKEN")
        self.FRONTEND_ORIGIN = self.require("FRONTEND_ORIGIN")

    @staticmethod
    def require(key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise RuntimeError(f"{key} environment variable is required")
        return value


settings = Settings()