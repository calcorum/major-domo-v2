"""
Team roster commands for Discord Bot v2.0
"""
import logging
from typing import Optional, Dict, Any, List

import discord
from discord.ext import commands

from services import team_service, player_service
from models.team import Team
from constants import SBA_CURRENT_SEASON
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from exceptions import BotException


class TeamRosterCommands(commands.Cog):
    """Team roster command handlers."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.TeamRosterCommands')
        self.logger.info("TeamRosterCommands cog initialized")
    
    @discord.app_commands.command(name="roster", description="Display team roster")
    @discord.app_commands.describe(
        abbrev="Team abbreviation (e.g., NYY, BOS, LAD)",
        roster_type="Roster week: current or next (defaults to current)"
    )
    @discord.app_commands.choices(roster_type=[
        discord.app_commands.Choice(name="Current Week", value="current"),
        discord.app_commands.Choice(name="Next Week", value="next")
    ])
    @logged_command("/roster")
    async def team_roster(self, interaction: discord.Interaction, abbrev: str, 
                         roster_type: str = "current"):
        """Display team roster with position breakdowns."""
        await interaction.response.defer()
        
        # Get team by abbreviation
        team = await team_service.get_team_by_abbrev(abbrev, SBA_CURRENT_SEASON)
        
        if team is None:
            self.logger.info("Team not found", team_abbrev=abbrev)
            embed = discord.Embed(
                title="Team Not Found",
                description=f"No team found with abbreviation '{abbrev.upper()}'",
                color=0xff6b6b
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Get roster data
        roster_data = await team_service.get_team_roster(team.id, roster_type)
        
        if not roster_data:
            embed = discord.Embed(
                title="Roster Not Available",
                description=f"No {roster_type} roster data available for {team.abbrev}",
                color=0xff6b6b
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Create roster embeds
        embeds = await self._create_roster_embeds(team, roster_data, roster_type)
        
        self.logger.info("Team roster displayed successfully", 
                   team_id=team.id,
                   team_abbrev=team.abbrev,
                   roster_type=roster_type)
        
        # Send first embed and follow up with others if needed
        await interaction.followup.send(embed=embeds[0])
        for embed in embeds[1:]:
            await interaction.followup.send(embed=embed)
    
    async def _create_roster_embeds(self, team: Team, roster_data: Dict[str, Any], 
                                   roster_type: str) -> List[discord.Embed]:
        """Create embeds for team roster data."""
        embeds = []
        
        # Main roster embed
        embed = discord.Embed(
            title=f"{team.abbrev} - {roster_type.title()} Roster",
            description=f"{team.lname} roster breakdown",
            color=int(team.color, 16) if team.color else 0xa6ce39
        )
        
        # Position counts for active roster
        if 'active' in roster_data:
            active_roster = roster_data['active']
            
            # Batting positions
            batting_positions = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH']
            batting_counts = []
            for pos in batting_positions:
                count = active_roster.get(pos, 0)
                batting_counts.append(f"**{pos}:** {count}")
            
            # Pitching positions  
            pitching_positions = ['SP', 'RP', 'CP']
            pitching_counts = []
            for pos in pitching_positions:
                count = active_roster.get(pos, 0)
                pitching_counts.append(f"**{pos}:** {count}")
            
            # Add position count fields
            embed.add_field(
                name="Batting Positions", 
                value="\n".join(batting_counts), 
                inline=True
            )
            embed.add_field(
                name="Pitching Positions", 
                value="\n".join(pitching_counts), 
                inline=True
            )
            
            # Total WAR
            total_war = active_roster.get('WARa', 0)
            embed.add_field(
                name="Total WARa", 
                value=f"{total_war:.1f}" if isinstance(total_war, (int, float)) else str(total_war), 
                inline=True
            )
        
        # Add injury list summaries
        if 'shortil' in roster_data and roster_data['shortil']:
            short_il_count = len(roster_data['shortil'].get('players', []))
            embed.add_field(name="Short IL", value=f"{short_il_count} players", inline=True)
        
        if 'longil' in roster_data and roster_data['longil']:
            long_il_count = len(roster_data['longil'].get('players', []))
            embed.add_field(name="Long IL", value=f"{long_il_count} players", inline=True)
        
        embeds.append(embed)
        
        # Create detailed player list embeds if there are players
        for roster_name, roster_info in roster_data.items():
            if roster_name in ['active', 'shortil', 'longil'] and 'players' in roster_info:
                players = roster_info['players']
                if players:
                    player_embed = self._create_player_list_embed(
                        team, roster_name, players
                    )
                    embeds.append(player_embed)
        
        return embeds
    
    def _create_player_list_embed(self, team: Team, roster_name: str, 
                                 players: List[Dict[str, Any]]) -> discord.Embed:
        """Create an embed with detailed player list."""
        roster_titles = {
            'active': 'Active Roster',
            'shortil': 'Short IL',
            'longil': 'Long IL'
        }
        
        embed = discord.Embed(
            title=f"{team.abbrev} - {roster_titles.get(roster_name, roster_name.title())}",
            color=int(team.color, 16) if team.color else 0xa6ce39
        )
        
        # Group players by position for better organization
        batters = []
        pitchers = []
        
        for player in players:
            name = player.get('name', 'Unknown')
            positions = player.get('positions', [])
            war = player.get('WARa', 0)
            
            # Format WAR display
            war_str = f"{war:.1f}" if isinstance(war, (int, float)) else str(war)
            
            # Determine if pitcher or batter
            is_pitcher = any(pos in ['SP', 'RP', 'CP'] for pos in positions)
            
            player_line = f"**{name}** ({'/'.join(positions)}) - WAR: {war_str}"
            
            if is_pitcher:
                pitchers.append(player_line)
            else:
                batters.append(player_line)
        
        # Add player lists to embed
        if batters:
            # Split long lists into multiple fields if needed
            batter_chunks = self._chunk_list(batters, 10)
            for i, chunk in enumerate(batter_chunks):
                field_name = "Batters" if i == 0 else f"Batters (cont.)"
                embed.add_field(name=field_name, value="\n".join(chunk), inline=False)
        
        if pitchers:
            pitcher_chunks = self._chunk_list(pitchers, 10)
            for i, chunk in enumerate(pitcher_chunks):
                field_name = "Pitchers" if i == 0 else f"Pitchers (cont.)"
                embed.add_field(name=field_name, value="\n".join(chunk), inline=False)
        
        embed.set_footer(text=f"Total players: {len(players)}")
        
        return embed
    
    def _chunk_list(self, lst: List[str], chunk_size: int) -> List[List[str]]:
        """Split a list into chunks of specified size."""
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]