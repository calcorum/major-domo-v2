"""
Team information commands for Discord Bot v2.0
"""
import logging
from typing import Optional

import discord
from discord.ext import commands

from services import team_service
from models.team import Team
from constants import SBA_CURRENT_SEASON
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from exceptions import BotException


class TeamInfoCommands(commands.Cog):
    """Team information command handlers."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.TeamInfoCommands')
        self.logger.info("TeamInfoCommands cog initialized")
    
    @discord.app_commands.command(name="team", description="Display team information")
    @discord.app_commands.describe(
        abbrev="Team abbreviation (e.g., NYY, BOS, LAD)",
        season="Season to show team info for (defaults to current season)"
    )
    @logged_command("/team")
    async def team_info(self, interaction: discord.Interaction, abbrev: str, season: Optional[int] = None):
        """Display comprehensive team information."""
        await interaction.response.defer()
        
        # Use current season if not specified
        season = season or SBA_CURRENT_SEASON
        
        # Get team by abbreviation
        team = await team_service.get_team_by_abbrev(abbrev, season)
        
        if team is None:
            self.logger.info("Team not found", team_abbrev=abbrev, season=season)
            embed = discord.Embed(
                title="Team Not Found",
                description=f"No team found with abbreviation '{abbrev.upper()}' in season {season}",
                color=0xff6b6b
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Get additional team data
        standings_data = await team_service.get_team_standings_position(team.id, season)
        
        # Create main embed
        embed = await self._create_team_embed(team, standings_data)
        
        self.logger.info("Team info displayed successfully", 
                   team_id=team.id,
                   team_name=team.lname,
                   season=season)
        
        await interaction.followup.send(embed=embed)
    
    @discord.app_commands.command(name="teams", description="List all teams in a season")
    @discord.app_commands.describe(
        season="Season to list teams for (defaults to current season)"
    )
    @logged_command("/teams")
    async def list_teams(self, interaction: discord.Interaction, season: Optional[int] = None):
        """List all teams in a season."""
        await interaction.response.defer()
        
        season = season or SBA_CURRENT_SEASON
        
        teams = await team_service.get_teams_by_season(season)
        
        if not teams:
            embed = discord.Embed(
                title="No Teams Found",
                description=f"No teams found for season {season}",
                color=0xff6b6b
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Sort teams by abbreviation
        teams.sort(key=lambda t: t.abbrev)
        
        # Create embed with team list
        embed = discord.Embed(
            title=f"SBA Teams - Season {season}",
            color=0xa6ce39
        )
        
        # Group teams by division if available
        if any(team.division_id for team in teams):
            divisions = {}
            for team in teams:
                div_id = team.division_id or 0
                if div_id not in divisions:
                    divisions[div_id] = []
                divisions[div_id].append(team)
            
            for div_id, div_teams in sorted(divisions.items()):
                div_name = f"Division {div_id}" if div_id > 0 else "Unassigned"
                team_list = "\n".join([f"**{team.abbrev}** - {team.lname}" for team in div_teams])
                embed.add_field(name=div_name, value=team_list, inline=True)
        else:
            # Simple list if no divisions
            team_list = "\n".join([f"**{team.abbrev}** - {team.lname}" for team in teams])
            embed.add_field(name="Teams", value=team_list, inline=False)
        
        embed.set_footer(text=f"Total: {len(teams)} teams")
        
        self.logger.info("Teams list displayed successfully", 
                   season=season, 
                   team_count=len(teams))
        
        await interaction.followup.send(embed=embed)
    
    async def _create_team_embed(self, team: Team, standings_data: Optional[dict] = None) -> discord.Embed:
        """Create a rich embed for team information."""
        embed = discord.Embed(
            title=f"{team.abbrev} - {team.lname}",
            description=f"Season {team.season} Team Information",
            color=int(team.color, 16) if team.color else 0xa6ce39
        )
        
        # Basic team info
        embed.add_field(name="Short Name", value=team.sname, inline=True)
        embed.add_field(name="Abbreviation", value=team.abbrev, inline=True)
        embed.add_field(name="Season", value=str(team.season), inline=True)
        
        # Stadium info
        if team.stadium:
            embed.add_field(name="Stadium", value=team.stadium, inline=True)
        
        # Division info
        if team.division_id:
            embed.add_field(name="Division", value=f"Division {team.division_id}", inline=True)
        
        # Standings info if available
        if standings_data:
            try:
                wins = standings_data.get('wins', 'N/A')
                losses = standings_data.get('losses', 'N/A')
                pct = standings_data.get('pct', 'N/A')
                gb = standings_data.get('gb', 'N/A')
                
                standings_text = f"**Record:** {wins}-{losses}"
                if pct != 'N/A':
                    standings_text += f" ({pct:.3f})"
                if gb != 'N/A' and gb != 0:
                    standings_text += f"\n**GB:** {gb}"
                
                embed.add_field(name="Standings", value=standings_text, inline=False)
            except (KeyError, TypeError):
                # Skip standings if data is malformed
                pass
        
        # Thumbnail if available
        if team.thumbnail:
            embed.set_thumbnail(url=team.thumbnail)
        
        return embed