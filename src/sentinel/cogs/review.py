from discord.ext import commands
import discord
import sentinel.utils.storage as storage

# Default text if no custom message configured
DEFAULT_REVIEW_MESSAGE = (
    "No custom message configured for this server. Go to the web UI to set one."
)

class Review(commands.Cog):
    """Commands related to user review requests."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="review",
        description="Starte eine Review-Anfrage an den Nutzer.",
    )
    async def review(self, ctx: commands.Context):  # noqa: D401
        """Send a visible message with review questions (placeholder)."""

        # Resolve guild-specific message from storage (set via web UI)
        guild = ctx.guild
        if guild is not None:
            cfg = storage.load_guild_config(guild.id)
            description = cfg.get("review_message", DEFAULT_REVIEW_MESSAGE)
        else:
            description = DEFAULT_REVIEW_MESSAGE

        embed = discord.Embed(
            title="📝 Review",
            description=description,
            color=discord.Color.blurple(),
        )
        # Send publicly visible message (not ephemeral)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Review(bot)) 
