from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

if TYPE_CHECKING:  # pragma: no cover
    from sentinel.bot import SentinelBot


class ConfigResponse(BaseModel):
    prefix: str


def get_app(bot: "SentinelBot") -> FastAPI:  # noqa: D401
    """Return a FastAPI app instance bound to the provided bot."""

    app = FastAPI(title="Sentinel Config API", version="0.1.0")

    @app.get("/health", tags=["misc"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/config", tags=["config"], response_model=ConfigResponse)
    async def read_config() -> ConfigResponse:
        from sentinel.config import get_settings
        settings = get_settings()
        return ConfigResponse(prefix=settings.command_prefix)

    @app.post("/config/prefix", tags=["config"])
    async def update_prefix(new_prefix: str):
        if not new_prefix:
            raise HTTPException(status_code=400, detail="Prefix cannot be empty.")
        # Example: update the command prefix at runtime
        bot.command_prefix = new_prefix  # type: ignore[assignment]
        return {"prefix": new_prefix}

    @app.get("/")
    async def root():
        return {"message": "Sentinel is running"}

    return app 