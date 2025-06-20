from fastapi import APIRouter, Body, Request

import sentinel.utils.storage as storage

from .auth_utils import require_admin
from .schemas import RoleIconEntry

router = APIRouter(tags=["config"])


@router.get("/guilds/{guild_id}/role-icons")
async def get_role_icons(guild_id: int, request: Request):
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    return cfg.get("role_icons", {})


@router.post("/guilds/{guild_id}/role-icons")
async def add_or_update_role_icon(
    guild_id: int,
    request: Request,
    entry: RoleIconEntry = Body(...),
):
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    role_icons = cfg.setdefault("role_icons", {})
    role_icons[str(entry.role_id)] = {"emoji": entry.emoji, "priority": entry.priority}
    storage.save_guild_config(guild_id, cfg)
    return {"status": "ok"} 
