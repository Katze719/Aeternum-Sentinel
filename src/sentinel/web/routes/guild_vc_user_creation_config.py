from fastapi import APIRouter, Request

import sentinel.utils.storage as storage

from .auth_utils import require_admin
from .schemas import VoiceAutoConfigPayload

router = APIRouter(tags=["config"])


@router.get("/guilds/{guild_id}/voice-channel-user-creation-config")
async def get_voice_channel_user_creation_config(guild_id: int, request: Request):
    """Return mapping of generator_channel_id -> config dict."""
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    return cfg.get("voice_channel_user_creation_config", {})


@router.post("/guilds/{guild_id}/voice-channel-user-creation-config")
async def upsert_voice_channel_user_creation_config(
    guild_id: int,
    payload: VoiceAutoConfigPayload,
    request: Request,
):
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    vacfg = cfg.setdefault("voice_channel_user_creation_config", {})
    vacfg[payload.generator_channel_id] = {
        "target_category_id": payload.target_category_id,
        "name_pattern": payload.name_pattern or "{username}",
    }
    storage.save_guild_config(guild_id, cfg)
    return {"status": "ok"} 
