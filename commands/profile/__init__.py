"""
Profile management commands package.

Handles user-facing profile management including player image updates.
"""
from discord.ext import commands


async def setup_profile_commands(bot: commands.Bot):
    """Load profile management commands."""
    from commands.profile.images import ImageCommands
    await bot.add_cog(ImageCommands(bot))
