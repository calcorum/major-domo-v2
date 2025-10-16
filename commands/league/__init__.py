"""
League command package for Discord Bot v2.0

Provides league-wide slash commands for standings and current state.
"""
import logging
from typing import List, Tuple, Type

import discord
from discord.ext import commands

from .info import LeagueInfoCommands
from .standings import StandingsCommands
from .schedule import ScheduleCommands
from .submit_scorecard import SubmitScorecardCommands

logger = logging.getLogger(f'{__name__}.setup_league')


async def setup_league(bot: commands.Bot) -> Tuple[int, int, List[str]]:
    """
    Set up league command modules.
    
    Returns:
        Tuple of (successful_loads, failed_loads, failed_modules)
    """
    league_cogs: List[Tuple[str, Type[commands.Cog]]] = [
        ("LeagueInfoCommands", LeagueInfoCommands),
        ("StandingsCommands", StandingsCommands),
        ("ScheduleCommands", ScheduleCommands),
        ("SubmitScorecardCommands", SubmitScorecardCommands),
    ]
    
    successful = 0
    failed = 0
    failed_modules = []
    
    for cog_name, cog_class in league_cogs:
        try:
            await bot.add_cog(cog_class(bot))
            logger.info(f"✅ Loaded league command module: {cog_name}")
            successful += 1
        except Exception as e:
            logger.error(f"❌ Failed to load league command module {cog_name}: {e}")
            failed += 1
            failed_modules.append(cog_name)
    
    # Log summary
    if failed == 0:
        logger.info(f"🎉 All {successful} league command modules loaded successfully")
    else:
        logger.warning(f"⚠️  League commands loaded with issues: {successful} successful, {failed} failed")
        if failed_modules:
            logger.warning(f"Failed modules: {', '.join(failed_modules)}")
    
    return successful, failed, failed_modules