"""
Dice Commands Package

This package contains all dice rolling Discord commands for gameplay.
"""
import logging
from discord.ext import commands

from .rolls import DiceRollCommands

logger = logging.getLogger(__name__)


async def setup_dice(bot: commands.Bot):
    """
    Setup all dice command modules.

    Returns:
        tuple: (successful_count, failed_count, failed_modules)
    """
    # Define all dice command cogs to load
    dice_cogs = [
        ("DiceRollCommands", DiceRollCommands),
    ]

    successful = 0
    failed = 0
    failed_modules = []

    for cog_name, cog_class in dice_cogs:
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
        logger.info(f"🎉 All {successful} dice command modules loaded successfully")
    else:
        logger.warning(f"⚠️  Dice commands loaded with issues: {successful} successful, {failed} failed")

    return successful, failed, failed_modules


# Export the setup function for easy importing
__all__ = ['setup_dice', 'DiceRollCommands']