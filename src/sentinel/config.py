from functools import lru_cache
# type: ignore[unused-import]

from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from a .env file if present as early as possible
load_dotenv()


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",  # Ignore any other env vars we don't model explicitly
    )

    # Discord
    discord_token: str  # looks for `DISCORD_TOKEN`
    command_prefix: str = "!"  # `COMMAND_PREFIX`

    # OAuth for web login
    discord_client_id: str
    discord_client_secret: str
    oauth_redirect_uri: str = "http://localhost:8000/callback"

    # Web server
    host: str = "0.0.0.0"  # `HOST`
    port: int = 8000  # `PORT`

    # Database (optional)
    database_url: Optional[str] = None  # `DATABASE_URL`


@lru_cache(maxsize=1)
def get_settings() -> Settings:  # pragma: no cover
    """Return a cached Settings instance to avoid re-parsing env vars."""

    return Settings() 
