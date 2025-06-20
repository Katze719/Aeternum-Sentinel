from fastapi import APIRouter, Request

import sentinel.utils.storage as storage

from .auth_utils import require_admin
from .schemas import NameFormatPayload

router = APIRouter(tags=["config"])


@router.get("/guilds/{guild_id}/name-format")
async def get_name_format(guild_id: int, request: Request):
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    return {"name_format": cfg.get("name_format", "{username} [{icons}]")}


@router.post("/guilds/{guild_id}/name-format")
async def set_name_format(guild_id: int, payload: NameFormatPayload, request: Request):
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    cfg["name_format"] = payload.name_format
    storage.save_guild_config(guild_id, cfg)
    return {"status": "ok"} 
