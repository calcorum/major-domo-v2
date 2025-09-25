"""
Voice Commands Package

This package contains voice channel management commands for gameplay.
"""
import logging
from discord.ext import commands

from .channels import VoiceChannelCommands

logger = logging.getLogger(__name__)


async def setup_voice(bot: commands.Bot):
    """
    Setup all voice command modules.

    Returns:
        tuple: (successful_count, failed_count, failed_modules)
    """
    # Define all voice command cogs to load
    voice_cogs = [
        ("VoiceChannelCommands", VoiceChannelCommands),
    ]

    successful = 0
    failed = 0
    failed_modules = []

    for cog_name, cog_class in voice_cogs:
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
        logger.info(f"🎉 All {successful} voice command modules loaded successfully")
    else:
        logger.warning(f"⚠️  Voice commands loaded with issues: {successful} successful, {failed} failed")

    return successful, failed, failed_modules


# Export the setup function for easy importing
__all__ = ['setup_voice', 'VoiceChannelCommands']