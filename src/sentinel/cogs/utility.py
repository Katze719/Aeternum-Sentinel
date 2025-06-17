from discord.ext import commands


class Utility(commands.Cog):
    """General utility commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="ping", description="Check bot latency.")
    async def ping(self, ctx: commands.Context):  # noqa: D401
        latency = self.bot.latency * 1000  # Convert to ms
        await ctx.reply(f"Pong! {latency:.2f} ms")

    @commands.hybrid_command(
        name="web",
        description="Get the URL of the Sentinel web interface or this guild's settings page.",
    )
    async def web(self, ctx: commands.Context):  # noqa: D401
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
        if ctx.guild is not None:
            url = f"{base_url}/guilds/{ctx.guild.id}"
        else:
            # DM or unknown guild – fall back to dashboard landing.
            url = base_url

        await ctx.reply(f"🌐 Sentinel Web-UI: {url}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot)) 
