from discord.ext import commands
import discord
import sentinel.utils.storage as storage

# Default text if no custom message configured
DEFAULT_REVIEW_MESSAGE = (
    "No custom message configured for this server. Go to the web UI to set one."
)

# Default link if none configured
DEFAULT_VOD_LINK = "https://example.com"

# Default TS message if none configured
DEFAULT_TS_MESSAGE = "No TeamSpeak server configured for this server. Please contact an administrator."

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

    # --------------------------------------------------
    # VOD command
    # --------------------------------------------------

    @commands.hybrid_command(
        name="vod",
        description="Sende den Link zum VOD-Formular.",
    )
    async def vod(self, ctx: commands.Context):  # noqa: D401
        """Send a public message containing the VOD form link."""

        guild = ctx.guild
        if guild is not None:
            cfg = storage.load_guild_config(guild.id)
            link = cfg.get("vod_link", DEFAULT_VOD_LINK)
        else:
            link = DEFAULT_VOD_LINK

        if not link:
            link = DEFAULT_VOD_LINK

        embed = discord.Embed(
            title="📹 VOD Formular",
            description=f"Use the following form to submit your VOD link:\n{link}",
            url=link,
            color=discord.Color.orange(),
        )
        await ctx.send(embed=embed)

    # --------------------------------------------------
    # TeamSpeak command
    # --------------------------------------------------

    @commands.hybrid_command(
        name="ts",
        description="Sende die TeamSpeak Server Informationen.",
    )
    async def ts(self, ctx: commands.Context):  # noqa: D401
        """Send a public message containing the TeamSpeak server information."""

        guild = ctx.guild
        if guild is not None:
            cfg = storage.load_guild_config(guild.id)
            ts_message = cfg.get("ts_message", DEFAULT_TS_MESSAGE)
        else:
            ts_message = DEFAULT_TS_MESSAGE

        if not ts_message:
            ts_message = DEFAULT_TS_MESSAGE

        embed = discord.Embed(
            title="🎤 TeamSpeak Server",
            description=ts_message,
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Review(bot)) 
