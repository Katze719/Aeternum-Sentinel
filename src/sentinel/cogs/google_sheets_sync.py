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
            _log.info("Starting manual sheet_sync for guild %s", guild.id)
            await self._sync_guild(guild)
            _log.info("Manual sheet_sync completed successfully for guild %s", guild.id)
        except Exception as exc:
            _log.exception("Manual sheet_sync failed for guild %s: %s", guild.id, exc)
            await interaction.followup.send(f"❌ Synchronisation fehlgeschlagen: {str(exc)}", ephemeral=True)
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

        _log.info("Starting sync for guild %s", guild.id)

        # Fetch google-sheet config
        cfg = storage.load_guild_config(guild.id)
        sheet_cfg = cfg.get("google_sheet")
        if not sheet_cfg:
            _log.warning("No google_sheet config found for guild %s", guild.id)
            return  # not configured

        creds_path: str | None = sheet_cfg.get("credentials_path")  # type: ignore[assignment]
        sheet_id: str | None = sheet_cfg.get("sheet_id")  # type: ignore[assignment]
        worksheet_name_in_cfg = sheet_cfg.get("worksheet_name")
        username_mappings = sheet_cfg.get("username_mappings", {})
        mapping_for_ws = {} if not worksheet_name_in_cfg else username_mappings.get(worksheet_name_in_cfg, {})

        _log.info("Guild %s config: sheet_id=%s, worksheet=%s, has_mapping=%s", 
                 guild.id, sheet_id, worksheet_name_in_cfg, bool(mapping_for_ws))

        if not sheet_id:
            _log.warning("No sheet_id configured for guild %s", guild.id)
            return

        try:
            # Google auth
            _log.info("Authenticating with Google Sheets for guild %s", guild.id)
            mgr = get_async_gspread_client_manager(creds_path) if creds_path else get_async_gspread_client_manager()
            agc = await mgr.authorize()
            ss = await agc.open_by_key(sheet_id)
            _log.info("Successfully opened Google Sheet %s for guild %s", sheet_id, guild.id)
        except Exception as e:
            _log.error("Failed to authenticate/open Google Sheet for guild %s: %s", guild.id, e)
            raise Exception(f"Google Sheets Authentifizierung fehlgeschlagen: {str(e)}")

        # --- Mapping Sheet: bot-config (DO NOT DELETE) ---
        mapping_sheet_name = "bot-config (DO NOT DELETE)"
        mapping_headers = ["discord_id", "username", "display_name", "joined_at", "last_seen", "status"]
        try:
            _log.info("Accessing mapping worksheet '%s' for guild %s", mapping_sheet_name, guild.id)
            mapping_ws = await ss.worksheet(mapping_sheet_name)
        except Exception:
            # Not found: create it
            _log.info("Creating mapping worksheet '%s' for guild %s", mapping_sheet_name, guild.id)
            mapping_ws = await ss.add_worksheet(mapping_sheet_name, rows=1000, cols=len(mapping_headers))
            await mapping_ws.update([mapping_headers], "A1")

        # Read all mapping rows (skip header)
        _log.info("Reading mapping data for guild %s", guild.id)
        mapping_rows = await mapping_ws.get_all_values()
        mapping = {}  # discord_id -> row index (1-based), row data
        for idx, row in enumerate(mapping_rows[1:], start=2):
            if len(row) < 1 or not row[0]:
                continue
            mapping[row[0]] = (idx, row)

        _log.info("Found %d existing mappings for guild %s", len(mapping), guild.id)

        # Aktuelle Member
        now = discord.utils.utcnow().isoformat(sep=" ", timespec="seconds")
        current_ids = set()
        updates = []  # (row_idx, new_row)
        for m in guild.members:
            current_ids.add(str(m.id))
            if str(m.id) in mapping:
                row_idx, old_row = mapping[str(m.id)]
                # Update username, display_name, last_seen nur wenn status geändert hat
                new_row = [
                    str(m.id),
                    m.name,
                    m.display_name,
                    old_row[3] if len(old_row) > 3 and old_row[3] else now,  # joined_at bleibt
                    old_row[4] if len(old_row) > 4 and old_row[4] else now,  # last_seen bleibt unverändert für aktive Member
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
                    now,  # last_seen für neue Member
                    "active",
                ]
                updates.append((None, new_row))

        # Markiere alle, die nicht mehr Member sind, als left
        for did, (row_idx, old_row) in mapping.items():
            if did not in current_ids and (len(old_row) < 6 or old_row[5] != "left"):
                # Setze status auf left, update last_seen nur beim Verlassen
                new_row = list(old_row)
                while len(new_row) < len(mapping_headers):
                    new_row.append("")
                new_row[4] = now  # last_seen nur beim Verlassen
                new_row[5] = "left"
                updates.append((row_idx, new_row))

        _log.info("Processing %d mapping updates for guild %s", len(updates), guild.id)

        # Schreibe alle Updates (bestehende Zeilen und neue Zeilen)
        for row_idx, row in updates:
            if row_idx is not None:
                rng = f"A{row_idx}:F{row_idx}"
                await mapping_ws.update([row], rng)
            else:
                await mapping_ws.append_row(row, value_input_option="USER_ENTERED")

        _log.info("Completed mapping updates for guild %s", guild.id)

        # --- Normale User-Listen: nur aktive Nutzer ---
        if worksheet_name_in_cfg:
            try:
                _log.info("Accessing worksheet '%s' for guild %s", worksheet_name_in_cfg, guild.id)
                ws = await ss.worksheet(worksheet_name_in_cfg)
            except Exception as e:
                _log.error("Failed to access worksheet '%s' for guild %s: %s", worksheet_name_in_cfg, guild.id, e)
                raise Exception(f"Worksheet '{worksheet_name_in_cfg}' nicht gefunden: {str(e)}")
        else:
            _log.info("Using first worksheet for guild %s", guild.id)
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

        _log.info("Found %d target members for guild %s (scope: %s)", len(target_members), guild.id, member_scope)

        # --------------------------------------------------
        # Determine anchor position from username mapping
        # --------------------------------------------------
        row_anchor = mapping_for_ws.get("row")  # 1-based
        col_anchor = mapping_for_ws.get("col")  # 0-based
        direction = mapping_for_ws.get("direction", "vertical")
        
        _log.info("Mapping config for guild %s: row=%s, col=%s, direction=%s", 
                 guild.id, row_anchor, col_anchor, direction)
        
        if row_anchor is None or col_anchor is None:
            _log.warning("No mapping defined for guild %s - nothing to update", guild.id)
            return

        # Lade das Worksheet nur EINMAL für alle Operationen
        _log.info("Loading worksheet data for guild %s", guild.id)
        all_values = await ws.get_all_values()
        
        # Build list of usernames (display names)
        names = [m.display_name for m in target_members]
        
        _log.info("Processing %d usernames for guild %s", len(names), guild.id)
        
        # --------------------------------------------------
        # Fetch existing names to compute longest length
        # --------------------------------------------------
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
        
        _log.info("Found %d existing names, %d new names for guild %s", len(existing_names), len(names), guild.id)
        
        # --------------------------------------------------
        # Username Mapping: Robuste Logik für alle Fälle
        # --------------------------------------------------
        username_updates = []  # (cell_range, new_value)
        
        if direction == "vertical":
            # Vertikales Mapping: Jede Zeile ist ein Name
            for i, name in enumerate(names):
                cell_range = f"{col_to_letter(col_anchor)}{row_anchor + i}"
                # Prüfe, ob sich der Wert geändert hat
                if i < len(existing_names) and existing_names[i] == name:
                    continue  # Keine Änderung
                username_updates.append((cell_range, [[name]]))
            
            # Lösche überschüssige Zeilen, falls weniger Namen als vorher
            if len(names) < len(existing_names):
                for i in range(len(names), len(existing_names)):
                    cell_range = f"{col_to_letter(col_anchor)}{row_anchor + i}"
                    username_updates.append((cell_range, [[""]]))
        else:
            # Horizontales Mapping: Alle Namen in einer Zeile
            current_row = existing_names if existing_names else [""] * max_len
            new_row = names + [""] * (max_len - len(names))
            
            # Prüfe, ob sich die Zeile geändert hat
            if current_row != new_row:
                cell_range = f"{col_to_letter(col_anchor)}{row_anchor}:{col_to_letter(col_anchor + max_len - 1)}{row_anchor}"
                username_updates.append((cell_range, [new_row]))
        
        _log.info("Prepared %d username updates for guild %s", len(username_updates), guild.id)
        
        # Führe Username-Updates aus
        if username_updates:
            try:
                _log.info("Executing username updates for guild %s", guild.id)
                for cell_range, value in username_updates:
                    await ws.update(value, cell_range)
                _log.info("Completed username updates for guild %s", guild.id)
            except Exception as e:
                _log.exception("Failed updating username mapping for guild %s: %s", guild.id, e)
                raise Exception(f"Username-Mapping Update fehlgeschlagen: {str(e)}")
        elif names:  # Falls keine Updates erkannt wurden, aber Namen vorhanden sind
            # Das passiert bei leeren Sheets oder wenn die Diff-Erkennung fehlschlägt
            _log.info("No username updates detected but names exist. Forcing update for guild %s", guild.id)
            try:
                if direction == "vertical":
                    # Force update für vertikales Mapping
                    for i, name in enumerate(names):
                        cell_range = f"{col_to_letter(col_anchor)}{row_anchor + i}"
                        await ws.update([[name]], cell_range)
                else:
                    # Force update für horizontales Mapping
                    new_row = names + [""] * (max_len - len(names))
                    cell_range = f"{col_to_letter(col_anchor)}{row_anchor}:{col_to_letter(col_anchor + max_len - 1)}{row_anchor}"
                    await ws.update([new_row], cell_range)
                _log.info("Completed forced username updates for guild %s", guild.id)
            except Exception as e:
                _log.exception("Failed forcing username update for guild %s: %s", guild.id, e)
                raise Exception(f"Erzwungenes Username-Update fehlgeschlagen: {str(e)}")

        # --------------------------------------------------
        # Regelspalten: mapping_columns aus der Config auswerten und eintragen
        # --------------------------------------------------
        mapping_columns_cfg = cfg.get("mapping_columns", {})
        mapping_columns = mapping_columns_cfg.get(worksheet_name_in_cfg, [])
        
        _log.info("Found %d mapping columns for guild %s", len(mapping_columns), guild.id)
        
        if mapping_columns:
            _log.info("Processing mapping columns for guild %s", guild.id)
            # Hole Header-Zeile und stelle sicher, dass sie vollständig ist
            header_row = all_values[row_anchor - 1] if row_anchor - 1 < len(all_values) else []
            
            # Map: Spaltenname -> Index (case-insensitive)
            col_name_to_idx = {name.lower().strip(): idx for idx, name in enumerate(header_row) if name.strip()}
            
            # Für jede Regelspalte den korrekten Index finden und Migration durchführen
            for col in mapping_columns:
                col_name = col["name"].strip()
                col_name_lower = col_name.lower()
                
                # Migration: Altes Format (mode, value, roles direkt) in neues Format (rules Array) konvertieren
                if "mode" in col and "rules" not in col:
                    # Altes Format → neues Format
                    old_rule = {
                        "mode": col["mode"],
                        "value": col.get("value", ""),
                        "roles": col.get("roles", [])
                    }
                    col["rules"] = [old_rule]
                    # Entferne alte Felder
                    col.pop("mode", None)
                    col.pop("value", None)
                    col.pop("roles", None)
                
                # Prüfe, ob es ein einzelner Buchstabe ist (A, B, C, etc.)
                if len(col_name) == 1 and col_name.upper() in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                    # Konvertiere Buchstabe zu Spaltenindex (A=0, B=1, C=2, etc.)
                    col_index = ord(col_name.upper()) - ord('A')
                    col["_computed_index"] = col_index
                else:
                    # Suche nach dem Namen in der Header-Zeile
                    if col_name_lower in col_name_to_idx:
                        col["_computed_index"] = col_name_to_idx[col_name_lower]
                    else:
                        # Fallback: Füge am Ende hinzu
                        col["_computed_index"] = len(header_row)
                        header_row.append(col["name"])
            
            # Stelle sicher, dass die Header-Zeile lang genug ist
            max_index = max(col["_computed_index"] for col in mapping_columns) if mapping_columns else 0
            while len(header_row) <= max_index:
                header_row.append("")
            
            # Aktualisiere all_values mit der erweiterten Header-Zeile (nur wenn nötig)
            header_changed = False
            if row_anchor - 1 < len(all_values):
                if all_values[row_anchor - 1] != header_row:
                    all_values[row_anchor - 1] = header_row
                    header_changed = True
            else:
                # Füge Header-Zeile hinzu, falls sie nicht existiert
                while len(all_values) < row_anchor - 1:
                    all_values.append([""] * len(header_row))
                all_values.append(header_row)
                header_changed = True
            
            # Sammle Regelspalten-Updates (nur Diffs)
            rule_updates = []  # (cell_range, new_value)
            
            # Für jede Zeile (Member) die Regelspalten füllen
            for i, m in enumerate(target_members):
                # Zeile im Sheet (bei vertical: row_anchor + i)
                row_idx = row_anchor - 1 + i if direction == "vertical" else row_anchor - 1
                
                # Stelle sicher, dass die Zeile existiert und lang genug ist
                while row_idx >= len(all_values):
                    all_values.append([""] * len(header_row))
                
                row = all_values[row_idx]
                # Stelle sicher, dass Zeile lang genug ist
                while len(row) <= max_index:
                    row.append("")
                
                # Sammle Änderungen für diese Zeile
                row_changes = []
                
                for col in mapping_columns:
                    idx = col["_computed_index"]
                    rules = col.get("rules", [])
                    behavior = col.get("behavior", "first")  # Default: erste Regel verwenden
                    
                    # Finde alle passenden Regeln
                    matching_rules = []
                    for rule in rules:
                        # Prüfe, ob Member eine der Rollen aus dieser Regel hat
                        has_role = any(str(r.id) in rule.get("roles", []) for r in m.roles)
                        if has_role:
                            matching_rules.append(rule)
                    
                    # Bestimme den neuen Wert basierend auf dem Verhalten
                    new_value = ""
                    if matching_rules:
                        if behavior == "first":
                            # Erste passende Regel verwenden
                            rule = matching_rules[0]
                            if rule.get("mode") == "truefalse":
                                new_value = "true"
                            elif rule.get("mode") == "string":
                                new_value = rule.get("value", "")
                        elif behavior == "combine":
                            # Alle Werte mit Komma trennen
                            values = []
                            for rule in matching_rules:
                                if rule.get("mode") == "truefalse":
                                    values.append("true")
                                elif rule.get("mode") == "string":
                                    value = rule.get("value", "")
                                    if value and value not in values:  # Duplikate vermeiden
                                        values.append(value)
                            new_value = ", ".join(values)
                    
                    # Prüfe, ob sich der Wert geändert hat
                    current_value = row[idx] if idx < len(row) else ""
                    if current_value != new_value:
                        row_changes.append((idx, new_value))
                        row[idx] = new_value  # Update in all_values für zukünftige Vergleiche
                
                # Erstelle Update für diese Zeile (nur wenn Änderungen vorhanden)
                if row_changes:
                    # Sortiere nach Spaltenindex für konsistente Updates
                    row_changes.sort(key=lambda x: x[0])
                    
                    # Erstelle Range für die geänderten Zellen
                    min_col = min(idx for idx, _ in row_changes)
                    max_col = max(idx for idx, _ in row_changes)
                    
                    # Extrahiere nur die geänderten Werte
                    changed_values = [row[idx] for idx in range(min_col, max_col + 1)]
                    
                    cell_range = f"{col_to_letter(min_col)}{row_idx + 1}:{col_to_letter(max_col)}{row_idx + 1}"
                    rule_updates.append((cell_range, [changed_values]))
            
            _log.info("Prepared %d rule updates for guild %s", len(rule_updates), guild.id)
            
            # Führe Regelspalten-Updates aus (nur wenn Änderungen vorhanden)
            if rule_updates:
                try:
                    _log.info("Executing rule updates for guild %s", guild.id)
                    for cell_range, value in rule_updates:
                        await ws.update(value, cell_range)
                    _log.info("Completed rule updates for guild %s", guild.id)
                except Exception as e:
                    _log.exception("Failed updating Regelspalten for guild %s: %s", guild.id, e)
                    raise Exception(f"Regelspalten-Update fehlgeschlagen: {str(e)}")
        
        _log.info("Sync completed successfully for guild %s", guild.id)

# Helper: convert column index to letter(s)
def col_to_letter(idx: int) -> str:
    s = ""
    while idx >= 0:
        s = chr(idx % 26 + 65) + s
        idx = idx // 26 - 1
    return s

async def setup(bot: commands.Bot):  # noqa: D401
    await bot.add_cog(GoogleSheetsSync(bot)) 
