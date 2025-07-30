from fastapi import APIRouter, Request

import sentinel.utils.storage as storage

from .auth_utils import require_admin
from .schemas import NameFormatPayload

router = APIRouter(tags=["config"])


@router.get("/guilds/{guild_id}/name-format")
async def get_name_format(guild_id: int, request: Request):
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    return {"name_format": cfg.get("name_format", "{username} [{icons}]")}


@router.post("/guilds/{guild_id}/name-format")
async def set_name_format(guild_id: int, payload: NameFormatPayload, request: Request):
    require_admin(guild_id, request)
    cfg = storage.load_guild_config(guild_id)
    old_fmt: str = cfg.get("name_format", "{username} [{icons}]")
    new_fmt: str = payload.name_format

    # Persist the new format first so that subsequent nickname updates use it.
    cfg["name_format"] = new_fmt
    storage.save_guild_config(guild_id, cfg)

    # ------------------------------------------------------------------
    # Re-apply nicknames in background (non-blocking for the HTTP request)
    # ------------------------------------------------------------------
    bot = request.app.state.bot
    role_cog = bot.get_cog("RoleIcons")  # type: ignore[attr-defined]

    async def _update_members():
        guild = bot.get_guild(guild_id)
        if guild is None or role_cog is None:
            return

        # Pre-compute helpers outside the member loop for efficiency
        regex = role_cog._build_regex(old_fmt)  # type: ignore[attr-defined]
        icons_cfg = cfg.get("role_icons", {})
        icons_sorted = role_cog._sorted_emojis(list(icons_cfg.values())) if icons_cfg else []  # type: ignore[attr-defined]

        for member in guild.members:
            # Extract base username using *old* format
            match = regex.match(member.display_name)
            base_username = match.group("name").strip() if match else member.display_name.strip()

            # Determine emojis for this member with current role config
            emojis = [icons_cfg[str(r.id)]["emoji"] for r in member.roles if str(r.id) in icons_cfg]
            if emojis and icons_sorted:
                emojis = [e for e in icons_sorted if e in emojis]

            new_nick = role_cog._format_name(base_username, emojis, new_fmt)  # type: ignore[attr-defined]

            if member.display_name != new_nick:
                try:
                    await member.edit(nick=new_nick, reason="Updating nickname pattern")
                except Exception:
                    # Swallow any per-member error to continue processing others
                    pass

    # Run without blocking the HTTP response
    bot.loop.create_task(_update_members())

    return {"status": "ok"} 
