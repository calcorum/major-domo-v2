"""
Soak Easter Egg Package

Monitors for "soak" mentions and responds with disappointment GIFs.
The more recently it was mentioned, the more disappointed the response.
"""
import logging
from discord.ext import commands

from .listener import SoakListener
from .info import SoakInfoCommands

logger = logging.getLogger(__name__)


async def setup_soak(bot: commands.Bot):
    """
    Setup all soak command modules.

    Returns:
        tuple: (successful_count, failed_count, failed_modules)
    """
    # Define all soak cogs to load
    soak_cogs = [
        ("SoakListener", SoakListener),
        ("SoakInfoCommands", SoakInfoCommands),
    ]

    successful = 0
    failed = 0
    failed_modules = []

    for cog_name, cog_class in soak_cogs:
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
        logger.info(f"🎉 All {successful} soak modules loaded successfully")
    else:
        logger.warning(f"⚠️  Soak commands loaded with issues: {successful} successful, {failed} failed")

    return successful, failed, failed_modules


# Export the setup function and classes for easy importing
__all__ = ['setup_soak', 'SoakListener', 'SoakInfoCommands']
