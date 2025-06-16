"""Package containing bot cogs (modules with commands, listeners, etc.).

Each cog module should expose an asynchronous `setup(bot: commands.Bot)` function
as described in the discord.py docs:
https://discordpy.readthedocs.io/en/stable/ext/commands/api.html#discord.ext.commands.CogMeta.setup

Example:

    class MyCog(commands.Cog):
        ...

    async def setup(bot):
        await bot.add_cog(MyCog(bot))
""" 
