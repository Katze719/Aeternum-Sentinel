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

    @app.get("/", response_class=HTMLResponse, tags=["ui"])
    async def landing(request: Request):
        return templates.TemplateResponse("landing.html", {"request": request})

    @app.get("/health", tags=["misc"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/config", tags=["config"], response_model=ConfigResponse)
    async def read_config() -> ConfigResponse:
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

    # -------------------- OAuth routes --------------------

    OAUTH_SCOPE = "identify guilds"
    DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
    DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
    DISCORD_USER_ENDPOINT = "https://discord.com/api/users/@me"

    _state_store: set[str] = set()
    _session_store: dict[str, dict] = {}

    SESSION_COOKIE = "sentinel_session"

    def _build_authorize_url(state: str, settings):
        params = {
            "client_id": settings.discord_client_id,
            "redirect_uri": settings.oauth_redirect_uri,
            "response_type": "code",
            "scope": OAUTH_SCOPE,
            "state": state,
            "prompt": "consent",
        }
        return f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}"

    @app.get("/login", tags=["auth"])
    async def login():
        """Redirect the user to Discord's OAuth2 authorization page."""

        settings = get_settings()
        state = secrets.token_urlsafe(16)
        _state_store.add(state)
        url = _build_authorize_url(state, settings)
        return RedirectResponse(url)

    @app.get("/callback", tags=["auth"])
    async def oauth_callback(code: str, state: str):
        """Handle redirect from Discord OAuth2 flow, exchange code for token and fetch user info."""

        if state not in _state_store:
            raise HTTPException(status_code=400, detail="Invalid state parameter.")
        _state_store.discard(state)

        settings = get_settings()

        data = {
            "client_id": settings.discord_client_id,
            "client_secret": settings.discord_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.oauth_redirect_uri,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        async with httpx.AsyncClient() as client:
            token_resp = await client.post(DISCORD_TOKEN_URL, data=data, headers=headers)
            if token_resp.status_code != 200:
                raise HTTPException(status_code=token_resp.status_code, detail="Failed to obtain access token")

            token_json = token_resp.json()
            access_token = token_json["access_token"]

            user_resp = await client.get(
                DISCORD_USER_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_resp.status_code != 200:
                raise HTTPException(status_code=user_resp.status_code, detail="Failed to fetch user info")

            user = user_resp.json()

        # Persist simple session (in-memory)
        session_id = secrets.token_urlsafe(24)
        _session_store[session_id] = {
            "access_token": access_token,
            "user": user,
        }

        response = RedirectResponse(url="/dashboard")
        response.set_cookie(SESSION_COOKIE, session_id, max_age=60 * 60 * 24, httponly=True)
        return response

    # -------------------- Auth-required helper --------------------

    def _get_session(request: Request) -> dict | None:  # pragma: no cover
        sid = request.cookies.get(SESSION_COOKIE)
        if sid and sid in _session_store:
            return _session_store[sid]
        return None

    # -------------------- Permission helpers --------------------

    def _require_admin(guild_id: int, request: Request) -> dict:  # pragma: no cover
        """Validate that the current session user has administrator (or manage_guild) permissions
        in the specified guild. Raises HTTPException if the requirement is not met.

        Returns the active session dictionary for further use inside the endpoint.
        """
        session = _get_session(request)
        if not session:
            raise HTTPException(status_code=401, detail="Authentication required.")

        guild = bot.get_guild(guild_id)
        if guild is None:
            raise HTTPException(status_code=404, detail="Guild not found or bot not in guild.")

        member = guild.get_member(int(session["user"]["id"]))
        if member is None:
            raise HTTPException(status_code=403, detail="User not in guild.")

        perms = member.guild_permissions
        if not (perms.administrator or perms.manage_guild):
            raise HTTPException(status_code=403, detail="Administrator permissions required.")

        return session

    # -------------------- Dashboard --------------------

    @app.get("/dashboard", response_class=HTMLResponse, tags=["ui"])
    async def dashboard(request: Request):
        session = _get_session(request)
        if not session:
            return RedirectResponse("/")

        user = session["user"]
        access_token = session["access_token"]

        # Fetch user's guilds
        async with httpx.AsyncClient() as client:
            guilds_resp = await client.get(
                "https://discord.com/api/users/@me/guilds",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if guilds_resp.status_code != 200:
                raise HTTPException(status_code=guilds_resp.status_code, detail="Failed to fetch guilds")

            user_guilds = guilds_resp.json()

        bot_guild_ids = {g.id for g in bot.guilds}
        common_guilds = [g for g in user_guilds if int(g["id"]) in bot_guild_ids]

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "guilds": common_guilds,
            },
        )

    @app.get("/guilds/{guild_id}", response_class=HTMLResponse, tags=["ui"])
    async def guild_settings(guild_id: int, request: Request):
        session = _require_admin(guild_id, request)

        guild = bot.get_guild(guild_id)
        if guild is None:
            raise HTTPException(status_code=404, detail="Guild not found or bot not in guild.")

        cfg = load_guild_config(guild_id)
        role_icons = cfg.get("role_icons", {})

        # Prepare roles for dropdown (exclude @everyone)
        roles = [
            {"id": r.id, "name": r.name}
            for r in guild.roles
            if not r.is_default()
        ]

        voice_channels = [
            {"id": str(ch.id), "name": ch.name}
            for ch in guild.voice_channels
        ]

        categories = [
            {"id": str(cat.id), "name": cat.name}
            for cat in guild.categories
        ]

        vcuc_cfg = cfg.get("voice_channel_user_creation_config", {})
        vcuc_enabled = cfg.get("voice_channel_user_creation_enabled", False)

        voice_channel_names = {str(ch['id']): ch['name'] for ch in voice_channels}
        category_names = {str(cat['id']): cat['name'] for cat in categories}

        return templates.TemplateResponse(
            "guild_settings.html",
            {
                "request": request,
                "guild": guild,
                "role_icons": role_icons,
                "roles": roles,
                "role_names": {str(r['id']): r['name'] for r in roles},
                "cfg_format": cfg.get("name_format", "{username} [{icons}]"),
                "icon_enabled": cfg.get("role_icon_enabled", False),
                "voice_channels": voice_channels,
                "categories": categories,
                "vcuc_cfg": vcuc_cfg,
                "vcuc_enabled": vcuc_enabled,
                "voice_channel_names": voice_channel_names,
                "category_names": category_names,
            },
        )

    # -------------------- Data models --------------------

    @app.get("/guilds/{guild_id}/role-icons", tags=["config"])
    async def get_role_icons(guild_id: int, request: Request):
        _require_admin(guild_id, request)
        cfg = load_guild_config(guild_id)
        return cfg.get("role_icons", {})

    @app.post("/guilds/{guild_id}/role-icons", tags=["config"])
    async def add_or_update_role_icon(guild_id: int, request: Request, entry: RoleIconEntry = Body(...)):
        _require_admin(guild_id, request)
        cfg = load_guild_config(guild_id)
        role_icons = cfg.setdefault("role_icons", {})
        role_icons[str(entry.role_id)] = {"emoji": entry.emoji, "priority": entry.priority}
        save_guild_config(guild_id, cfg)
        return {"status": "ok"}

    @app.delete("/guilds/{guild_id}/role-icons/{role_id}", tags=["config"])
    async def delete_role_icon(guild_id: int, role_id: int, request: Request):
        _require_admin(guild_id, request)
        cfg = load_guild_config(guild_id)
        role_icons = cfg.get("role_icons", {})
        role_icons.pop(str(role_id), None)
        save_guild_config(guild_id, cfg)
        return {"status": "deleted"}

    @app.get("/guilds/{guild_id}/name-format", tags=["config"])
    async def get_name_format(guild_id: int, request: Request):
        _require_admin(guild_id, request)
        cfg = load_guild_config(guild_id)
        return {"name_format": cfg.get("name_format", "{username} [{icons}]")}

    @app.post("/guilds/{guild_id}/name-format", tags=["config"])
    async def set_name_format(guild_id: int, payload: NameFormatPayload, request: Request):
        _require_admin(guild_id, request)
        cfg = load_guild_config(guild_id)
        cfg["name_format"] = payload.name_format
        save_guild_config(guild_id, cfg)
        return {"status": "ok"}

    # Enable/disable role icon feature

    @app.get("/guilds/{guild_id}/role-icons-enabled", tags=["config"])
    async def get_enabled(guild_id: int, request: Request):
        _require_admin(guild_id, request)
        cfg = load_guild_config(guild_id)
        return {"enabled": cfg.get("role_icon_enabled", False)}

    @app.post("/guilds/{guild_id}/role-icons-enabled", tags=["config"])
    async def set_enabled(guild_id: int, payload: TogglePayload, request: Request):
        _require_admin(guild_id, request)
        cfg = load_guild_config(guild_id)
        cfg["role_icon_enabled"] = payload.enabled
        save_guild_config(guild_id, cfg)
        return {"status": "ok"}

    # -------------------- Voice channel user creation config --------------------

    @app.get("/guilds/{guild_id}/voice-channel-user-creation-config", tags=["config"])
    async def get_voice_channel_user_creation_config(guild_id: int, request: Request):
        """Return mapping of generator_channel_id -> {target_category_id, name_pattern}."""
        _require_admin(guild_id, request)
        cfg = load_guild_config(guild_id)
        return cfg.get("voice_channel_user_creation_config", {})

    @app.post("/guilds/{guild_id}/voice-channel-user-creation-config", tags=["config"])
    async def upsert_voice_channel_user_creation_config(guild_id: int, payload: VoiceAutoConfigPayload, request: Request):
        """Add or update a generator-channel configuration."""
        _require_admin(guild_id, request)
        cfg = load_guild_config(guild_id)
        vacfg = cfg.setdefault("voice_channel_user_creation_config", {})
        vacfg[payload.generator_channel_id] = {
            "target_category_id": payload.target_category_id,
            "name_pattern": payload.name_pattern or "{username}",
        }
        save_guild_config(guild_id, cfg)
        return {"status": "ok"}

    @app.delete("/guilds/{guild_id}/voice-channel-user-creation-config/{generator_id}", tags=["config"])
    async def delete_voice_channel_user_creation_config(guild_id: int, generator_id: int, request: Request):
        _require_admin(guild_id, request)
        cfg = load_guild_config(guild_id)
        vacfg = cfg.get("voice_channel_user_creation_config", {})
        vacfg.pop(str(generator_id), None)
        save_guild_config(guild_id, cfg)
        return {"status": "deleted"}

    # Enable/disable voice auto channel feature

    @app.get("/guilds/{guild_id}/voice-channel-user-creation-enabled", tags=["config"])
    async def get_voice_user_creation_enabled(guild_id: int, request: Request):
        _require_admin(guild_id, request)
        cfg = load_guild_config(guild_id)
        return {"enabled": cfg.get("voice_channel_user_creation_enabled", False)}

    @app.post("/guilds/{guild_id}/voice-channel-user-creation-enabled", tags=["config"])
    async def set_voice_user_creation_enabled(guild_id: int, payload: TogglePayload, request: Request):
        _require_admin(guild_id, request)
        cfg = load_guild_config(guild_id)
        cfg["voice_channel_user_creation_enabled"] = payload.enabled
        save_guild_config(guild_id, cfg)
        return {"status": "ok"}

    return app 