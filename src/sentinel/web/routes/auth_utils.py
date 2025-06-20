from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sentinel.config import get_settings

__all__ = [
    "router",
    "get_session",
    "save_session",
    "require_admin",
]

# ---------------------------------------------------------------------------
# Discord OAuth constants & in-memory session management
# ---------------------------------------------------------------------------

OAUTH_SCOPE = "identify guilds"
DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_ENDPOINT = "https://discord.com/api/users/@me"

_state_store: dict[str, str] = {}
_session_store: dict[str, dict[str, Any]] = {}

SESSION_COOKIE = "sentinel_session"


# A minimal router for auth endpoints that need to share the same helpers -------
router = APIRouter(tags=["auth"])  # Will be extended by login/callback modules


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _build_authorize_url(state: str, settings) -> str:
    params = {
        "client_id": settings.discord_client_id,
        "redirect_uri": settings.oauth_redirect_uri,
        "response_type": "code",
        "scope": OAUTH_SCOPE,
        "state": state,
        "prompt": "consent",
    }
    return f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}"


def get_session(request: Request) -> dict | None:  # pragma: no cover
    """Retrieve the persisted session dict from the request cookies (if any)."""
    sid = request.cookies.get(SESSION_COOKIE)
    if sid and sid in _session_store:
        return _session_store[sid]
    return None


def save_session(access_token: str, user: dict[str, Any]) -> str:
    """Create a new session entry and return the generated *session_id*."""
    session_id = secrets.token_urlsafe(24)
    _session_store[session_id] = {
        "access_token": access_token,
        "user": user,
    }
    return session_id


# ---------------------------------------------------------------------------
# Permission helpers (exported for other route modules)
# ---------------------------------------------------------------------------

def require_admin(guild_id: int, request: Request):  # pragma: no cover
    """Validate that the current session user has administrator permissions.

    If validation passes, the current session dict is returned. Otherwise a
    matching ``HTTPException`` is raised.
    """

    session = get_session(request)
    accepts_html = "text/html" in (request.headers.get("accept", ""))

    if not session:
        if accepts_html:
            raise HTTPException(
                status_code=status.HTTP_302_FOUND,
                headers={"Location": f"/login?next=/guilds/{guild_id}"},
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    bot = request.app.state.bot
    guild = bot.get_guild(guild_id)
    if guild is None:
        if accepts_html:
            raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/?msg=guild_not_found"})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guild not found or bot not in guild.")

    member = guild.get_member(int(session["user"]["id"]))
    if member is None:
        if accepts_html:
            raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/?msg=user_not_in_guild"})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not in guild.")

    perms = member.guild_permissions
    if not (perms.administrator or perms.manage_guild):
        if accepts_html:
            raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/?msg=insufficient_perms"})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator permissions required.")

    return session


# ---------------------------------------------------------------------------
# Core auth routes (login & callback)
# ---------------------------------------------------------------------------

# @router.get("/login")
# async def login(request: Request, next: str | None = "/dashboard"):
#     """Kick-off Discord OAuth2 flow and redirect the user."""
#
#     settings = get_settings()
#
#     state = secrets.token_urlsafe(16)
#     _state_store[state] = next or "/dashboard"
#
#     url = _build_authorize_url(state, settings)
#     return RedirectResponse(url)
#
#
# @router.get("/callback")
# async def oauth_callback(code: str, state: str):
#     """Handle redirect from Discord OAuth2 flow, exchange code for token and fetch user info."""
#
#     if state not in _state_store:
#         raise HTTPException(status_code=400, detail="Invalid state parameter.")
#
#     # Retrieve and remove target path from state store.
#     redirect_target = _state_store.pop(state, "/dashboard")
#
#     settings = get_settings()
#     data = {
#         "client_id": settings.discord_client_id,
#         "client_secret": settings.discord_client_secret,
#         "grant_type": "authorization_code",
#         "code": code,
#         "redirect_uri": settings.oauth_redirect_uri,
#     }
#     headers = {"Content-Type": "application/x-www-form-urlencoded"}
#
#     async with httpx.AsyncClient() as client:
#         token_resp = await client.post(DISCORD_TOKEN_URL, data=data, headers=headers)
#         if token_resp.status_code != 200:
#             raise HTTPException(status_code=token_resp.status_code, detail="Failed to obtain access token")
#
#         token_json = token_resp.json()
#         access_token = token_json["access_token"]
#
#         user_resp = await client.get(
#             DISCORD_USER_ENDPOINT,
#             headers={"Authorization": f"Bearer {access_token}"},
#         )
#         if user_resp.status_code != 200:
#             raise HTTPException(status_code=user_resp.status_code, detail="Failed to fetch user info")
#
#         user = user_resp.json()
#
#     # Persist simple session (in-memory)
#     session_id = save_session(access_token, user)
#
#     response = RedirectResponse(url=redirect_target)
#     response.set_cookie(SESSION_COOKIE, session_id, max_age=60 * 60 * 24, httponly=True)
#     return response 
