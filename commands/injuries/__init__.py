"""
Injury commands package

Provides commands for managing player injuries:
- /injury roll - Roll for injury using player's injury rating
- /injury set-new - Set a new injury for a player
- /injury clear - Clear a player's injury
"""
from discord.ext import commands
from .management import setup

__all__ = ['setup_injuries']


async def setup_injuries(bot: commands.Bot) -> tuple[int, int, list[str]]:
    """
    Setup function for loading injury commands.

    Returns:
        Tuple of (successful_count, failed_count, failed_module_names)
    """
    successful = 0
    failed = 0
    failed_modules = []

    try:
        await setup(bot)
        successful += 1
    except Exception as e:
        bot.logger.error(f"Failed to load InjuryGroup: {e}")
        failed += 1
        failed_modules.append('InjuryGroup')

    return successful, failed, failed_modules
