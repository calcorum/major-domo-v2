"""
League information commands for Discord Bot v2.0
"""
import logging
from typing import Optional

import discord
from discord.ext import commands

from services import league_service
from constants import SBA_CURRENT_SEASON
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from exceptions import BotException

class LeagueInfoCommands(commands.Cog):
    """League information command handlers."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.LeagueInfoCommands')
        self.logger.info("LeagueInfoCommands cog initialized")
    
    @discord.app_commands.command(name="league", description="Display current league status and information")
    @logged_command("/league")
    async def league_info(self, interaction: discord.Interaction):
        """Display current league state and information."""
        await interaction.response.defer()
        
        # Get current league state
        current_state = await league_service.get_current_state()
        
        if current_state is None:
            embed = discord.Embed(
                title="League Information Unavailable",
                description="❌ Unable to retrieve current league information",
                color=0xff6b6b
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Create league info embed
        embed = discord.Embed(
            title="🏆 SBA League Status",
            description="Current league information and status",
            color=0xa6ce39
        )
        
        # Basic league info
        embed.add_field(name="Season", value=str(current_state.season), inline=True)
        embed.add_field(name="Week", value=str(current_state.week), inline=True)
        
        # League status
        if current_state.freeze:
            embed.add_field(name="Status", value="🔒 Frozen", inline=True)
        else:
            embed.add_field(name="Status", value="🟢 Active", inline=True)
        
        # Season phase
        if current_state.is_offseason:
            phase = "🏖️ Offseason"
        elif current_state.is_playoffs:
            phase = "🏆 Playoffs"
        else:
            phase = "⚾ Regular Season"
        
        embed.add_field(name="Phase", value=phase, inline=True)
        
        # Trading info
        if current_state.can_trade_picks:
            embed.add_field(name="Draft Pick Trading", value="✅ Open", inline=True)
        else:
            embed.add_field(name="Draft Pick Trading", value="❌ Closed", inline=True)
        
        # Trade deadline info
        embed.add_field(name="Trade Deadline", value=f"Week {current_state.trade_deadline}", inline=True)
        
        # Additional info
        embed.add_field(
            name="Betting Week", 
            value=current_state.bet_week, 
            inline=True
        )
        
        if current_state.playoffs_begin <= 18:
            embed.add_field(
                name="Playoffs Begin", 
                value=f"Week {current_state.playoffs_begin}", 
                inline=True
            )
        
        self.logger.info("League info displayed successfully", 
                   season=current_state.season,
                   week=current_state.week,
                   phase=phase)
        
        await interaction.followup.send(embed=embed)