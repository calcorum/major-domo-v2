"""
League information commands for Discord Bot v2.0
"""
import logging
from typing import Optional

import discord
from discord.ext import commands

from services import league_service
from config import get_config
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from exceptions import BotException
from utils.permissions import requires_team
from views.embeds import EmbedTemplate

class LeagueInfoCommands(commands.Cog):
    """League information command handlers."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.LeagueInfoCommands')
        self.logger.info("LeagueInfoCommands cog initialized")
    
    @discord.app_commands.command(name="league-metadata", description="Display current league metadata")
    @requires_team()
    @logged_command("/league-metadata")
    async def league_info(self, interaction: discord.Interaction):
        """Display current league state and information."""
        await interaction.response.defer()
        
        # Get current league state
        current_state = await league_service.get_current_state()
        
        if current_state is None:
            embed = EmbedTemplate.create_base_embed(
                title="League Information Unavailable",
                description="❌ Unable to retrieve current league information"
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Create league info embed
        embed = EmbedTemplate.create_base_embed(
            title="🏆 SBA League Metadata",
            description="Current league metadata"
        )
        
        # Basic league info
        embed.add_field(name="Season", value=str(current_state.season), inline=True)
        embed.add_field(name="Week", value=str(current_state.week), inline=True)
        
        # Season phase - determine phase and add field first
        if current_state.is_offseason:
            embed.add_field(name="Timing", value="🏔️ Offseason", inline=True)
            # Add offseason-specific fields here if needed
            
        elif current_state.is_playoffs:
            embed.add_field(name="Phase", value="🏆 Playoffs", inline=True)
            # Add playoff-specific fields here if needed
            
        else:
            embed.add_field(name="Phase", value="⚾ Regular Season", inline=True)
        
            # League status
            if current_state.freeze:
                embed.add_field(name="Transactions", value="🔒 Frozen", inline=True)
            else:
                embed.add_field(name="Transactions", value="🟢 Active", inline=True)
        
            # Trade deadline info
            embed.add_field(name="Trade Deadline", value=f"Week {current_state.trade_deadline}", inline=True)
        
            # Playoff timing
            embed.add_field(
                name="Playoffs Begin", 
                value=f"Week {current_state.playoffs_begin}", 
                inline=True
            )
    
        if current_state.ever_trade_picks:
            if current_state.can_trade_picks:
                embed.add_field(name="Draft Pick Trading", value="✅ Open", inline=True)
            else:
                embed.add_field(name="Draft Pick Trading", value="❌ Closed", inline=True)

        # Additional info
        embed.add_field(
            name="Sheets Card ID", 
            value=current_state.bet_week, 
            inline=True
        )
        
        await interaction.followup.send(embed=embed)