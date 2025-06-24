from fastapi import APIRouter, Request

import sentinel.utils.storage as storage

from .auth_utils import require_admin
from .schemas import ReviewMessagePayload

router = APIRouter(tags=["config"])


@router.get("/guilds/{guild_id}/review-message")
async def get_review_message(guild_id: int, request: Request):
    """Return the stored review message for the guild."""
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    return {"message": cfg.get("review_message", "")}


@router.post("/guilds/{guild_id}/review-message")
async def update_review_message(guild_id: int, payload: ReviewMessagePayload, request: Request):
    """Create or update the review message for a guild."""
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    cfg["review_message"] = payload.message
    storage.save_guild_config(guild_id, cfg)
    return {"status": "ok"} 
