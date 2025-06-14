from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import secrets
from urllib.parse import urlencode

import httpx
from fastapi.responses import HTMLResponse, RedirectResponse
from sentinel.config import get_settings

if TYPE_CHECKING:  # pragma: no cover
    from sentinel.bot import SentinelBot


class ConfigResponse(BaseModel):
    prefix: str


def get_app(bot: SentinelBot) -> FastAPI:  # noqa: D401
    """Return a FastAPI app instance bound to the provided bot."""

    app = FastAPI(title="Sentinel Config API", version="0.1.0")

    @app.get("/", response_class=HTMLResponse, tags=["ui"])
    async def landing() -> str:
        """Simple landing page with login button."""

        settings = get_settings()
        login_url = "/login"
        return f"""
        <!DOCTYPE html>
        <html lang='en'>
        <head>
            <meta charset='utf-8'>
            <title>Sentinel Bot</title>
            <style>
              body {{ font-family: sans-serif; display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; }}
              a.button {{ padding:1rem 2rem; background:#5865F2; color:white; text-decoration:none; border-radius:8px; font-size:1.2rem; }}
            </style>
        </head>
        <body>
            <h1>Aeternum Sentinel - Discord Bot</h1>
            <p>Aeternum Sentinel is a Discord bot that helps you manage your Discord server.</p>
            <p><a class='button' href='{login_url}'>Login with Discord</a></p>
        </body>
        </html>
        """

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

    OAUTH_SCOPE = "identify"
    DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
    DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
    DISCORD_USER_ENDPOINT = "https://discord.com/api/users/@me"

    _state_store: set[str] = set()

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

        # For demonstration we just greet user.
        username = f"{user['username']}#{user['discriminator']}"
        return HTMLResponse(f"<h2>Welcome, {username}!</h2><p>You are now logged in.</p>")

    return app 