"""
Spoiler Commands Package

This package contains the spoiler listener that watches for Discord spoiler tags
and posts "Deez Watch!" alerts.
"""
import logging
from discord.ext import commands

from .listener import SpoilerListener

logger = logging.getLogger(__name__)


async def setup_spoiler(bot: commands.Bot):
    """
    Setup spoiler listener module.

    Returns:
        tuple: (successful_count, failed_count, failed_modules)
    """
    # Define spoiler cogs to load
    spoiler_cogs = [
        ("SpoilerListener", SpoilerListener),
    ]

    successful = 0
    failed = 0
    failed_modules = []

    for cog_name, cog_class in spoiler_cogs:
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
        logger.info(f"🎉 All {successful} spoiler module(s) loaded successfully")
    else:
        logger.warning(
            f"⚠️  Spoiler modules loaded with issues: "
            f"{successful} successful, {failed} failed"
        )

    return successful, failed, failed_modules


# Export the setup function for easy importing
__all__ = ['setup_spoiler', 'SpoilerListener']
