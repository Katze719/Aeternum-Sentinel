from discord.ext import commands


class Utility(commands.Cog):
    """General utility commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="ping", description="Check bot latency.")
    async def ping(self, ctx: commands.Context):  # noqa: D401
        latency = self.bot.latency * 1000  # Convert to ms
        await ctx.reply(f"Pong! {latency:.2f} ms")

    @commands.hybrid_command(name="web", description="Get the URL of the Sentinel web interface.")
    async def web(self, ctx: commands.Context):  # noqa: D401
        """Return the public URL where the FastAPI UI is reachable."""

        # Import lazily to avoid circulars
        from sentinel.config import get_settings  # type: ignore

        settings = get_settings()

        # Derive base URL from the OAuth redirect URI to respect overrides via
        # environment variables (OAUTH_REDIRECT_URI).
        base_url = settings.oauth_redirect_uri.rsplit("/", 1)[0]

        await ctx.reply(f"🌐 Sentinel Web-UI: {base_url}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot)) 
