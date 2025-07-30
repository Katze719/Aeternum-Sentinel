from __future__ import annotations

from fastapi import APIRouter, Request, Body, HTTPException

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


# ------------------------------------------------------------------
# Endpoint to update extra settings (member filter) for existing mapping
# ------------------------------------------------------------------


@router.post("/guilds/{guild_id}/google-sheet/username-mapping-settings")
async def set_username_mapping_settings(
    guild_id: int,
    request: Request,
    worksheet: str = Body(...),
    member_scope: str = Body(...),
    role_ids: list[str] | None = Body(None),
):
    """Attach *member_scope* / *role_ids* to an existing username mapping for *worksheet*."""

    require_admin(guild_id, request)

    cfg = storage.load_guild_config(guild_id)
    sheet_cfg = cfg.setdefault("google_sheet", {})
    mappings = sheet_cfg.setdefault("username_mappings", {})

    mapping = mappings.get(worksheet)
    if mapping is None:
        # Mapping must exist already – otherwise nothing to update
        raise HTTPException(status_code=404, detail="Username-Mapping für Worksheet nicht vorhanden")

    mapping["member_scope"] = member_scope

    if member_scope == "role":
        if not role_ids:
            raise HTTPException(status_code=400, detail="role_ids erforderlich für member_scope=role")
        mapping["role_ids"] = role_ids
    else:
        # clear any previous role filter
        mapping.pop("role_ids", None)

    storage.save_guild_config(guild_id, cfg)
    return {"status": "ok"}


# ------------------------------------------------------------------
# DELETE mapping
# ------------------------------------------------------------------


@router.delete("/guilds/{guild_id}/google-sheet/username-mapping/{worksheet}")
async def delete_username_mapping(
    guild_id: int,
    worksheet: str,
    request: Request,
):
    """Delete the username mapping for *worksheet* in *guild_id*."""

    require_admin(guild_id, request)

    cfg = storage.load_guild_config(guild_id)
    sheet_cfg = cfg.get("google_sheet", {})
    mappings = sheet_cfg.get("username_mappings", {})

    if worksheet in mappings:
        mappings.pop(worksheet)
        storage.save_guild_config(guild_id, cfg)
        return {"status": "deleted"}

    raise HTTPException(status_code=404, detail="Mapping nicht gefunden") 
