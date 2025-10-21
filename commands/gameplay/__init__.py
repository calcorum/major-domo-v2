"""
Gameplay Commands Package

This package contains commands for live game tracking and scorecard management.
"""
import logging
from discord.ext import commands

from .scorebug import ScorebugCommands

logger = logging.getLogger(__name__)


async def setup_gameplay(bot: commands.Bot):
    """
    Setup all gameplay command modules.

    Returns:
        tuple: (successful_count, failed_count, failed_modules)
    """
    # Define all gameplay command cogs to load
    gameplay_cogs = [
        ("ScorebugCommands", ScorebugCommands),
    ]

    successful = 0
    failed = 0
    failed_modules = []

    for cog_name, cog_class in gameplay_cogs:
        try:
            await bot.add_cog(cog_class(bot))
            logger.info(f"✅ Loaded {cog_name}")
            successful += 1
        except Exception as e:
            logger.error(f"❌ Failed to load {cog_name}: {e}", exc_info=True)
            failed += 1
            failed_modules.append(cog_name)

    # Log summary
    if failed == 0:
        logger.info(f"🎉 All {successful} gameplay command modules loaded successfully")
    else:
        logger.warning(f"⚠️  Gameplay commands loaded with issues: {successful} successful, {failed} failed")

    return successful, failed, failed_modules


# Export the setup function for easy importing
__all__ = ['setup_gameplay', 'ScorebugCommands']
