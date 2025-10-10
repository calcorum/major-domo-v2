"""
Help Commands package for Discord Bot v2.0

Modern slash command system for admin-created help topics.
"""
import logging
from typing import List, Tuple, Type

from discord.ext import commands

from .main import HelpCommands

logger = logging.getLogger(f'{__name__}.setup_help_commands')


async def setup_help_commands(bot: commands.Bot) -> Tuple[int, int, List[str]]:
    """
    Set up help commands command modules.

    Returns:
        Tuple of (successful_loads, failed_loads, failed_modules)
    """
    help_command_cogs: List[Tuple[str, Type[commands.Cog]]] = [
        ("HelpCommands", HelpCommands),
    ]

    successful = 0
    failed = 0
    failed_modules = []

    for cog_name, cog_class in help_command_cogs:
        try:
            await bot.add_cog(cog_class(bot))
            logger.info(f"✅ Loaded help commands module: {cog_name}")
            successful += 1
        except Exception as e:
            logger.error(f"❌ Failed to load help commands module {cog_name}: {e}")
            failed += 1
            failed_modules.append(cog_name)

    # Log summary
    if failed == 0:
        logger.info(f"🎉 All {successful} help commands modules loaded successfully")
    else:
        logger.warning(f"⚠️  Help commands loaded with issues: {successful} successful, {failed} failed")
        if failed_modules:
            logger.warning(f"Failed modules: {', '.join(failed_modules)}")

    return successful, failed, failed_modules
