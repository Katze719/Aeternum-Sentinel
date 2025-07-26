from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

import sentinel.utils.storage as storage
from .auth_utils import require_admin

router = APIRouter(tags=["config"])

# ---------------------------------------------------------------------------
# Configuration endpoints
# ---------------------------------------------------------------------------

@router.get("/guilds/{guild_id}/image-analysis")
async def get_image_analysis_config(guild_id: int, request: Request):
    """Get image analysis configuration for the guild."""
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    
    return {
        "enabled": cfg.get("image_analysis_enabled", False),
        "channel_id": cfg.get("image_analysis_channel_id"),
        "gemini_api_key": cfg.get("gemini_api_key", ""),
        "payout_sheet_id": cfg.get("payout_sheet_id", ""),
        "payout_worksheet_name": cfg.get("payout_worksheet_name", ""),
        "payout_user_column": cfg.get("payout_user_column", ""),
        "payout_event_row": cfg.get("payout_event_row", ""),
        "payout_event_start_column": cfg.get("payout_event_start_column", ""),
        "payout_language": cfg.get("payout_language", "de"),
        "confirmation_roles": cfg.get("confirmation_roles", []),
    }

@router.post("/guilds/{guild_id}/image-analysis")
async def set_image_analysis_config(guild_id: int, request: Request, payload: dict):
    """Update image analysis configuration for the guild."""
    require_admin(guild_id, request)
    
    cfg = storage.load_guild_config(guild_id)
    
    # Update configuration
    if "enabled" in payload:
        cfg["image_analysis_enabled"] = bool(payload["enabled"])
    
    if "channel_id" in payload:
        cfg["image_analysis_channel_id"] = payload["channel_id"]
    
    if "gemini_api_key" in payload:
        cfg["gemini_api_key"] = payload["gemini_api_key"]
    
    # Payout tracking configuration
    if "payout_sheet_id" in payload:
        cfg["payout_sheet_id"] = payload["payout_sheet_id"]
    
    if "payout_worksheet_name" in payload:
        cfg["payout_worksheet_name"] = payload["payout_worksheet_name"]
    
    if "payout_user_column" in payload:
        cfg["payout_user_column"] = payload["payout_user_column"]
    
    if "payout_event_row" in payload:
        cfg["payout_event_row"] = payload["payout_event_row"]
    
    if "payout_event_start_column" in payload:
        cfg["payout_event_start_column"] = payload["payout_event_start_column"]
    
    if "payout_language" in payload:
        cfg["payout_language"] = payload["payout_language"]
    
    if "confirmation_roles" in payload:
        cfg["confirmation_roles"] = payload["confirmation_roles"]
    
    storage.save_guild_config(guild_id, cfg)
    return {"status": "ok"}

# ---------------------------------------------------------------------------
# Channel list for UI
# ---------------------------------------------------------------------------

@router.get("/guilds/{guild_id}/channels")
async def get_guild_channels(guild_id: int, request: Request):
    """Get list of text channels in the guild for UI selection."""
    require_admin(guild_id, request)
    
    bot = request.app.state.bot
    guild = bot.get_guild(guild_id)
    
    if guild is None:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    channels = []
    for channel in guild.text_channels:
        channels.append({
            "id": str(channel.id),
            "name": channel.name,
            "category": channel.category.name if channel.category else None,
        })
    
    # Sort by category name, then channel name
    channels.sort(key=lambda x: (x["category"] or "", x["name"]))
    
    return channels

@router.get("/guilds/{guild_id}/roles")
async def get_guild_roles(guild_id: int, request: Request):
    """Get list of roles in the guild for UI selection."""
    require_admin(guild_id, request)
    
    bot = request.app.state.bot
    guild = bot.get_guild(guild_id)
    
    if guild is None:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    roles = []
    for role in guild.roles:
        # Skip @everyone role and bot roles
        if role.name != "@everyone" and not role.managed:
            roles.append({
                "id": str(role.id),
                "name": role.name,
                "color": str(role.color),
            })
    
    # Sort by position (highest first)
    roles.sort(key=lambda x: guild.get_role(int(x["id"])).position, reverse=True)
    
    return roles

# ---------------------------------------------------------------------------
# Test endpoint
# ---------------------------------------------------------------------------

@router.post("/guilds/{guild_id}/image-analysis/test")
async def test_image_analysis(guild_id: int, request: Request, payload: dict):
    """Test image analysis with a URL."""
    require_admin(guild_id, request)
    
    image_url = payload.get("image_url")
    if not image_url:
        raise HTTPException(status_code=400, detail="image_url is required")
    
    # Get configuration
    cfg = storage.load_guild_config(guild_id)
    api_key = cfg.get("gemini_api_key")
    
    if not api_key:
        raise HTTPException(status_code=400, detail="No Gemini API key configured")
    
    try:
        # Get bot instance to access the image analysis cog
        bot = request.app.state.bot
        image_cog = bot.get_cog("ImageAnalysis")
        
        if not image_cog:
            raise HTTPException(status_code=500, detail="ImageAnalysis cog not loaded")
        
        # Download image from URL
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    raise HTTPException(status_code=400, detail=f"Failed to download image: {resp.status}")
                
                image_data = await resp.read()
        
        # Call Gemini API
        response_text = await image_cog._call_gemini_api(image_data, api_key)
        if not response_text:
            return {"extracted_text": "", "usernames": []}
        
        # Parse usernames
        usernames = image_cog._parse_usernames(response_text)
        
        return {
            "extracted_text": response_text,
            "usernames": usernames
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

# ---------------------------------------------------------------------------
# Payout sheet test endpoint
# ---------------------------------------------------------------------------

@router.post("/guilds/{guild_id}/image-analysis/test-payout")
async def test_payout_tracking(guild_id: int, request: Request, payload: dict):
    """Test payout tracking with sample usernames."""
    require_admin(guild_id, request)
    
    test_usernames = payload.get("usernames", [])
    thread_name = payload.get("thread_name", "Test Event")
    
    if not test_usernames:
        raise HTTPException(status_code=400, detail="usernames array is required")
    
    # Get configuration
    cfg = storage.load_guild_config(guild_id)
    
    # Check if payout configuration is complete
    required_fields = ["payout_sheet_id", "payout_worksheet_name", "payout_user_column", "payout_event_row"]
    missing_fields = [field for field in required_fields if not cfg.get(field)]
    
    if missing_fields:
        raise HTTPException(status_code=400, detail=f"Missing payout configuration: {', '.join(missing_fields)}")
    
    try:
        # Get bot instance to access the image analysis cog
        bot = request.app.state.bot
        image_cog = bot.get_cog("ImageAnalysis")
        
        if not image_cog:
            raise HTTPException(status_code=500, detail="ImageAnalysis cog not loaded")
        
        # Resolve dynamic worksheet name for testing
        worksheet_template = cfg.get("payout_worksheet_name")
        payout_language = cfg.get("payout_language", "de")
        resolved_worksheet = image_cog._resolve_worksheet_name(worksheet_template, payout_language)
        
        # Test payout tracking
        result = await image_cog._process_payout_tracking(test_usernames, thread_name, guild_id)
        
        # Add resolved worksheet name to result for display
        if result.get("success"):
            result["resolved_worksheet"] = resolved_worksheet
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payout test failed: {str(e)}")

# ---------------------------------------------------------------------------
# UI page
# ---------------------------------------------------------------------------

@router.get("/guilds/{guild_id}/image-analysis-ui", response_class=HTMLResponse)
async def image_analysis_ui(guild_id: int, request: Request):
    """Show image analysis configuration page."""
    require_admin(guild_id, request)
    
    bot = request.app.state.bot
    guild = bot.get_guild(guild_id)
    
    if guild is None:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "guild_image_analysis.html",
        {
            "request": request,
            "guild": guild,
        },
    ) 
