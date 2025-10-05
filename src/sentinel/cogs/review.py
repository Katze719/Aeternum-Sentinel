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

        # Components v2 with enhanced styling
        class ReviewView(discord.ui.LayoutView):
            def __init__(self, message: str):
                super().__init__()
                # Enhanced formatting with better structure
                content = f"# 📝 Review Anfrage\n\n{message}\n\n*Bitte lies dir alles sorgfältig durch.*"
                container = discord.ui.Container(
                    discord.ui.TextDisplay(content),
                    accent_colour=discord.Colour.blurple(),
                )
                self.add_item(container)
        
        await ctx.send(view=ReviewView(description))

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

        # Components v2 with enhanced styling
        class VodView(discord.ui.LayoutView):
            def __init__(self, link: str):
                super().__init__()
                # Enhanced formatting with clickable link
                content = (
                    f"# 📹 VOD Formular\n\n"
                    f"Nutze das folgende Formular, um deinen VOD-Link einzureichen:\n\n"
                    f"🔗 **[Zum Formular]({link})**\n\n"
                    f"*Stelle sicher, dass dein VOD alle relevanten Informationen enthält.*"
                )
                container = discord.ui.Container(
                    discord.ui.TextDisplay(content),
                    accent_colour=discord.Colour.orange(),
                )
                self.add_item(container)
        
        await ctx.send(view=VodView(link))

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

        # Components v2 with enhanced styling
        class TsView(discord.ui.LayoutView):
            def __init__(self, message: str):
                super().__init__()
                # Enhanced formatting with better structure
                content = (
                    f"# 🎤 TeamSpeak Server\n\n"
                    f"{message}\n\n"
                    f"*Verbinde dich mit dem Server, um mit deinem Team zu kommunizieren.*"
                )
                container = discord.ui.Container(
                    discord.ui.TextDisplay(content),
                    accent_colour=discord.Colour.green(),
                )
                self.add_item(container)
        
        await ctx.send(view=TsView(ts_message))

async def setup(bot: commands.Bot):
    await bot.add_cog(Review(bot)) 
