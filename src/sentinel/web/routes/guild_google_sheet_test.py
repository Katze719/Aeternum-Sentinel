from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException

import sentinel.utils.storage as storage
from sentinel.integrations.google_sheets import get_async_gspread_client_manager
from .auth_utils import require_admin

router = APIRouter(tags=["config"])


@router.post("/guilds/{guild_id}/google-sheet/test")
async def google_sheet_test(guild_id: int, request: Request):
    """Simple connectivity test – checks if the configured sheet is reachable."""

    require_admin(guild_id, request)

    cfg = storage.load_guild_config(guild_id).get("google_sheet", {})
    sheet_id: str | None = cfg.get("sheet_id")  # type: ignore
    worksheet_name: str | None = cfg.get("worksheet_name")  # type: ignore

    if not sheet_id:
        raise HTTPException(status_code=400, detail="Sheet-ID nicht gesetzt.")

    try:
        mgr = get_async_gspread_client_manager()
        agc = await mgr.authorize()
        ss = await agc.open_by_key(sheet_id)
        if worksheet_name:
            await ss.worksheet(worksheet_name)
        # otherwise first worksheet exists by default
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Verbindung fehlgeschlagen: {exc}")

    return {"status": "ok"} 
