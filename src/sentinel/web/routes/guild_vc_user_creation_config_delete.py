from fastapi import APIRouter, Request

import sentinel.utils.storage as storage

from .auth_utils import require_admin

router = APIRouter(tags=["config"])


@router.delete("/guilds/{guild_id}/voice-channel-user-creation-config/{generator_id}")
async def delete_voice_channel_user_creation_config(guild_id: int, generator_id: int, request: Request):
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    vacfg = cfg.get("voice_channel_user_creation_config", {})
    vacfg.pop(str(generator_id), None)
    storage.save_guild_config(guild_id, cfg)
    return {"status": "deleted"} 
