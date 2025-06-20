import secrets

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from .auth_utils import _state_store, _build_authorize_url
from sentinel.config import get_settings

router = APIRouter(tags=["auth"])


@router.get("/login")
async def login(request: Request, next: str | None = "/dashboard"):
    """Kick-off Discord OAuth2 flow and redirect the user."""

    settings = get_settings()

    state = secrets.token_urlsafe(16)
    _state_store[state] = next or "/dashboard"

    url = _build_authorize_url(state, settings)
    return RedirectResponse(url) 
