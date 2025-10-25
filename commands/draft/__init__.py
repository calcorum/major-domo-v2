"""
Draft Commands Package for Discord Bot v2.0

Contains slash commands for draft operations:
- /draft - Make a draft pick with autocomplete
- /draft-status - View current draft state (TODO)
- /draft-admin - Admin controls for draft management (TODO)
"""
import logging
from discord.ext import commands

from .picks import DraftPicksCog

logger = logging.getLogger(__name__)


async def setup_draft(bot: commands.Bot):
    """
    Setup all draft command modules.

    Returns:
        tuple: (successful_count, failed_count, failed_modules)
    """
    # Define all draft command cogs to load
    draft_cogs = [
        ("DraftPicksCog", DraftPicksCog),
    ]

    successful = 0
    failed = 0
    failed_modules = []

    for cog_name, cog_class in draft_cogs:
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
        logger.info(f"🎉 All {successful} draft command modules loaded successfully")
    else:
        logger.warning(f"⚠️  Draft commands loaded with issues: {successful} successful, {failed} failed")

    return successful, failed, failed_modules


# Export the setup function for easy importing
__all__ = ['setup_draft', 'DraftPicksCog']