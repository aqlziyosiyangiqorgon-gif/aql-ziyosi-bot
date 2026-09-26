"""Application configuration using pydantic-settings."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bot environment settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BOT_TOKEN: str = Field(..., description="Telegram bot API token")
    ADMIN_IDS: list[int] = Field(default_factory=list, description="Super admin user IDs")
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./data/bot.db",
        description="Async SQLAlchemy database URL",
    )
    BACKUP_CHAT_ID: int | None = Field(
        default=None,
        description="Target Telegram chat/channel ID for database backups",
    )
    SUB_CACHE_SECONDS: int = Field(default=60, description="Subscription positive cache TTL")
    TIMEZONE: str = Field(default="Asia/Tashkent", description="Timezone name")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: object) -> list[int]:
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",") if p.strip()]
            return [int(p) for p in parts]
        if isinstance(v, (list, tuple, set)):
            return [int(x) for x in v]
        if isinstance(v, int):
            return [v]
        return []

    @property
    def effective_backup_chat_id(self) -> int | None:
        """Return designated backup chat ID or fallback to the first super admin."""
        if self.BACKUP_CHAT_ID:
            return self.BACKUP_CHAT_ID
        if self.ADMIN_IDS:
            return self.ADMIN_IDS[0]
        return None

    @property
    def masked_token(self) -> str:
        """Returns masked token string for safe logging."""
        if not self.BOT_TOKEN or ":" not in self.BOT_TOKEN:
            return "***"
        prefix, secret = self.BOT_TOKEN.split(":", 1)
        return f"{prefix}:***{secret[-4:]}" if len(secret) >= 4 else f"{prefix}:***"


def load_settings() -> Settings:
    """Load settings from environment and .env."""
    return Settings()
