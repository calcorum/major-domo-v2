"""
Admin command package for Discord Bot v2.0

Contains administrative commands for league management.
"""
import logging
from typing import List, Tuple, Type

import discord
from discord.ext import commands

from .management import AdminCommands
from .users import UserManagementCommands
from .league_management import LeagueManagementCommands

logger = logging.getLogger(f'{__name__}.setup_admin')


async def setup_admin(bot: commands.Bot) -> Tuple[int, int, List[str]]:
    """
    Set up admin command modules.
    
    Returns:
        Tuple of (successful_loads, failed_loads, failed_modules)
    """
    admin_cogs: List[Tuple[str, Type[commands.Cog]]] = [
        ("AdminCommands", AdminCommands),
        ("UserManagementCommands", UserManagementCommands),
        ("LeagueManagementCommands", LeagueManagementCommands),
    ]
    
    successful = 0
    failed = 0
    failed_modules = []
    
    for cog_name, cog_class in admin_cogs:
        try:
            await bot.add_cog(cog_class(bot))
            logger.info(f"✅ Loaded admin command module: {cog_name}")
            successful += 1
        except Exception as e:
            logger.error(f"❌ Failed to load admin command module {cog_name}: {e}")
            failed += 1
            failed_modules.append(cog_name)
    
    # Log summary
    if failed == 0:
        logger.info(f"🎉 All {successful} admin command modules loaded successfully")
    else:
        logger.warning(f"⚠️  Admin commands loaded with issues: {successful} successful, {failed} failed")
        if failed_modules:
            logger.warning(f"Failed modules: {', '.join(failed_modules)}")
    
    return successful, failed, failed_modules