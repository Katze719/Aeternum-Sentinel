from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from sentinel.utils.storage import load_guild_config

from .auth_utils import require_admin

router = APIRouter(tags=["ui"])


@router.get("/guilds/{guild_id}/sheet", response_class=HTMLResponse)
async def guild_sheet_page(guild_id: int, request: Request):
    """Render an extra page dedicated to Google-Sheet preview & settings."""

    require_admin(guild_id, request)

    cfg = load_guild_config(guild_id).get("google_sheet", {})

    bot = request.app.state.bot
    guild = bot.get_guild(guild_id)
    if guild is None:
        roles = []
    else:
        roles = [
            {"id": r.id, "name": r.name}
            for r in guild.roles
            if not r.is_default()
        ]

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "guild_sheet.html",
        {
            "request": request,
            "guild_id": guild_id,
            "sheet_cfg": cfg,
            "roles": roles,
        },
    ) 
