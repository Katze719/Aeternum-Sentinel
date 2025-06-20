from __future__ import annotations

from fastapi import APIRouter, Request, Body

from sentinel.utils import storage
from .auth_utils import require_admin

router = APIRouter(tags=["config"])


class MappingPayload(storage.Any):
    pass


@router.post("/guilds/{guild_id}/google-sheet/username-mapping")
async def set_username_mapping(
    guild_id: int,
    request: Request,
    row: int = Body(...),
    col: int = Body(...),
    direction: str = Body(...),
    worksheet: str = Body(...),
):
    require_admin(guild_id, request)

    cfg = storage.load_guild_config(guild_id)
    sheet_cfg = cfg.setdefault("google_sheet", {})
    mappings = sheet_cfg.setdefault("username_mappings", {})
    key = worksheet
    mappings[key] = {"row": row, "col": col, "direction": direction}
    storage.save_guild_config(guild_id, cfg)
    return {"status": "ok"} 
