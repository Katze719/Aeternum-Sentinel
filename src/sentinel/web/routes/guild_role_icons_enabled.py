from fastapi import APIRouter, Request

import sentinel.utils.storage as storage

from .auth_utils import require_admin
from .schemas import TogglePayload

router = APIRouter(tags=["config"])


@router.get("/guilds/{guild_id}/role-icons-enabled")
async def get_role_icons_enabled(guild_id: int, request: Request):
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    return {"enabled": cfg.get("role_icon_enabled", False)}


@router.post("/guilds/{guild_id}/role-icons-enabled")
async def set_role_icons_enabled(guild_id: int, payload: TogglePayload, request: Request):
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    cfg["role_icon_enabled"] = payload.enabled
    storage.save_guild_config(guild_id, cfg)
    return {"status": "ok"} 
