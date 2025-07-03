from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .auth_utils import get_session

router = APIRouter(tags=["ui"])


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Show all guilds the current user shares with the bot."""

    session = get_session(request)
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

    bot = request.app.state.bot
    bot_guild_ids = {g.id for g in bot.guilds}

    common_guilds: list[dict] = []
    for g in user_guilds:
        if int(g["id"]) not in bot_guild_ids:
            continue

        icon_hash = g.get("icon")
        if icon_hash:
            g["icon_url"] = f"https://cdn.discordapp.com/icons/{g['id']}/{icon_hash}.png?size=128"
        else:
            g["icon_url"] = "https://cdn.discordapp.com/embed/avatars/0.png"

        common_guilds.append(g)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "guilds": common_guilds,
        },
    ) 
