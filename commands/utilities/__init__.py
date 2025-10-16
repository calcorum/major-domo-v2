"""
Utility commands package for Discord Bot v2.0

This package contains general utility commands that enhance user experience.
"""
import logging
from discord.ext import commands

from .weather import WeatherCommands
from .charts import ChartCommands, ChartManageGroup, ChartCategoryGroup

__all__ = ['WeatherCommands', 'ChartCommands', 'ChartManageGroup', 'ChartCategoryGroup', 'setup_utilities']

logger = logging.getLogger(__name__)


async def setup_utilities(bot: commands.Bot) -> tuple[int, int, list[str]]:
    """
    Setup function for utilities commands.

    Args:
        bot: The Discord bot instance

    Returns:
        Tuple of (successful_count, failed_count, failed_module_names)
    """
    successful = 0
    failed = 0
    failed_modules = []

    # Cogs that need bot instance
    cog_classes = [
        WeatherCommands,
        ChartCommands,
    ]

    for cog_class in cog_classes:
        try:
            await bot.add_cog(cog_class(bot))
            logger.info(f"Loaded cog: {cog_class.__name__}")
            successful += 1
        except Exception as e:
            logger.error(f"Failed to load cog {cog_class.__name__}: {e}", exc_info=True)
            failed += 1
            failed_modules.append(cog_class.__name__)

    # Command groups (added directly to command tree)
    command_groups = [
        ChartManageGroup,
        ChartCategoryGroup,
    ]

    for group_class in command_groups:
        try:
            bot.tree.add_command(group_class())
            logger.info(f"Loaded command group: {group_class.__name__}")
            successful += 1
        except Exception as e:
            logger.error(f"Failed to load command group {group_class.__name__}: {e}", exc_info=True)
            failed += 1
            failed_modules.append(group_class.__name__)

    return successful, failed, failed_modules
