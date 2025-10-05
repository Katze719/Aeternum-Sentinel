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
        """Replace placeholders in *fmt* and tidy up if no *emojis* are present.

        Besides the simple placeholder replacement we perform an additional cleanup
        step: if *emojis* is empty we remove any left-over punctuation or whitespace
        which might have surrounded the ``{icons}`` placeholder (e.g. "[ ]", "()",
        or simple trailing spaces). This prevents artefacts such as an empty pair
        of brackets ("[]") or a dangling space from remaining in the nickname when
        the icon list is empty.
        """

        # First perform the raw replacement.
        rendered = fmt.replace("{username}", username).replace("{icons}", "".join(emojis))

        # If there are no emojis we may have to strip left-over characters that
        # were intended to wrap the icons (e.g. " []", " ()", " {}") or superfluous
        # whitespace. We only run this expensive regex cleanup if *emojis* is empty
        # because otherwise we want to keep the surrounding delimiters.
        if not emojis:
            # 1) Remove common wrapping patterns that ended up empty, optionally
            #    preceded by whitespace.  Examples that should vanish:
            #       " []", "()", " \u200B[]" …
            rendered = re.sub(r"\s*([\[\(\{])\s*[\]\)\}]\s*", "", rendered)

            # 2) Remove dangling separators like '|', '-', ':' etc. that remain
            #    at the *end* of the nickname once the icons are gone.
            rendered = re.sub(r"\s*[\|\-–—~•:;>+]+\s*$", "", rendered)

            # 3) Collapse multiple consecutive whitespace characters and trim.
            rendered = re.sub(r"\s{2,}", " ", rendered).strip()

        return rendered

    @staticmethod
    def _build_regex(fmt: str) -> re.Pattern:
        """Build a regex that extracts the *base* username from an already
        formatted nickname.

        The resulting pattern always contains a named capturing group ``name`` for
        the username.  If the supplied *fmt* still contains an ``{icons}``
        placeholder we replace it with a greedy ``.*``.  If it no longer contains
        that placeholder (because the guild owner removed it) we nevertheless
        allow an *optional* trailing icon segment so that we can clean up stale
        icons that might still be present in old nicknames.
        """

        has_icons_placeholder = "{icons}" in fmt

        # Use NON-greedy capture when we *expect* an icon segment afterwards, but
        # greedy capture when the segment is optional – otherwise we would only
        # grab the first word of multi-part names ("Tim Hubert" → "Tim").
        name_group = r"(?P<name>.+?)" if has_icons_placeholder else r"(?P<name>.+)"

        pattern = re.escape(fmt).replace(r"\{username\}", name_group)

        if has_icons_placeholder:
            # The format still includes the placeholder ⇒ direct substitution.
            pattern = pattern.replace(r"\{icons\}", r".*")
        else:
            # No placeholder anymore ⇒ treat a trailing icon part as *optional*.
            # Typical historic patterns have icons at the end, separated by a
            # space and maybe wrapped in brackets.  We therefore allow either:
            #   " <anything>"           – space followed by icons
            #   " [<anything>]"         – space + icons wrapped in []
            pattern += r"(?:\s*\[.*\]|\s+.*)?"

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
        base_username = match.group("name").strip() if match else member.display_name.strip()

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
            # Components v2 error message with enhanced styling
            class ErrorView(discord.ui.LayoutView):
                def __init__(self):
                    super().__init__()
                    content = (
                        "# ❌ Fehler\n\n"
                        "Dieser Befehl kann nur in einem Server verwendet werden.\n\n"
                        "*Bitte führe den Befehl in einem Discord-Server aus.*"
                    )
                    container = discord.ui.Container(
                        discord.ui.TextDisplay(content),
                        accent_colour=discord.Colour.red(),
                    )
                    self.add_item(container)
            
            await interaction.followup.send(view=ErrorView(), ephemeral=True)
            return

        for member in guild.members:
            await self._apply_nickname(member)

        # Components v2 success message with enhanced styling
        class SuccessView(discord.ui.LayoutView):
            def __init__(self, member_count: int):
                super().__init__()
                content = (
                    "# ✅ Nicknames aktualisiert\n\n"
                    f"Alle **{member_count}** Mitglieder-Nicknames wurden erfolgreich mit ihren Rollen-Icons aktualisiert.\n\n"
                    "*Die Änderungen sind sofort sichtbar.*"
                )
                container = discord.ui.Container(
                    discord.ui.TextDisplay(content),
                    accent_colour=discord.Colour.green(),
                )
                self.add_item(container)
        
        await interaction.followup.send(view=SuccessView(len(guild.members)))

    # Listener to auto-update when role added/removed

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles == after.roles and before.display_name == after.display_name:
            return
        await self._apply_nickname(after)


def build_regex(fmt: str) -> re.Pattern:
    # Keep behaviour in sync with RoleIcons._build_regex
    has_icons_placeholder = '{icons}' in fmt
    name_group = r'(?P<name>.+?)' if has_icons_placeholder else r'(?P<name>.+)'

    pattern = re.escape(fmt).replace(r'\{username\}', name_group)

    if has_icons_placeholder:
        pattern = pattern.replace(r'\{icons\}', r'.*')
    else:
        pattern += r'(?:\s*\[.*\]|\s+.*)?'

    return re.compile(f'^{pattern}$')


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleIcons(bot)) 
