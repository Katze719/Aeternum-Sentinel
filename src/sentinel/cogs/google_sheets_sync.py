from __future__ import annotations

"""Cog that synchronises guild members to a Google Sheet.

The concrete spreadsheet to use ("sheet_id") must be configured via the
REST-API exposed by *sentinel.web* (see :pymod:`sentinel.web.routes.guild_google_sheet`).
If the guild has not yet been configured an informative error message will be
shown to the command invoker.
"""

from typing import List, Set
import logging

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks

import sentinel.utils.storage as storage
from sentinel.integrations.google_sheets import get_async_gspread_client_manager

_log = logging.getLogger(__name__)


class GoogleSheetsSync(commands.Cog):
    """Sync Discord member information to Google Sheets."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._pending: Set[int] = set()
        self._sync_loop.start()

    # ------------------------------------------------------------------
    # Slash-commands
    # ------------------------------------------------------------------

    @app_commands.command(name="sheet_sync", description="Synchronise members to the configured Google Sheet.")
    @app_commands.checks.has_permissions(administrator=True)
    async def sheet_sync(self, interaction: discord.Interaction):  # noqa: D401
        """Push the current guild's member list to Google Sheets."""

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Dieser Befehl kann nur in einer Guild verwendet werden.", ephemeral=True)
            return

        cfg = storage.load_guild_config(guild.id)
        if not cfg.get("google_sheet"):
            await interaction.response.send_message(
                "ℹ️ Für diese Guild ist kein Google-Sheet konfiguriert.", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            await self._sync_guild(guild)
        except Exception as exc:
            _log.exception("Manual sheet_sync failed for guild %s: %s", guild.id, exc)
            await interaction.followup.send("❌ Synchronisation fehlgeschlagen. Bitte prüfe die Logs.", ephemeral=True)
            return

        await interaction.followup.send("✅ Mitglieder wurden erfolgreich mit Google Sheets synchronisiert.", ephemeral=True)

    # --------------------------------------------------------------
    # Background loop processing pending guild syncs (debounced)
    # --------------------------------------------------------------

    @tasks.loop(seconds=60)  # every minute
    async def _sync_loop(self):
        if not self._pending:
            return
        # Copy and clear to allow new events while syncing
        guild_ids = list(self._pending)
        self._pending.clear()
        for gid in guild_ids:
            guild = self.bot.get_guild(gid)
            if guild:
                try:
                    await self._sync_guild(guild)
                except Exception:
                    _log.exception("Auto-sync failed for guild %s", gid)

    @_sync_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    # --------------------------------------------------------------
    # Event listeners scheduling syncs
    # --------------------------------------------------------------

    async def _schedule_sync(self, guild: discord.Guild):
        self._pending.add(guild.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self._schedule_sync(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self._schedule_sync(member.guild)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # schedule if roles changed
        if set(before.roles) != set(after.roles):
            await self._schedule_sync(after.guild)

    # --------------------------------------------------------------
    # Core sync implementation (used by slash command + auto-loop)
    # --------------------------------------------------------------

    async def _sync_guild(self, guild: discord.Guild):
        """Synchronise *guild* members to its configured Google Sheet."""

        # Fetch google-sheet config
        cfg = storage.load_guild_config(guild.id)
        sheet_cfg = cfg.get("google_sheet")
        if not sheet_cfg:
            return  # not configured

        creds_path: str | None = sheet_cfg.get("credentials_path")  # type: ignore[assignment]
        sheet_id: str | None = sheet_cfg.get("sheet_id")  # type: ignore[assignment]
        worksheet_name_in_cfg = sheet_cfg.get("worksheet_name")
        username_mappings = sheet_cfg.get("username_mappings", {})
        mapping_for_ws = {} if not worksheet_name_in_cfg else username_mappings.get(worksheet_name_in_cfg, {})

        if not sheet_id:
            return

        # Google auth
        mgr = get_async_gspread_client_manager(creds_path) if creds_path else get_async_gspread_client_manager()
        agc = await mgr.authorize()
        ss = await agc.open_by_key(sheet_id)

        if worksheet_name_in_cfg:
            ws = await ss.worksheet(worksheet_name_in_cfg)
        else:
            ws = (await ss.worksheets())[0]

        # Build member list
        member_scope: str = mapping_for_ws.get("member_scope", "all")  # type: ignore[assignment]

        if member_scope == "role":
            ids_raw = mapping_for_ws.get("role_ids") or []
            if not isinstance(ids_raw, (list, tuple)):
                role_ids_int: List[int] = []
            else:
                try:
                    role_ids_int = [int(r) for r in ids_raw]
                except ValueError:
                    role_ids_int = []

            if role_ids_int:
                roles_required = [guild.get_role(rid) for rid in role_ids_int if guild.get_role(rid)]
                target_members = [m for m in guild.members if all(r in m.roles for r in roles_required)]
            else:
                target_members = []
        else:
            target_members = list(guild.members)

        # --------------------------------------------------
        # Determine anchor position from username mapping
        # --------------------------------------------------

        row_anchor = mapping_for_ws.get("row")  # 1-based
        col_anchor = mapping_for_ws.get("col")  # 0-based
        direction = mapping_for_ws.get("direction", "vertical")

        if row_anchor is None or col_anchor is None:
            # No mapping defined → nothing to update
            return

        # Build list of usernames (display names)
        names = [m.display_name for m in target_members]

        # --------------------------------------------------
        # Fetch existing names to compute longest length
        # --------------------------------------------------

        all_values = await ws.get_all_values()
        existing_names: List[str] = []
        if direction == "vertical":
            # Iterate from anchor downward until first empty cell
            r = row_anchor - 1  # 0-based index
            while r < len(all_values):
                row_vals = all_values[r]
                if col_anchor < len(row_vals) and row_vals[col_anchor]:
                    existing_names.append(row_vals[col_anchor])
                    r += 1
                else:
                    break
        else:
            # horizontal – look at anchor row
            r_idx = row_anchor - 1
            if r_idx < len(all_values):
                row_vals = all_values[r_idx]
                c = col_anchor
                while c < len(row_vals):
                    if row_vals[c]:
                        existing_names.append(row_vals[c])
                        c += 1
                    else:
                        break

        max_len = max(len(names), len(existing_names))

        if direction == "vertical":
            values = [[n] for n in names] + [[""]] * (max_len - len(names))
        else:
            pad = [""] * (max_len - len(names))
            values = [names + pad]

        # Clear an area large enough first (optional)
        # For simplicity, overwrite by writing values; leftover old entries may persist if list shrinks.
        # To keep sheet clean, write empty strings after list to clear previous data up to 1000 cells.
        try:
            await ws.update(values, f"{col_to_letter(col_anchor)}{row_anchor}")
        except Exception:
            _log.exception("Failed updating worksheet for guild %s", guild.id)

# Helper: convert column index to letter(s)
def col_to_letter(idx: int) -> str:
    s = ""
    while idx >= 0:
        s = chr(idx % 26 + 65) + s
        idx = idx // 26 - 1
    return s

async def setup(bot: commands.Bot):  # noqa: D401
    await bot.add_cog(GoogleSheetsSync(bot)) 
