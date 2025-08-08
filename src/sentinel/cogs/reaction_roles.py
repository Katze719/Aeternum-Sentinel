from __future__ import annotations

import logging
from typing import Optional, Dict, Any

import discord
from discord.ext import commands

import sentinel.utils.storage as storage

_log = logging.getLogger(__name__)


CONFIG_KEY = "reaction_roles"


class ReactionRoles(commands.Cog):
    """Assign/remove roles when users react/unreact on a configured message.

    Configuration is stored per guild under the key ``reaction_roles`` and
    expected to look like this (persisted by the web UI):

    {
        "channel_id": "123456789012345678",
        "message_id": 987654321098765432,  # optional until published
        "title": "Choose your roles",
        "description": "Pick the roles that match you.",
        "items": [
            {"emoji_id": "111111111111111111", "emoji_name": "myemoji", "emoji_unicode": null, "role_id": "2222", "description": "Some desc"},
            {"emoji_id": null, "emoji_name": null, "emoji_unicode": "😀", "role_id": "3333", "description": "Other desc"}
        ]
    }
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_cfg(guild_id: int) -> Optional[Dict[str, Any]]:
        cfg = storage.load_guild_config(guild_id)
        rr = cfg.get(CONFIG_KEY)
        if not isinstance(rr, dict):
            return None
        # Basic shape validation
        if "channel_id" not in rr or "items" not in rr:
            return None
        return rr

    @staticmethod
    def _match_item(payload_emoji: discord.PartialEmoji, items: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
        # For custom emoji we prefer matching by ID; for unicode by name field (which is the unicode char)
        if payload_emoji.id:
            pid = str(payload_emoji.id)
            for item in items:
                if item.get("emoji_id") and str(item.get("emoji_id")) == pid:
                    return item
        else:
            name = payload_emoji.name
            for item in items:
                if item.get("emoji_unicode") == name:
                    return item
        return None

    async def _ensure_guild_role(self, guild: discord.Guild, role_id: str | int) -> Optional[discord.Role]:
        try:
            rid = int(role_id)
        except (TypeError, ValueError):
            return None
        role = guild.get_role(rid)
        return role

    # ------------------------------------------------------------------
    # Raw reaction events
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Ignore own reactions and DMs
        if payload.user_id == (self.bot.user.id if self.bot.user else 0):
            return
        if payload.guild_id is None:
            return

        rr_cfg = self._load_cfg(payload.guild_id)
        if not rr_cfg:
            return

        # Only handle reactions on the configured message
        if int(rr_cfg.get("message_id") or 0) != payload.message_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        item = self._match_item(payload.emoji, rr_cfg.get("items", []))
        if not item:
            return

        role = await self._ensure_guild_role(guild, item.get("role_id"))
        if not role:
            return

        # Get member from payload if present, else fetch
        member: Optional[discord.Member]
        if payload.member is not None:
            member = payload.member
        else:
            member = guild.get_member(payload.user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(payload.user_id)
                except discord.HTTPException:
                    member = None
        if member is None or member.bot:
            return

        try:
            if role not in member.roles:
                await member.add_roles(role, reason="Reaction role opt-in")
        except discord.Forbidden:
            _log.warning("Missing permissions to add role %s in guild %s", role.id, guild.id)
        except discord.HTTPException as exc:
            _log.error("Failed to add role via reaction: %s", exc)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        # Ignore DMs
        if payload.guild_id is None:
            return

        rr_cfg = self._load_cfg(payload.guild_id)
        if not rr_cfg:
            return

        if int(rr_cfg.get("message_id") or 0) != payload.message_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        item = self._match_item(payload.emoji, rr_cfg.get("items", []))
        if not item:
            return

        role = await self._ensure_guild_role(guild, item.get("role_id"))
        if not role:
            return

        member = guild.get_member(payload.user_id)
        if member is None or member.bot:
            return

        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Reaction role opt-out")
        except discord.Forbidden:
            _log.warning("Missing permissions to remove role %s in guild %s", role.id, guild.id)
        except discord.HTTPException as exc:
            _log.error("Failed to remove role via reaction: %s", exc)


async def setup(bot: commands.Bot):  # noqa: D401
    await bot.add_cog(ReactionRoles(bot)) 
