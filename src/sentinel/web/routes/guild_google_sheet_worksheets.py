from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException

import sentinel.utils.storage as storage
from sentinel.integrations.google_sheets import get_async_gspread_client_manager
from .auth_utils import require_admin

router = APIRouter(tags=["google-sheet"])


@router.get("/guilds/{guild_id}/google-sheet/worksheets")
async def list_worksheets(guild_id: int, request: Request, sheet_id: str | None = None):
    """Return the list of worksheet names for the given *sheet_id*.

    The *sheet_id* can be supplied explicitly as query parameter or – if
    omitted – will be taken from the stored guild configuration.
    """

    require_admin(guild_id, request)

    cfg = storage.load_guild_config(guild_id).get("google_sheet", {})
    if sheet_id is None:
        sheet_id = cfg.get("sheet_id")  # type: ignore[assignment]

    if not sheet_id:
        raise HTTPException(status_code=400, detail="sheet_id is required")

    try:
        mgr = get_async_gspread_client_manager()
        agc = await mgr.authorize()
        ss = await agc.open_by_key(sheet_id)
        worksheets = await ss.worksheets()
        names = [ws.title for ws in worksheets]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"worksheets": names} 
