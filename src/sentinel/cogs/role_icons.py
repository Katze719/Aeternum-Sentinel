from __future__ import annotations

import logging
from typing import List
import re

import discord
from discord import app_commands
from discord.ext import commands

from sentinel.utils.storage import load_guild_config, save_guild_config

_log = logging.getLogger(__name__)


ROLE_ICONS_KEY = "role_icons"
FORMAT_KEY = "name_format"
DEFAULT_FORMAT = "{username} [{icons}]"


class RoleIcons(commands.Cog):
    """Manage role-based icons and update member nicknames accordingly."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Utility methods -----------------------------------------------------

    @staticmethod
    def _sorted_emojis(icons: List[dict]) -> List[str]:
        # Sort by priority ascending (lower value = leftmost)
        return [entry["emoji"] for entry in sorted(icons, key=lambda e: e.get("priority", 0))]

    def _format_name(self, username: str, emojis: List[str], fmt: str) -> str:
        return fmt.replace("{username}", username).replace("{icons}", "".join(emojis))

    @staticmethod
    def _build_regex(fmt: str) -> re.Pattern:
        pattern = (
            re.escape(fmt)
            .replace(r"\{username\}", r"(?P<name>.+?)")
            .replace(r"\{icons\}", r".*")
        )
        return re.compile(f"^{pattern}$")

    async def _apply_nickname(self, member: discord.Member):
        cfg = load_guild_config(member.guild.id)
        if not cfg.get("role_icon_enabled", False):
            return
        fmt = cfg.get(FORMAT_KEY, DEFAULT_FORMAT)
        icons_cfg = cfg.get(ROLE_ICONS_KEY, {})

        # Determine emojis for this member based on roles
        emojis: List[str] = []
        for role in member.roles:
            if str(role.id) in icons_cfg:
                emojis.append(icons_cfg[str(role.id)]["emoji"])
        # Order them by priority
        if emojis:
            icons_sorted = self._sorted_emojis(list(icons_cfg.values()))
            emojis = [e for e in icons_sorted if e in emojis]

        # Determine base username from current display_name to avoid double application
        regex = self._build_regex(fmt)
        match = regex.match(member.display_name)
        base_username = match.group("name") if match else member.display_name

        new_nick = self._format_name(base_username, emojis, fmt)

        # Only update when necessary to avoid endless re-formatting
        if member.display_name == new_nick:
            return

        try:    
            await member.edit(nick=new_nick, reason='Updating role icons')
        except discord.Forbidden:
            _log.warning("Missing permissions to edit nickname for %s", member)
        except discord.HTTPException as exc:
            _log.error("Failed to change nickname: %s", exc)

    # Commands ------------------------------------------------------------

    @app_commands.command(name="update_icons", description="Update all member nicknames with role icons.")
    @app_commands.default_permissions(manage_guild=True)
    async def update_icons(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("❌ Guild context required.")
            return

        for member in guild.members:
            await self._apply_nickname(member)

        await interaction.followup.send("✔️ Alle Nicknames aktualisiert.")

    # Listener to auto-update when role added/removed

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles == after.roles and before.display_name == after.display_name:
            return
        await self._apply_nickname(after)


def build_regex(fmt: str) -> re.Pattern:
    pattern = (
        re.escape(fmt)
        .replace(r'\{username\}', r'(?P<name>.+?)')
        .replace(r'\{icons\}', r'.*')          # Icons dürfen alles sein
    )
    return re.compile(f'^{pattern}$')


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleIcons(bot)) 
