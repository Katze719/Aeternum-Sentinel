from discord.ext import commands


class Utility(commands.Cog):
    """General utility commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="ping", description="Check bot latency.")
    async def ping(self, ctx: commands.Context):  # noqa: D401
        latency = self.bot.latency * 1000  # Convert to ms
        await ctx.reply(f"Pong! {latency:.2f} ms")


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot)) 