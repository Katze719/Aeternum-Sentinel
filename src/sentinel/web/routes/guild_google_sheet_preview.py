from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException

import sentinel.utils.storage as storage
from sentinel.integrations.google_sheets import get_async_gspread_client_manager

router = APIRouter(tags=["google-sheet"])


@router.get("/guilds/{guild_id}/google-sheet/preview")
async def preview_google_sheet(guild_id: int, request: Request):
    """Return all rows of the configured Google Sheet."""

    # Reuse existing admin check
    from .auth_utils import require_admin  # local import to avoid cycle

    require_admin(guild_id, request)

    cfg = storage.load_guild_config(guild_id).get("google_sheet")
    if not cfg:
        raise HTTPException(status_code=404, detail="Google Sheet not configured for guild")

    sheet_id: str = cfg.get("sheet_id")  # type: ignore
    # Allow overriding via query param ?worksheet=..
    worksheet_name = request.query_params.get("worksheet") or cfg.get("worksheet_name")  # type: ignore

    if not sheet_id or not worksheet_name:
        raise HTTPException(status_code=400, detail="sheet_id and worksheet_name required")

    try:
        mgr = get_async_gspread_client_manager()
        agc = await mgr.authorize()
        ss = await agc.open_by_key(sheet_id)
        ws = await ss.worksheet(worksheet_name)

        values = await ws.get_all_values()
    except Exception as exc:
        # Return clear error for UI
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"values": values}
