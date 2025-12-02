"""
Team roster commands for Discord Bot v2.0
"""
import logging
from typing import Optional, Dict, Any, List

import discord
from discord.ext import commands

from config import get_config
from models.player import Player
from services import team_service, player_service
from models.team import Team
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from exceptions import BotException
from utils.permissions import requires_team
from views.embeds import EmbedTemplate, EmbedColors


class TeamRosterCommands(commands.Cog):
    """Team roster command handlers."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.TeamRosterCommands')
        self.logger.info("TeamRosterCommands cog initialized")
    
    @discord.app_commands.command(name="roster", description="Display team roster")
    @discord.app_commands.describe(
        abbrev="Team abbreviation (e.g., BSG, DEN, WV, etc.)",
        roster_type="Roster week: current or next (defaults to current)"
    )
    @discord.app_commands.choices(roster_type=[
        discord.app_commands.Choice(name="Current Week", value="current"),
        discord.app_commands.Choice(name="Next Week", value="next")
    ])
    @requires_team()
    @logged_command("/roster")
    async def team_roster(self, interaction: discord.Interaction, abbrev: str, 
                         roster_type: str = "current"):
        """Display team roster with position breakdowns."""
        await interaction.response.defer()
        
        # Get team by abbreviation
        team = await team_service.get_team_by_abbrev(abbrev, get_config().sba_season)
        
        if team is None:
            self.logger.info("Team not found", team_abbrev=abbrev)
            embed = EmbedTemplate.error(
                title="Team Not Found",
                description=f"No team found with abbreviation '{abbrev.upper()}'"
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Get roster data
        roster_data = await team_service.get_team_roster(team.id, roster_type)
        
        if not roster_data:
            embed = EmbedTemplate.error(
                title="Roster Not Available",
                description=f"No {roster_type} roster data available for {team.abbrev}"
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Create roster embeds
        embeds = await self._create_roster_embeds(team, roster_data, roster_type)
        
        # Send first embed and follow up with others if needed
        await interaction.followup.send(embed=embeds[0])
        for embed in embeds[1:]:
            await interaction.followup.send(embed=embed)
    
    async def _create_roster_embeds(self, team: Team, roster_data: Dict[str, Any], 
                                   roster_type: str) -> List[discord.Embed]:
        """Create embeds for team roster data."""
        embeds = []
        
        # Main roster embed
        embed = EmbedTemplate.create_base_embed(
            title=f"{team.abbrev} - {roster_type.title()} Week",
            description=f"{team.lname} Roster Breakdown",
            color=int(team.color, 16) if team.color else EmbedColors.PRIMARY
        )
        
        # Position counts for active roster
        for key in ['active', 'longil', 'shortil']:
            if key in roster_data:     
                this_roster = roster_data[key]

                players = this_roster.get('players')
                if len(players) > 0:
                    this_team = players[0].get("team", {"id": "Unknown", "sname": "Unknown"})

                    embed.add_field(
                        name='Team (ID)',
                        value=f'{this_team.get("sname")} ({this_team.get("id")})',
                        inline=True
                    )

                    embed.add_field(
                        name='Player Count',
                        value=f'{len(players)} Players'
                    )

                # Total WAR
                total_war = this_roster.get('WARa', 0)
                embed.add_field(
                    name="Total sWAR", 
                    value=f"{total_war:.2f}" if isinstance(total_war, (int, float)) else str(total_war), 
                    inline=True
                )
                
                embed.add_field(
                    name='Position Counts',
                    value=self._position_code_block(this_roster),
                    inline=False
                )
        
        embeds.append(embed)
        
        # Create detailed player list embeds if there are players
        for roster_name, roster_info in roster_data.items():
            if roster_name in ['active', 'longil', 'shortil'] and 'players' in roster_info:
                players = sorted(roster_info['players'], key=lambda player: player.get('wara', 0), reverse=True)
                if players:
                    player_embed = self._create_player_list_embed(
                        team, roster_name, players
                    )
                    embeds.append(player_embed)
        
        return embeds
    
    def _position_code_block(self, roster_data: dict) -> str:
        return f'```\n C 1B 2B 3B SS\n' \
            f' {roster_data.get("C", 0)}  {roster_data.get("1B", 0)}  {roster_data.get("2B", 0)}  ' \
            f'{roster_data.get("3B", 0)}  {roster_data.get("SS", 0)}\n\nLF CF RF SP RP\n' \
            f' {roster_data.get("LF", 0)}  {roster_data.get("CF", 0)}  {roster_data.get("RF", 0)}  ' \
            f'{roster_data.get("SP", 0)}  {roster_data.get("RP", 0)}\n```'

    def _create_player_list_embed(self, team: Team, roster_name: str, 
                                 players: List[Dict[str, Any]]) -> discord.Embed:
        """Create an embed with detailed player list."""
        roster_titles = {
            'active': 'Active Roster',
            'longil': 'Minor League',
            'shortil': 'Injured List'
        }
        
        embed = EmbedTemplate.create_base_embed(
            title=f"{team.abbrev} - {roster_titles.get(roster_name, roster_name.title())}",
            color=int(team.color, 16) if team.color else EmbedColors.PRIMARY
        )
        
        # Group players by position for better organization
        batters = []
        pitchers = []
        
        for player in players:
            try:
                this_player = Player.from_api_data(player)
                player_line = f"{this_player} - sWAR: {this_player.wara}"

                if this_player.is_pitcher:
                    pitchers.append(player_line)
                else:
                    batters.append(player_line)
            except Exception as e:
                self.logger.warning(f"Failed to create player from data: {e}", player_id=player.get('id'))
        
        # Add player lists to embed
        if batters:
            # Split long lists into multiple fields if needed
            batter_chunks = self._chunk_list(batters, 16)
            for i, chunk in enumerate(batter_chunks):
                field_name = "Batters" if i == 0 else f"Batters (cont.)"
                embed.add_field(name=field_name, value="\n".join(chunk), inline=True)
            embed.add_field(name='', value='', inline=False)
        
        if pitchers:
            pitcher_chunks = self._chunk_list(pitchers, 16)
            for i, chunk in enumerate(pitcher_chunks):
                field_name = "Pitchers" if i == 0 else f"Pitchers (cont.)"
                embed.add_field(name=field_name, value="\n".join(chunk), inline=False)
        
        embed.set_footer(text=f"Total players: {len(players)}")
        
        return embed
    
    def _chunk_list(self, lst: List[str], chunk_size: int) -> List[List[str]]:
        """Split a list into chunks of specified size."""
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]