from fastapi import APIRouter, HTTPException, Request

from .auth_utils import require_admin

router = APIRouter(tags=["actions"])


@router.post("/guilds/{guild_id}/apply-role-icons")
async def apply_role_icons(guild_id: int, request: Request):
    """Iterate over all guild members and re-apply the Role-Icon nickname format."""

    require_admin(guild_id, request)

    bot = request.app.state.bot
    guild = bot.get_guild(guild_id)
    if guild is None:
        raise HTTPException(status_code=404, detail="Guild not found or bot not in guild.")

    role_cog = bot.get_cog("RoleIcons")
    if role_cog is None:  # pragma: no cover
        raise HTTPException(status_code=500, detail="RoleIcons cog not loaded.")

    updated = 0
    for member in guild.members:
        await role_cog._apply_nickname(member)  # type: ignore[attr-defined]
        updated += 1

    return {"updated": updated} 
