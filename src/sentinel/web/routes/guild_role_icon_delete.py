from fastapi import APIRouter, Request

import sentinel.utils.storage as storage

from .auth_utils import require_admin

router = APIRouter(tags=["config"])


@router.delete("/guilds/{guild_id}/role-icons/{role_id}")
async def delete_role_icon(guild_id: int, role_id: int, request: Request):
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    role_icons = cfg.get("role_icons", {})
    role_icons.pop(str(role_id), None)
    storage.save_guild_config(guild_id, cfg)
    return {"status": "deleted"} 
