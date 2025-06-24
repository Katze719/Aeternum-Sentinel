from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from sentinel.utils.storage import load_guild_config

from .auth_utils import require_admin

router = APIRouter(tags=["ui"])


@router.get("/guilds/{guild_id}", response_class=HTMLResponse)
async def guild_settings(guild_id: int, request: Request):
    """Render the per-guild settings UI page."""

    require_admin(guild_id, request)

    bot = request.app.state.bot
    guild = bot.get_guild(guild_id)
    if guild is None:
        raise HTTPException(status_code=404, detail="Guild not found or bot not in guild.")

    cfg = load_guild_config(guild_id)
    role_icons = cfg.get("role_icons", {})

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

    sheet_cfg = cfg.get("google_sheet", {})

    review_message = cfg.get("review_message", "")

    vod_link = cfg.get("vod_link", "")

    voice_channel_names = {str(ch['id']): ch['name'] for ch in voice_channels}
    category_names = {str(cat['id']): cat['name'] for cat in categories}

    templates = request.app.state.templates
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
            "sheet_cfg": sheet_cfg,
            "review_message": review_message,
            "vod_link": vod_link,
        },
    ) 
