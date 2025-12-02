"""
Team information commands for Discord Bot v2.0
"""
import logging
from typing import Optional
from config import get_config

import discord
from discord.ext import commands

from services import team_service, player_service
from models.team import RosterType, Team
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from exceptions import BotException
from views.embeds import EmbedTemplate, EmbedColors
from views.base import PaginationView


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
        season = season or get_config().sba_season
        
        # Get team by abbreviation
        team = await team_service.get_team_by_abbrev(abbrev, season)
        
        if team is None:
            self.logger.info("Team not found", team_abbrev=abbrev, season=season)
            embed = EmbedTemplate.error(
                title="Team Not Found",
                description=f"No team found with abbreviation '{abbrev.upper()}' in season {season}"
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Get additional team data
        standings_data = await team_service.get_team_standings_position(team.id, season)
        
        # Create main embed
        embed = await self._create_team_embed(team, standings_data)
        
        await interaction.followup.send(embed=embed)
    
    @discord.app_commands.command(name="teams", description="List all teams in a season")
    @discord.app_commands.describe(
        season="Season to list teams for (defaults to current season)"
    )
    @logged_command("/teams")
    async def list_teams(self, interaction: discord.Interaction, season: Optional[int] = None):
        """List all teams in a season."""
        await interaction.response.defer()

        season = season or get_config().sba_season

        teams = await team_service.get_teams_by_season(season)

        if not teams:
            embed = EmbedTemplate.error(
                title="No Teams Found",
                description=f"No teams found for season {season}"
            )
            await interaction.followup.send(embed=embed)
            return

        # Filter to major league teams only and sort by abbreviation
        ml_teams = [team for team in teams if team.roster_type() == RosterType.MAJOR_LEAGUE]
        ml_teams.sort(key=lambda t: t.abbrev)

        if not ml_teams:
            embed = EmbedTemplate.error(
                title="No Major League Teams Found",
                description=f"No major league teams found for season {season}"
            )
            await interaction.followup.send(embed=embed)
            return

        # Create paginated embeds (12 teams per page to stay under character limit)
        teams_per_page = 12
        pages: list[discord.Embed] = []

        for i in range(0, len(ml_teams), teams_per_page):
            page_teams = ml_teams[i:i + teams_per_page]

            embed = EmbedTemplate.create_base_embed(
                title=f"SBA Teams - Season {season}",
                color=EmbedColors.PRIMARY
            )

            for team in page_teams:
                embed.add_field(
                    name=f'{team}',
                    value=self._team_detail_description(team),
                    inline=False
                )

            embed.set_footer(text=f"Total: {len(ml_teams)} teams")
            pages.append(embed)

        # Use pagination if multiple pages, otherwise send single embed
        if len(pages) > 1:
            pagination = PaginationView(
                pages=pages,
                user_id=interaction.user.id,
                show_page_numbers=True
            )
            await interaction.followup.send(embed=pagination.get_current_embed(), view=pagination)
        else:
            await interaction.followup.send(embed=pages[0])
    
    def _team_detail_description(self, team: Team) -> str:
        return f'GM: {team.gm_names()}\nID: {team.id}'

    async def _create_team_embed(self, team: Team, standings_data: Optional[dict] = None) -> discord.Embed:
        """Create a rich embed for team information."""
        embed = EmbedTemplate.create_base_embed(
            title=f"{team.abbrev} - {team.lname}",
            description=f"Season {team.season} Team Information",
            color=int(team.color, 16) if team.color else EmbedColors.PRIMARY
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

        # Core Players (6 most expensive)
        try:
            core_players = await player_service.get_players_by_team(team.id, team.season, sort='cost-desc')
            if core_players:
                # Take top 6 most expensive players
                top_players = core_players[:6]

                core_text = ""
                for i, player in enumerate(top_players, 1):
                    # Format: Position - Name (WARA)
                    position = getattr(player, 'pos_1', 'N/A') or 'N/A'
                    wara = getattr(player, 'wara', 0.0) or 0.0
                    core_text += f"{i}. {position} - {player.name} ({wara:.1f})\n"

                if core_text:
                    embed.add_field(name="Core Players", value=core_text, inline=False)
        except Exception as e:
            self.logger.warning(f"Failed to load core players for team {team.id}: {e}")

        # Thumbnail if available
        if team.thumbnail:
            embed.set_thumbnail(url=team.thumbnail)

        return embed