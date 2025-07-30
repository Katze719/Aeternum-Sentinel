from fastapi import APIRouter, Request

import sentinel.utils.storage as storage

from .auth_utils import require_admin
from .schemas import VodLinkPayload

router = APIRouter(tags=["config"])


@router.get("/guilds/{guild_id}/vod-link")
async def get_vod_link(guild_id: int, request: Request):
    """Return the VOD form link for the guild."""
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    return {"link": cfg.get("vod_link", "")}


@router.post("/guilds/{guild_id}/vod-link")
async def update_vod_link(guild_id: int, payload: VodLinkPayload, request: Request):
    """Create or update the VOD form link for a guild."""
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    cfg["vod_link"] = payload.link
    storage.save_guild_config(guild_id, cfg)
    return {"status": "ok"} 
