"""
Draft Commands Package for Discord Bot v2.0

Contains slash commands for draft operations:
- /draft - Make a draft pick with autocomplete
- /draft-status - View current draft state
- /draft-on-clock - Detailed on the clock information
- /draft-admin - Admin controls for draft management
- /draft-list - View auto-draft queue
- /draft-list-add - Add player to queue
- /draft-list-remove - Remove player from queue
- /draft-list-clear - Clear entire queue
- /draft-board - View draft picks by round
"""
import logging
from discord.ext import commands

from .picks import DraftPicksCog
from .status import DraftStatusCommands
from .list import DraftListCommands
from .board import DraftBoardCommands
from .admin import DraftAdminGroup

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
        ("DraftStatusCommands", DraftStatusCommands),
        ("DraftListCommands", DraftListCommands),
        ("DraftBoardCommands", DraftBoardCommands),
    ]

    successful = 0
    failed = 0
    failed_modules = []

    # Load regular cogs
    for cog_name, cog_class in draft_cogs:
        try:
            await bot.add_cog(cog_class(bot))
            logger.info(f"✅ Loaded {cog_name}")
            successful += 1
        except Exception as e:
            logger.error(f"❌ Failed to load {cog_name}: {e}", exc_info=True)
            failed += 1
            failed_modules.append(cog_name)

    # Load draft admin group (app_commands.Group pattern)
    try:
        bot.tree.add_command(DraftAdminGroup(bot))
        logger.info("✅ Loaded DraftAdminGroup")
        successful += 1
    except Exception as e:
        logger.error(f"❌ Failed to load DraftAdminGroup: {e}", exc_info=True)
        failed += 1
        failed_modules.append("DraftAdminGroup")

    # Log summary
    if failed == 0:
        logger.info(f"🎉 All {successful} draft command modules loaded successfully")
    else:
        logger.warning(f"⚠️  Draft commands loaded with issues: {successful} successful, {failed} failed")

    return successful, failed, failed_modules


# Export the setup function for easy importing
__all__ = [
    'setup_draft',
    'DraftPicksCog',
    'DraftStatusCommands',
    'DraftListCommands',
    'DraftBoardCommands',
    'DraftAdminGroup'
]