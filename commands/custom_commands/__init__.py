"""
Custom Commands package for Discord Bot v2.0

Modern slash command system for user-created custom commands.
"""
import logging
from typing import List, Tuple, Type

from discord.ext import commands

from .main import CustomCommandsCommands

logger = logging.getLogger(f'{__name__}.setup_custom_commands')


async def setup_custom_commands(bot: commands.Bot) -> Tuple[int, int, List[str]]:
    """
    Set up custom commands command modules.
    
    Returns:
        Tuple of (successful_loads, failed_loads, failed_modules)
    """
    custom_command_cogs: List[Tuple[str, Type[commands.Cog]]] = [
        ("CustomCommandsCommands", CustomCommandsCommands),
    ]
    
    successful = 0
    failed = 0
    failed_modules = []
    
    for cog_name, cog_class in custom_command_cogs:
        try:
            await bot.add_cog(cog_class(bot))
            logger.info(f"✅ Loaded custom commands module: {cog_name}")
            successful += 1
        except Exception as e:
            logger.error(f"❌ Failed to load custom commands module {cog_name}: {e}")
            failed += 1
            failed_modules.append(cog_name)
    
    # Log summary
    if failed == 0:
        logger.info(f"🎉 All {successful} custom commands modules loaded successfully")
    else:
        logger.warning(f"⚠️  Custom commands loaded with issues: {successful} successful, {failed} failed")
        if failed_modules:
            logger.warning(f"Failed modules: {', '.join(failed_modules)}")
    
    return successful, failed, failed_modules