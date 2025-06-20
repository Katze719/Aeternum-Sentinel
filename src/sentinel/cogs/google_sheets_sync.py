from __future__ import annotations

"""Cog that synchronises guild members to a Google Sheet.

The concrete spreadsheet to use ("sheet_id") must be configured via the
REST-API exposed by *sentinel.web* (see :pymod:`sentinel.web.routes.guild_google_sheet`).
If the guild has not yet been configured an informative error message will be
shown to the command invoker.
"""

from typing import List
import logging

import discord
from discord import app_commands
from discord.ext import commands

import sentinel.utils.storage as storage
from sentinel.integrations.google_sheets import get_async_gspread_client_manager

_log = logging.getLogger(__name__)


class GoogleSheetsSync(commands.Cog):
    """Sync Discord member information to Google Sheets."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

        # ------------------------------------------------------------------
        # Fetch google-sheet config for this guild.
        # ------------------------------------------------------------------
        cfg = storage.load_guild_config(guild.id)
        sheet_cfg = cfg.get("google_sheet")
        if not sheet_cfg:
            await interaction.response.send_message(
                "ℹ️ Für diese Guild ist kein Google-Sheet konfiguriert.", ephemeral=True
            )
            return

        creds_path: str = sheet_cfg.get("credentials_path")  # type: ignore[assignment]
        sheet_id: str = sheet_cfg.get("sheet_id")  # type: ignore[assignment]
        worksheet_name: str | None = sheet_cfg.get("worksheet_name")  # type: ignore[assignment]

        if not creds_path or not sheet_id:
            await interaction.response.send_message("Die Sheet-Konfiguration ist unvollständig.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        try:
            # Authorise once per command invocation; the low traffic should be OK.
            mgr = get_async_gspread_client_manager(creds_path)
            agc = await mgr.authorize()

            # Open spreadsheet and pick worksheet.
            ss = await agc.open_by_key(sheet_id)

            if worksheet_name:
                ws = await ss.worksheet(worksheet_name)
            else:
                # Fallback: first worksheet
                ws_list = await ss.worksheets()
                ws = ws_list[0]

            # ------------------------------------------------------------------
            # Prepare data: header + rows
            # ------------------------------------------------------------------
            header = [
                "User ID",
                "Username#Discriminator",
                "Display-Name",
                "Bots?",
                "Joined at",
            ]

            rows: List[List[str]] = [header]
            for member in guild.members:
                rows.append(
                    [
                        str(member.id),
                        str(member),  # username#discrim
                        member.display_name,
                        "✅" if member.bot else "❌",
                        member.joined_at.isoformat() if member.joined_at else "",
                    ]
                )

            # ------------------------------------------------------------------
            # Write to sheet: clear old contents first, then batch-update.
            # ------------------------------------------------------------------
            await ws.clear()
            # Update the sheet starting at the first cell (A1)
            await ws.update(rows)

        except Exception as exc:  # pragma: no cover – anything can go wrong when calling external APIs
            _log.exception("Failed to sync members for guild %s: %s", guild.id, exc)
            await interaction.followup.send(
                "❌ Synchronisation fehlgeschlagen. Bitte prüfe die Logs.", ephemeral=True
            )
            return

        await interaction.followup.send(
            f"✅ {len(guild.members)} Mitglieder wurden erfolgreich mit Google Sheets synchronisiert.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):  # noqa: D401
    await bot.add_cog(GoogleSheetsSync(bot)) 
