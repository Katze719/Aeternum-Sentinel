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
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latenz: **{latency:.2f} ms**",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)

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

        embed = discord.Embed(
            title="🌐 Sentinel Web-UI",
            description=url,
            color=discord.Color.blue(),
            url=url,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot)) 
