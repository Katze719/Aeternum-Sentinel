from __future__ import annotations

"""Google Sheet configuration endpoints for individual guilds."""

from fastapi import APIRouter, Body, Request, HTTPException

import sentinel.utils.storage as storage

from .auth_utils import require_admin

router = APIRouter(tags=["config"])


@router.get("/guilds/{guild_id}/google-sheet")
async def get_google_sheet_config(guild_id: int, request: Request):
    """Return the stored Google-Sheet configuration for *guild_id*."""

    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    return cfg.get("google_sheet", {})


@router.post("/guilds/{guild_id}/google-sheet")
async def set_google_sheet_config(
    guild_id: int,
    request: Request,
    payload: dict = Body(..., description="Google sheet configuration (sheet_id[, worksheet_name])") ,
):
    """Replace the entire Google-Sheet config for *guild_id* with *payload*."""

    require_admin(guild_id, request)

    if not isinstance(payload, dict):
        # The FastAPI validator should already cover this, but let's be safe.
        return {"error": "Invalid payload"}

    if not payload.get("sheet_id"):
        raise HTTPException(status_code=400, detail="sheet_id is required")

    cfg = storage.load_guild_config(guild_id)
    sheet_cfg = cfg.get("google_sheet", {})
    # Accept additional optional keys for member filtering
    allowed_keys = ("sheet_id", "worksheet_name", "member_scope", "role_ids")
    allowed = {k: v for k, v in payload.items() if k in allowed_keys}
    # Preserve other keys (e.g., username_mappings)
    sheet_cfg.update(allowed)
    cfg["google_sheet"] = sheet_cfg
    storage.save_guild_config(guild_id, cfg)
    return {"status": "ok"} 
