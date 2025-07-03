from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request, Body
from pydantic import BaseModel
import secrets
from urllib.parse import urlencode

import httpx
from fastapi.responses import HTMLResponse, RedirectResponse
from sentinel.config import get_settings
from sentinel.utils.storage import load_guild_config, save_guild_config
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path

if TYPE_CHECKING:  # pragma: no cover
    from sentinel.bot import SentinelBot


class ConfigResponse(BaseModel):
    prefix: str


# Role icon payload model (used by REST endpoints)
class RoleIconEntry(BaseModel):
    role_id: str
    emoji: str
    priority: int | None = 0


class NameFormatPayload(BaseModel):
    name_format: str


class TogglePayload(BaseModel):
    enabled: bool


# Models for voice auto channel feature ---------------------------------


class VoiceAutoConfigPayload(BaseModel):
    generator_channel_id: str
    target_category_id: str
    name_pattern: str | None = "{username}"


def get_app(bot: SentinelBot) -> FastAPI:  # noqa: D401
    """Return a FastAPI app instance bound to the provided bot."""

    app = FastAPI(title="Sentinel Config API", version="0.1.0")

    # Mount static files (CSS/JS)
    static_path = Path(__file__).parent / "static"
    static_path.mkdir(parents=True, exist_ok=True)
    templates_path = Path(__file__).parent / "templates"
    templates_path.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_path), name="static")
    templates = Jinja2Templates(directory=str(templates_path))

    # Compile SCSS to CSS once at startup (non-blocking)
    try:
        from sentinel.utils.assets import compile_scss  # local import to avoid cost if unused

        static_dir = Path(__file__).parent / "static"
        compile_scss(static_dir / "scss" / "sentinel.scss", static_dir / "css" / "sentinel.css")
    except Exception as _:
        # If Sass compilation fails we continue with last generated CSS
        pass

    # ------------------------------------------------------------------
    # Routes are defined in dedicated modules under ``sentinel.web.routes``.
    # Expose *bot* and *templates* via the application state so the routers
    # can access them without creating import cycles.
    # ------------------------------------------------------------------

    app.state.bot = bot
    app.state.templates = templates

    # Register all routers and finish early so the legacy inline route
    # definitions below are skipped (they are kept for reference but never
    # executed).
    from .routes import register_routes

    register_routes(app)

    return app
