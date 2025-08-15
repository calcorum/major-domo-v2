"""
Player Commands Package

This package contains all player-related Discord commands organized into focused modules:
- info.py: Player information and statistics display
"""
import logging
from discord.ext import commands

from .info import PlayerInfoCommands

logger = logging.getLogger(__name__)


async def setup_players(bot: commands.Bot):
    """
    Setup all player command modules.
    
    Args:
        bot: The Discord bot instance
        
    Returns:
        tuple: (successful_count, failed_count, failed_modules)
    """
    # Define all player command cogs to load
    player_cogs = [
        ("PlayerInfoCommands", PlayerInfoCommands),
        # Future player command modules:
        # ("PlayerSearchCommands", PlayerSearchCommands),
        # ("PlayerStatsCommands", PlayerStatsCommands), 
        # ("PlayerCompareCommands", PlayerCompareCommands),
    ]
    
    successful = 0
    failed = 0
    failed_modules = []
    
    for cog_name, cog_class in player_cogs:
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
        logger.info(f"🎉 All {successful} player command modules loaded successfully")
    else:
        logger.warning(f"⚠️  Player commands loaded with issues: {successful} successful, {failed} failed")
        if failed_modules:
            logger.warning(f"Failed modules: {', '.join(failed_modules)}")
    
    return successful, failed, failed_modules


# Export the setup function for easy importing
__all__ = ['setup_players', 'PlayerInfoCommands']