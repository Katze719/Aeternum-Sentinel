from __future__ import annotations

"""Google Sheet configuration endpoints for individual guilds."""

from fastapi import APIRouter, Body, Request

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
    payload: dict = Body(..., description="Google sheet configuration (sheet_id, worksheet_name)") ,
):
    """Replace the entire Google-Sheet config for *guild_id* with *payload*."""

    require_admin(guild_id, request)

    if not isinstance(payload, dict):
        # The FastAPI validator should already cover this, but let's be safe.
        return {"error": "Invalid payload"}

    cfg = storage.load_guild_config(guild_id)
    # Only allow certain keys
    allowed = {k: v for k, v in payload.items() if k in ("sheet_id", "worksheet_name")}
    cfg["google_sheet"] = allowed
    storage.save_guild_config(guild_id, cfg)
    return {"status": "ok"} 
