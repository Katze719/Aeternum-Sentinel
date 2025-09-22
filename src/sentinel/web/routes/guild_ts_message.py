from fastapi import APIRouter, Request

import sentinel.utils.storage as storage

from .auth_utils import require_admin
from .schemas import TsMessagePayload

router = APIRouter(tags=["config"])


@router.get("/guilds/{guild_id}/ts-message")
async def get_ts_message(guild_id: int, request: Request):
    """Return the TeamSpeak message for the guild."""
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    return {"message": cfg.get("ts_message", "")}


@router.post("/guilds/{guild_id}/ts-message")
async def update_ts_message(guild_id: int, payload: TsMessagePayload, request: Request):
    """Create or update the TeamSpeak message for a guild."""
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    cfg["ts_message"] = payload.message
    storage.save_guild_config(guild_id, cfg)
    return {"status": "ok"} 
