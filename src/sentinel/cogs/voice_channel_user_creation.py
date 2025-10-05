from __future__ import annotations

import logging
from typing import Dict, Optional
import re

import discord
from discord.ext import commands
from discord import app_commands

from sentinel.utils.storage import load_guild_config, save_guild_config

_log = logging.getLogger(__name__)

# Config keys and defaults
VCUC_CONFIG_KEY = "voice_channel_user_creation_config"  # mapping: generator_id -> {target_category_id, name_pattern}
VCUC_ENABLED_KEY = "voice_channel_user_creation_enabled"
DEFAULT_NAME_PATTERN = "{username}"


class VoiceChannelUserCreation(commands.Cog):
    """Erstellt temporäre Voice-Channels, wenn ein Nutzer einen definierten Generator-Channel betritt."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._auto_channels: Dict[int, set[int]] = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_enabled(cfg: dict) -> bool:
        return cfg.get(VCUC_ENABLED_KEY, False)

    @staticmethod
    def _generator_map(cfg: dict) -> dict[str, dict]:
        return cfg.get(VCUC_CONFIG_KEY, {})

    def _register_auto_channel(self, guild_id: int, channel_id: int):
        self._auto_channels.setdefault(guild_id, set()).add(channel_id)

    def _is_auto_channel(self, guild_id: int, channel_id: int) -> bool:
        # Fast-path check in in-memory set first
        if channel_id in self._auto_channels.get(guild_id, set()):
            return True

        # Fallback to on-disk config to support bot restarts
        cfg = load_guild_config(guild_id)
        chan_ids = cfg.get(self._PERSIST_KEY, [])
        if channel_id in chan_ids:
            # Lazily repopulate in-memory cache for faster future lookups
            self._register_auto_channel(guild_id, channel_id)
            return True
        return False

    async def _cleanup_channel_if_empty(self, channel: discord.VoiceChannel):
        if channel.members:
            return
        guild_id = channel.guild.id
        if not self._is_auto_channel(guild_id, channel.id):
            return
        try:
            await channel.delete(reason="Cleaning up empty auto voice channel")
            self._auto_channels[guild_id].discard(channel.id)
            self._persist_autochannel_remove(guild_id, channel.id)
        except discord.Forbidden:
            _log.warning("Missing permissions to delete voice channel %s (guild %s)", channel, guild_id)
        except discord.HTTPException as exc:
            _log.error("Failed to delete voice channel %s: %s", channel, exc)

    # ------------------------------------------------------------------
    # Persistent storage helpers
    # ------------------------------------------------------------------

    _PERSIST_KEY = "voice_channel_user_creation_autochannels"  # list[int]

    def _persist_autochannel_add(self, guild_id: int, chan_id: int) -> None:
        """Store a newly created auto-channel in the on-disk guild config."""
        data = load_guild_config(guild_id)
        ids = set(data.get(self._PERSIST_KEY, []))
        ids.add(chan_id)
        data[self._PERSIST_KEY] = list(ids)
        save_guild_config(guild_id, data)

    def _persist_autochannel_remove(self, guild_id: int, chan_id: int) -> None:
        """Remove an auto-channel from the on-disk guild config (if present)."""
        data = load_guild_config(guild_id)
        if self._PERSIST_KEY in data:
            ids = set(data[self._PERSIST_KEY])
            ids.discard(chan_id)
            data[self._PERSIST_KEY] = list(ids)
            save_guild_config(guild_id, data)

    # ------------------------------------------------------------------
    # Listener
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        # Ignore changes that don't involve switching channels (e.g. mute, deaf)
        if before.channel == after.channel:
            return

        guild = member.guild
        cfg = load_guild_config(guild.id)
        if not self._is_enabled(cfg):
            return

        generator_map = self._generator_map(cfg)
        if not after.channel or str(after.channel.id) not in generator_map:
            # Might still need to clean up previous channel
            if before.channel and isinstance(before.channel, discord.VoiceChannel):
                await self._cleanup_channel_if_empty(before.channel)
            return

        entry = generator_map[str(after.channel.id)]
        raw_cat_id = entry.get("target_category_id")
        category_id: Optional[int] = int(raw_cat_id) if raw_cat_id is not None else None
        name_pattern: str = entry.get("name_pattern") or entry.get("name_format") or DEFAULT_NAME_PATTERN

        if category_id is None:
            _log.warning("Generator channel %s configured without target category", after.channel.id)
            return

        category = guild.get_channel(category_id)  # type: ignore[arg-type]
        if category is None or not isinstance(category, discord.CategoryChannel):
            _log.warning("Configured target category %s not found in guild %s", raw_cat_id, guild.id)
            return

        # ------------------------------------------------------------------
        # Berechtigungen des Bots prüfen
        # ------------------------------------------------------------------

        bot_member: Optional[discord.Member] = guild.me  # type: ignore[assignment]
        if bot_member is None:
            _log.warning("Bot-Mitgliedsobjekt in Guild %s nicht gefunden", guild.id)
            return

        perms_global = bot_member.guild_permissions
        perms_category = category.permissions_for(bot_member)

        # Manage Channels ⇢ Channel erstellen/löschen/verschieben
        if not (perms_global.manage_channels or perms_category.manage_channels):
            _log.warning(
                "Fehlende Berechtigung 'Manage Channels': Bot kann in Guild %s oder Kategorie '%s' keinen Kanal erstellen",
                guild.id,
                category.name,
            )
            return

        # Move Members ⇢ Mitglieder verschieben
        if not (perms_global.move_members or perms_category.move_members):
            _log.warning(
                "Fehlende Berechtigung 'Move Members': Bot kann Nutzer in Guild %s oder Kategorie '%s' nicht verschieben",
                guild.id,
                category.name,
            )
            return

        # Resolve placeholders in pattern
        chan_name = name_pattern.replace("{username}", member.display_name)

        if "{number}" in chan_name:
            number = self._next_channel_number(name_pattern, category, member.display_name)
            chan_name = chan_name.replace("{number}", str(number))

        try:
            # Copy permission overwrites from the generator channel so that the
            # newly created channel inherits the same access rules.
            new_channel = await guild.create_voice_channel(
                chan_name,
                category=category,
                overwrites=after.channel.overwrites if after.channel else None,  # type: ignore[arg-type]
                reason="Auto voice channel creation",
            )
        except discord.Forbidden:
            _log.warning("Missing permissions to create voice channel in guild %s", guild.id)
            return
        except discord.HTTPException as exc:
            _log.error("Failed to create voice channel: %s", exc)
            return

        self._register_auto_channel(guild.id, new_channel.id)
        self._persist_autochannel_add(guild.id, new_channel.id)

        try:
            await member.move_to(new_channel, reason="Moving to auto voice channel")
        except discord.Forbidden:
            _log.warning("Missing permissions to move member in guild %s", guild.id)
        except discord.HTTPException as exc:
            _log.error("Failed to move member: %s", exc)

        # Clean up previous channel if empty
        if before.channel and isinstance(before.channel, discord.VoiceChannel):
            await self._cleanup_channel_if_empty(before.channel)

    # ------------------------------------------------------------------
    # Command
    # ------------------------------------------------------------------

    @app_commands.command(name="cleanup_voice", description="Delete empty auto-created voice channels.")
    @app_commands.default_permissions(manage_guild=True)
    async def cleanup_voice(self, interaction: discord.Interaction):
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
            
            await interaction.response.send_message(view=ErrorView(), ephemeral=True)
            return

        removed = 0
        # Combine in-memory and persisted IDs to ensure complete cleanup
        persisted_ids = set(load_guild_config(guild.id).get(self._PERSIST_KEY, []))
        candidate_ids = set(self._auto_channels.get(guild.id, set())) | persisted_ids

        for chan_id in list(candidate_ids):
            channel = guild.get_channel(chan_id)
            if isinstance(channel, discord.VoiceChannel) and not channel.members:
                try:
                    await channel.delete(reason="Manual cleanup via command")
                    self._auto_channels[guild.id].discard(chan_id)
                    self._persist_autochannel_remove(guild.id, chan_id)
                    removed += 1
                except discord.Forbidden:
                    pass

        # Components v2 success message with enhanced styling
        class SuccessView(discord.ui.LayoutView):
            def __init__(self, count: int):
                super().__init__()
                if count == 0:
                    content = (
                        "# ✅ Cleanup abgeschlossen\n\n"
                        "Keine leeren Voice-Channels gefunden.\n\n"
                        "*Alle Voice-Channels werden aktiv genutzt.*"
                    )
                elif count == 1:
                    content = (
                        "# ✅ Cleanup abgeschlossen\n\n"
                        "**1** leerer Voice-Channel wurde entfernt.\n\n"
                        "*Der Server ist jetzt aufgeräumt.*"
                    )
                else:
                    content = (
                        f"# ✅ Cleanup abgeschlossen\n\n"
                        f"**{count}** leere Voice-Channels wurden entfernt.\n\n"
                        f"*Der Server ist jetzt aufgeräumt.*"
                    )
                container = discord.ui.Container(
                    discord.ui.TextDisplay(content),
                    accent_colour=discord.Colour.green(),
                )
                self.add_item(container)
        
        await interaction.response.send_message(view=SuccessView(removed))

    # ------------------------------------------------------------------
    # Internal numbering helper
    # ------------------------------------------------------------------

    @staticmethod
    def _build_number_regex(pattern: str, username_resolved: str) -> re.Pattern:
        escaped = re.escape(pattern)
        escaped = escaped.replace(re.escape("{username}"), re.escape(username_resolved))
        escaped = escaped.replace(re.escape("{number}"), r"(\d+)")
        return re.compile(f"^{escaped}$")

    def _next_channel_number(self, pattern: str, category: discord.CategoryChannel, username_val: str) -> int:
        regex = self._build_number_regex(pattern, username_val)
        max_num = 0
        for channel in category.channels:
            if not isinstance(channel, discord.VoiceChannel):
                continue
            m = regex.match(channel.name)
            if m and m.groups():
                try:
                    num = int(m.group(1))
                    max_num = max(max_num, num)
                except ValueError:
                    continue
        return max_num + 1 if max_num else 1


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceChannelUserCreation(bot)) 
