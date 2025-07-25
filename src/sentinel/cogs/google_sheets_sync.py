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

        # --- Mapping Sheet: bot-config (DO NOT DELETE) ---
        mapping_sheet_name = "bot-config (DO NOT DELETE)"
        mapping_headers = ["discord_id", "username", "display_name", "joined_at", "last_seen", "status"]
        try:
            mapping_ws = await ss.worksheet(mapping_sheet_name)
        except Exception:
            # Not found: create it
            mapping_ws = await ss.add_worksheet(mapping_sheet_name, rows=1000, cols=len(mapping_headers))
            await mapping_ws.update([mapping_headers], "A1")

        # Read all mapping rows (skip header)
        mapping_rows = await mapping_ws.get_all_values()
        mapping = {}  # discord_id -> row index (1-based), row data
        for idx, row in enumerate(mapping_rows[1:], start=2):
            if len(row) < 1 or not row[0]:
                continue
            mapping[row[0]] = (idx, row)

        # Aktuelle Member
        now = discord.utils.utcnow().isoformat(sep=" ", timespec="seconds")
        current_ids = set()
        updates = []  # (row_idx, new_row)
        for m in guild.members:
            current_ids.add(str(m.id))
            if str(m.id) in mapping:
                row_idx, old_row = mapping[str(m.id)]
                # Update username, display_name, last_seen, status
                new_row = [
                    str(m.id),
                    m.name,
                    m.display_name,
                    old_row[3] if len(old_row) > 3 and old_row[3] else now,  # joined_at bleibt
                    now,
                    "active",
                ]
                updates.append((row_idx, new_row))
            else:
                # New entry
                new_row = [
                    str(m.id),
                    m.name,
                    m.display_name,
                    now,
                    now,
                    "active",
                ]
                updates.append((None, new_row))

        # Markiere alle, die nicht mehr Member sind, als left
        for did, (row_idx, old_row) in mapping.items():
            if did not in current_ids and (len(old_row) < 6 or old_row[5] != "left"):
                # Setze status auf left, update last_seen
                new_row = list(old_row)
                while len(new_row) < len(mapping_headers):
                    new_row.append("")
                new_row[4] = now  # last_seen
                new_row[5] = "left"
                updates.append((row_idx, new_row))

        # Schreibe alle Updates (bestehende Zeilen und neue Zeilen)
        for row_idx, row in updates:
            if row_idx is not None:
                rng = f"A{row_idx}:F{row_idx}"
                await mapping_ws.update([row], rng)
            else:
                await mapping_ws.append_row(row, value_input_option="USER_ENTERED")

        # --- Normale User-Listen: nur aktive Nutzer ---
        if worksheet_name_in_cfg:
            ws = await ss.worksheet(worksheet_name_in_cfg)
        else:
            ws = (await ss.worksheets())[0]

        # Build member list (nur aktive Nutzer laut Mapping)
        member_scope: str = mapping_for_ws.get("member_scope", "all")
        active_ids = {str(m.id) for m in guild.members}
        # Filtere auf status=active im Mapping-Sheet
        active_mapping = {did: row for did, (idx, row) in mapping.items() if len(row) >= 6 and row[5] == "active"}
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
                target_members = [m for m in guild.members if all(r in m.roles for r in roles_required) and str(m.id) in active_mapping]
            else:
                target_members = []
        else:
            target_members = [m for m in guild.members if str(m.id) in active_mapping]

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
