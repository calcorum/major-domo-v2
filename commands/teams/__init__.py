"""
Team command package for Discord Bot v2.0

Provides team-related slash commands for the SBA league.
"""
import logging
from typing import List, Tuple, Type

import discord
from discord.ext import commands

from .info import TeamInfoCommands
from .roster import TeamRosterCommands
from .branding import BrandingCommands

logger = logging.getLogger(f'{__name__}.setup_teams')


async def setup_teams(bot: commands.Bot) -> Tuple[int, int, List[str]]:
    """
    Set up team command modules.
    
    Returns:
        Tuple of (successful_loads, failed_loads, failed_modules)
    """
    team_cogs: List[Tuple[str, Type[commands.Cog]]] = [
        ("TeamInfoCommands", TeamInfoCommands),
        ("TeamRosterCommands", TeamRosterCommands),
        ("BrandingCommands", BrandingCommands),
    ]
    
    successful = 0
    failed = 0
    failed_modules = []
    
    for cog_name, cog_class in team_cogs:
        try:
            await bot.add_cog(cog_class(bot))
            logger.info(f"✅ Loaded team command module: {cog_name}")
            successful += 1
        except Exception as e:
            logger.error(f"❌ Failed to load team command module {cog_name}: {e}")
            failed += 1
            failed_modules.append(cog_name)
    
    # Log summary
    if failed == 0:
        logger.info(f"🎉 All {successful} team command modules loaded successfully")
    else:
        logger.warning(f"⚠️  Team commands loaded with issues: {successful} successful, {failed} failed")
        if failed_modules:
            logger.warning(f"Failed modules: {', '.join(failed_modules)}")
    
    return successful, failed, failed_modules