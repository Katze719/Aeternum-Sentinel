from discord.ext import commands
import discord
from discord import app_commands


class Utility(commands.Cog):
    """General utility commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check bot latency.")
    async def ping(self, interaction: discord.Interaction):  # noqa: D401
        latency = self.bot.latency * 1000  # Convert to ms
        
        # Components v2 with enhanced styling
        class PingView(discord.ui.LayoutView):
            def __init__(self, latency: float):
                super().__init__()
                # Enhanced formatting with latency indicator
                if latency < 100:
                    status = "🟢 Ausgezeichnet"
                    color = discord.Colour.green()
                elif latency < 200:
                    status = "🟡 Gut"
                    color = discord.Colour.gold()
                else:
                    status = "🔴 Hoch"
                    color = discord.Colour.red()
                
                content = (
                    f"# 🏓 Pong!\n\n"
                    f"**Latenz:** {latency:.2f} ms\n"
                    f"**Status:** {status}\n\n"
                    f"*Der Bot ist online und antwortet.*"
                )
                container = discord.ui.Container(
                    discord.ui.TextDisplay(content),
                    accent_colour=color,
                )
                self.add_item(container)
        
        await interaction.response.send_message(view=PingView(latency))

    @app_commands.command(
        name="web",
        description="Get the URL of the Sentinel web interface or this guild's settings page.",
    )
    async def web(self, interaction: discord.Interaction):  # noqa: D401
        """Return the web interface URL.

        If invoked from within a guild, respond with the direct link to **that** guild's
        settings page. Otherwise fall back to the generic landing page.
        """

        # Lazily import to prevent circular dependencies.
        from sentinel.config import get_settings  # type: ignore

        settings = get_settings()

        # Respect overrides of the public base URL via the OAUTH_REDIRECT_URI env var.
        base_url = settings.oauth_redirect_uri.rsplit("/", 1)[0]

        # If the command is used inside a guild, append the guild-specific path.
        if interaction.guild is not None:
            url = f"{base_url}/guilds/{interaction.guild.id}"
        else:
            # DM or unknown guild – fall back to dashboard landing.
            url = base_url

        # Components v2 with enhanced styling
        class WebView(discord.ui.LayoutView):
            def __init__(self, url: str, is_guild: bool):
                super().__init__()
                # Enhanced formatting with guild-specific message
                if is_guild:
                    desc = "Hier findest du die Einstellungen für diesen Server:"
                else:
                    desc = "Hier findest du das Sentinel Dashboard:"
                
                content = (
                    f"# 🌐 Sentinel Web-UI\n\n"
                    f"{desc}\n\n"
                    f"🔗 **[Web-Interface öffnen]({url})**\n\n"
                    f"*Konfiguriere deinen Bot über das benutzerfreundliche Web-Interface.*"
                )
                container = discord.ui.Container(
                    discord.ui.TextDisplay(content),
                    accent_colour=discord.Colour.blue(),
                )
                self.add_item(container)
        
        await interaction.response.send_message(view=WebView(url, interaction.guild is not None))

    @app_commands.command(name="changelog", description="Zeige den neuesten Changelog-Eintrag als Embed.")
    async def changelog(self, interaction: discord.Interaction):
        """Sendet den neuesten Changelog-Eintrag als Discord Embed."""
        import pathlib
        changelog_path = pathlib.Path(__file__).parent.parent.parent.parent / "CHANGELOG.md"
        try:
            with changelog_path.open("r", encoding="utf-8") as f:
                content = f.read()
        except Exception as exc:
            await interaction.response.send_message(f"Fehler beim Laden des Changelogs: {exc}", ephemeral=True)
            return

        # Finde den neuesten Changelog-Eintrag (alles bis zur nächsten # Überschrift)
        lines = content.splitlines()
        latest_changelog = []
        in_latest = False
        
        for line in lines:
            # Wenn wir eine neue Hauptüberschrift finden (nach dem ersten), stoppen wir
            if line.startswith('# ') and in_latest:
                break
            elif line.startswith('# '):
                in_latest = True
            
            if in_latest:
                latest_changelog.append(line)
        
        # Konvertiere zurück zu Text
        latest_content = '\n'.join(latest_changelog)
        
        # Extrahiere Version und Titel aus der ersten Zeile
        title_line = latest_changelog[0] if latest_changelog else ""
        version_match = title_line.split('–') if '–' in title_line else title_line.split('-')
        version = version_match[0].strip('# ') if version_match else "v1.0.1"
        title = version_match[1].strip() if len(version_match) > 1 else "Changelog"
        
        # Discord Embeds haben ein Limit von 4096 Zeichen pro Embed-Description
        if len(latest_content) > 4096:
            # Kürze den Inhalt und füge "..." hinzu
            latest_content = latest_content[:4093] + "..."
        
        # Components v2 with enhanced styling
        class ChangelogView(discord.ui.LayoutView):
            def __init__(self, title: str, content: str):
                super().__init__()
                # Enhanced formatting with better structure
                formatted_content = (
                    f"# 🦄 {title}\n\n"
                    f"{content}\n\n"
                    f"*Danke, dass du Sentinel nutzt!*"
                )
                container = discord.ui.Container(
                    discord.ui.TextDisplay(formatted_content),
                    accent_colour=discord.Colour.purple(),
                )
                self.add_item(container)
        
        await interaction.response.send_message(view=ChangelogView(title, latest_content))


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot)) 
