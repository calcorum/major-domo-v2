"""
Transaction command package for Discord Bot v2.0

Contains transaction management commands for league operations.
"""
import logging
from typing import List, Tuple, Type

import discord
from discord.ext import commands

from .management import TransactionCommands
from .dropadd import DropAddCommands
from .trade import TradeCommands

logger = logging.getLogger(f'{__name__}.setup_transactions')


async def setup_transactions(bot: commands.Bot) -> Tuple[int, int, List[str]]:
    """
    Set up transaction command modules.
    
    Returns:
        Tuple of (successful_loads, failed_loads, failed_modules)
    """
    transaction_cogs: List[Tuple[str, Type[commands.Cog]]] = [
        ("TransactionCommands", TransactionCommands),
        ("DropAddCommands", DropAddCommands),
        ("TradeCommands", TradeCommands),
    ]
    
    successful = 0
    failed = 0
    failed_modules = []
    
    for cog_name, cog_class in transaction_cogs:
        try:
            await bot.add_cog(cog_class(bot))
            logger.info(f"✅ Loaded transaction command module: {cog_name}")
            successful += 1
        except Exception as e:
            logger.error(f"❌ Failed to load transaction command module {cog_name}: {e}")
            failed += 1
            failed_modules.append(cog_name)
    
    # Log summary
    if failed == 0:
        logger.info(f"🎉 All {successful} transaction command modules loaded successfully")
    else:
        logger.warning(f"⚠️  Transaction commands loaded with issues: {successful} successful, {failed} failed")
        if failed_modules:
            logger.warning(f"Failed modules: {', '.join(failed_modules)}")
    
    return successful, failed, failed_modules