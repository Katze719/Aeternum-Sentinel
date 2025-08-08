from __future__ import annotations

from typing import Any

import discord
from fastapi import APIRouter, Body, HTTPException, Request

from .auth_utils import require_admin
from sentinel.utils.storage import load_guild_config, save_guild_config

router = APIRouter(tags=["reaction-roles"]) 


@router.get("/guilds/{guild_id}/reaction-roles")
async def get_reaction_roles(guild_id: int, request: Request) -> dict[str, Any]:
    require_admin(guild_id, request)
    cfg = load_guild_config(guild_id)
    return cfg.get("reaction_roles", {})


@router.post("/guilds/{guild_id}/reaction-roles")
async def set_reaction_roles(guild_id: int, request: Request, payload: dict = Body(...)) -> dict[str, str]:
    require_admin(guild_id, request)

    # Minimal validation
    channel_id = payload.get("channel_id")
    items = payload.get("items")
    if not channel_id or not isinstance(items, list):
        raise HTTPException(status_code=400, detail="channel_id and items[] required")

    # Persist configuration and preserve existing message_id so we can edit instead of reposting
    cfg = load_guild_config(guild_id)
    existing = cfg.get("reaction_roles") or {}
    if existing.get("message_id"):
        payload["message_id"] = existing["message_id"]
    cfg["reaction_roles"] = payload
    save_guild_config(guild_id, cfg)
    return {"status": "ok"}


@router.get("/guilds/{guild_id}/emojis")
async def list_guild_emojis(guild_id: int, request: Request):
    """Return custom emojis for UI selection."""
    require_admin(guild_id, request)

    bot = request.app.state.bot
    guild: discord.Guild | None = bot.get_guild(guild_id)
    if guild is None:
        raise HTTPException(status_code=404, detail="Guild not found")

    emojis = []
    for e in guild.emojis:
        emojis.append({
            "id": str(e.id),
            "name": e.name,
            "animated": e.animated,
            "url": str(e.url),
        })
    return emojis


@router.post("/guilds/{guild_id}/reaction-roles/publish")
async def publish_reaction_roles(guild_id: int, request: Request) -> dict[str, Any]:
    """Create or update the reaction role message and add the configured reactions.

    Returns message_id and a simple status.
    """
    require_admin(guild_id, request)

    bot = request.app.state.bot
    guild: discord.Guild | None = bot.get_guild(guild_id)
    if guild is None:
        raise HTTPException(status_code=404, detail="Guild not found")

    cfg = load_guild_config(guild_id)
    rr = cfg.get("reaction_roles")
    if not rr:
        raise HTTPException(status_code=400, detail="No reaction roles configured")

    channel_id = int(rr.get("channel_id"))
    channel = guild.get_channel(channel_id)
    if channel is None or not isinstance(channel, discord.TextChannel):
        raise HTTPException(status_code=400, detail="Configured channel not found or not a text channel")

    title = rr.get("title") or "Reaction Roles"
    description = rr.get("description") or "React to get roles."
    items: list[dict[str, Any]] = rr.get("items", [])

    # Build embed
    embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
    for it in items:
        role_id = it.get("role_id")
        role = guild.get_role(int(role_id)) if role_id else None
        # Render role name without raw mention markup to avoid <@&id> text
        label = f"@{role.name}" if role else f"Role {role_id}"
        per_item_desc = it.get("description") or ""
        # Show emoji preview text
        if it.get("emoji_unicode"):
            emoji_preview = it["emoji_unicode"]
        elif it.get("emoji_id"):
            emoji_preview = f"<:{it.get('emoji_name') or 'emoji'}:{it['emoji_id']}>"
        else:
            emoji_preview = ""
        embed.add_field(name=f"{emoji_preview} {label}", value=per_item_desc or "\u200b", inline=False)

    # Send or edit message
    message_id = rr.get("message_id")
    message: discord.Message | None = None
    if message_id:
        try:
            message = await channel.fetch_message(int(message_id))
        except Exception:
            message = None

    # If an old message exists but is in a different channel or can't be fetched, delete it and post new
    if message is None:
        # Try to remove old message if stored but not found in channel
        old_id = rr.get("message_id")
        if old_id:
            for ch in guild.text_channels:
                try:
                    old_msg = await ch.fetch_message(int(old_id))
                    await old_msg.delete()
                    break
                except Exception:
                    continue
        message = await channel.send(embed=embed)
        rr["message_id"] = message.id
    else:
        await message.edit(embed=embed)

    # Clear existing reactions and add configured ones
    try:
        await message.clear_reactions()
    except Exception:
        # Fallback: remove only our own
        try:
            for reaction in message.reactions:
                async for user in reaction.users():
                    if user == bot.user:
                        try:
                            await reaction.remove(user)
                        except Exception:
                            pass
        except Exception:
            pass

    # Add all reactions
    for it in items:
        try:
            if it.get("emoji_unicode"):
                await message.add_reaction(it["emoji_unicode"])
            elif it.get("emoji_id"):
                e = guild.get_emoji(int(it["emoji_id"]))
                if e is not None:
                    await message.add_reaction(e)
        except discord.HTTPException:
            # Skip invalid/unusable emojis
            continue

    # Persist possibly updated config
    cfg["reaction_roles"] = rr
    save_guild_config(guild_id, cfg)

    return {"status": "ok", "message_id": rr["message_id"]} 
