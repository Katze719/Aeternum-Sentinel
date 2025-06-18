from fastapi import APIRouter, Request

import sentinel.utils.storage as storage

from .auth_utils import require_admin
from .schemas import TogglePayload

router = APIRouter(tags=["config"])


@router.get("/guilds/{guild_id}/voice-channel-user-creation-enabled")
async def get_vc_user_creation_enabled(guild_id: int, request: Request):
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    return {"enabled": cfg.get("voice_channel_user_creation_enabled", False)}


@router.post("/guilds/{guild_id}/voice-channel-user-creation-enabled")
async def set_vc_user_creation_enabled(guild_id: int, payload: TogglePayload, request: Request):
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    cfg["voice_channel_user_creation_enabled"] = payload.enabled
    storage.save_guild_config(guild_id, cfg)
    return {"status": "ok"} 
