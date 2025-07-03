from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
import httpx

from .auth_utils import (
    _state_store,
    DISCORD_TOKEN_URL,
    DISCORD_USER_ENDPOINT,
    save_session,
    SESSION_COOKIE,
)
from sentinel.config import get_settings

router = APIRouter(tags=["auth"])


@router.get("/callback")
async def oauth_callback(code: str, state: str):
    """Handle redirect from Discord OAuth2 flow, exchange code for token and fetch user info."""

    if state not in _state_store:
        raise HTTPException(status_code=400, detail="Invalid state parameter.")

    redirect_target = _state_store.pop(state, "/dashboard")
    settings = get_settings()

    data = {
        "client_id": settings.discord_client_id,
        "client_secret": settings.discord_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.oauth_redirect_uri,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(DISCORD_TOKEN_URL, data=data, headers=headers)
        if token_resp.status_code != 200:
            raise HTTPException(status_code=token_resp.status_code, detail="Failed to obtain access token")

        token_json = token_resp.json()
        access_token = token_json["access_token"]

        user_resp = await client.get(
            DISCORD_USER_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=user_resp.status_code, detail="Failed to fetch user info")

        user = user_resp.json()

    # Persist session
    session_id = save_session(access_token, user)

    response = RedirectResponse(url=redirect_target)
    response.set_cookie(SESSION_COOKIE, session_id, max_age=60 * 60 * 24, httponly=True)
    return response 
