from discord.ext import commands
import discord
from discord import app_commands


class Review(commands.Cog):
    """Commands related to user review requests."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="review",
        description="Starte eine Review-Anfrage an den Nutzer.",
    )
    async def review(self, interaction: discord.Interaction):  # noqa: D401
        """Send a visible message with review questions (placeholder)."""

        embed = discord.Embed(
            title="📝 Review",
            description=(
                "Hier muss björn fragen einfügen.\n\n"
                "*(Leillith sloten!)\n\n"
                "*(Hier könnte ihre werbung stehen)\n\n"
                "GOAT Telefonsex 0190….*"
            ),
            color=discord.Color.blurple(),
        )
        # Send publicly visible message (not ephemeral)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Review(bot)) 
