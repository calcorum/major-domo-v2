"""
League Standings Commands

Implements slash commands for displaying league standings and playoff picture.
"""
from typing import Optional

import discord
from discord.ext import commands

from services.standings_service import standings_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from constants import SBA_CURRENT_SEASON
from views.embeds import EmbedColors, EmbedTemplate


class StandingsCommands(commands.Cog):
    """League standings command handlers."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.StandingsCommands')
    
    @discord.app_commands.command(
        name="standings",
        description="Display league standings"
    )
    @discord.app_commands.describe(
        season="Season to show standings for (defaults to current season)",
        division="Show specific division only (optional)"
    )
    @logged_command("/standings")
    async def standings(
        self,
        interaction: discord.Interaction,
        season: Optional[int] = None,
        division: Optional[str] = None
    ):
        """Display league standings by division."""
        await interaction.response.defer()
        
        search_season = season or SBA_CURRENT_SEASON
        
        if division:
            # Show specific division
            await self._show_division_standings(interaction, search_season, division)
        else:
            # Show all divisions
            await self._show_all_standings(interaction, search_season)
    
    @discord.app_commands.command(
        name="playoff-picture",
        description="Display current playoff picture"
    )
    @discord.app_commands.describe(
        season="Season to show playoff picture for (defaults to current season)"
    )
    @logged_command("/playoff-picture")
    async def playoff_picture(
        self,
        interaction: discord.Interaction,
        season: Optional[int] = None
    ):
        """Display playoff picture with division leaders and wild card race."""
        await interaction.response.defer()
        
        search_season = season or SBA_CURRENT_SEASON
        self.logger.debug("Fetching playoff picture", season=search_season)
        
        playoff_data = await standings_service.get_playoff_picture(search_season)
        
        if not playoff_data["division_leaders"] and not playoff_data["wild_card"]:
            await interaction.followup.send(
                f"❌ No playoff data available for season {search_season}.",
                ephemeral=True
            )
            return
        
        embed = await self._create_playoff_picture_embed(playoff_data, search_season)
        await interaction.followup.send(embed=embed)
    
    async def _show_all_standings(self, interaction: discord.Interaction, season: int):
        """Show standings for all divisions."""
        self.logger.debug("Fetching all division standings", season=season)
        
        divisions = await standings_service.get_standings_by_division(season)
        
        if not divisions:
            await interaction.followup.send(
                f"❌ No standings available for season {season}.",
                ephemeral=True
            )
            return
        
        embeds = []
        
        # Create embed for each division
        for div_name, teams in divisions.items():
            if teams:  # Only create embed if division has teams
                embed = await self._create_division_embed(div_name, teams, season)
                embeds.append(embed)
        
        # Send first embed, then follow up with others
        if embeds:
            await interaction.followup.send(embed=embeds[0])
            
            # Send additional embeds as follow-ups
            for embed in embeds[1:]:
                await interaction.followup.send(embed=embed)
    
    async def _show_division_standings(self, interaction: discord.Interaction, season: int, division: str):
        """Show standings for a specific division."""
        self.logger.debug("Fetching division standings", season=season, division=division)
        
        divisions = await standings_service.get_standings_by_division(season)
        
        # Find matching division (case insensitive)
        target_division = None
        division_lower = division.lower()
        
        for div_name, teams in divisions.items():
            if division_lower in div_name.lower():
                target_division = (div_name, teams)
                break
        
        if not target_division:
            available = ", ".join(divisions.keys())
            await interaction.followup.send(
                f"❌ Division '{division}' not found. Available divisions: {available}",
                ephemeral=True
            )
            return
        
        div_name, teams = target_division
        
        if not teams:
            await interaction.followup.send(
                f"❌ No teams found in {div_name} division.",
                ephemeral=True
            )
            return
        
        embed = await self._create_division_embed(div_name, teams, season)
        await interaction.followup.send(embed=embed)
    
    async def _create_division_embed(self, division_name: str, teams, season: int) -> discord.Embed:
        """Create an embed for a division's standings."""
        embed = EmbedTemplate.create_base_embed(
            title=f"🏆 {division_name} Division - Season {season}",
            color=EmbedColors.PRIMARY
        )
        
        # Create standings table
        standings_lines = []
        for i, team in enumerate(teams, 1):
            # Format team line
            team_line = (
                f"{i}. **{team.team.abbrev}** {team.wins}-{team.losses} "
                f"({team.winning_percentage:.3f})"
            )
            
            # Add games behind if not first place
            if team.div_gb is not None and team.div_gb > 0:
                team_line += f" *{team.div_gb:.1f} GB*"
            
            standings_lines.append(team_line)
        
        embed.add_field(
            name="Standings",
            value="\n".join(standings_lines),
            inline=False
        )
        
        # # Add additional stats for top teams
        # if len(teams) >= 3:
        #     stats_lines = []
        #     for team in teams[:3]:  # Top 3 teams
        #         stats_line = (
        #             f"**{team.team.abbrev}**: "
        #             f"Home {team.home_record} • "
        #             f"Last 8: {team.last8_record} • "
        #             f"Streak: {team.current_streak}"
        #         )
        #         stats_lines.append(stats_line)
            
        #     embed.add_field(
        #         name="Recent Form (Top 3)",
        #         value="\n".join(stats_lines),
        #         inline=False
        #     )
        
        embed.set_footer(text=f"Season {season}")
        return embed
    
    async def _create_playoff_picture_embed(self, playoff_data, season: int) -> discord.Embed:
        """Create playoff picture embed."""
        embed = EmbedTemplate.create_base_embed(
            title=f"🏅 Playoff Picture - Season {season}",
            color=EmbedColors.SUCCESS
        )
        
        # Division Leaders
        if playoff_data["division_leaders"]:
            leaders_lines = []
            for i, team in enumerate(playoff_data["division_leaders"], 1):
                division = team.team.division.division_name if hasattr(team.team, 'division') and team.team.division else "Unknown"
                leaders_lines.append(
                    f"{i}. **{team.team.abbrev}** {team.wins}-{team.losses} "
                    f"({team.winning_percentage:.3f}) - *{division}*"
                )
            
            embed.add_field(
                name="🥇 Division Leaders",
                value="\n".join(leaders_lines),
                inline=False
            )
        
        # Wild Card Race
        if playoff_data["wild_card"]:
            wc_lines = []
            for i, team in enumerate(playoff_data["wild_card"][:8], 1):  # Top 8 wild card
                wc_gb = team.wild_card_gb_display
                wc_line = (
                    f"{i}. **{team.team.abbrev}** {team.wins}-{team.losses} "
                    f"({team.winning_percentage:.3f})"
                )
                
                # Add games behind info
                if wc_gb != "-":
                    wc_line += f" *{wc_gb} GB*"
                elif i <= 4:
                    wc_line += " *In playoffs*"
                
                wc_lines.append(wc_line)
                
                # Add playoff cutoff line after 4th team
                if i == 4:
                    wc_lines.append("─────────── *Playoff Cutoff* ───────────")
            
            embed.add_field(
                name="🎯 Wild Card Race (Top 4 make playoffs)",
                value="\n".join(wc_lines),
                inline=False
            )
        
        embed.set_footer(text=f"Season {season}")
        return embed


async def setup(bot: commands.Bot):
    """Load the standings commands cog."""
    await bot.add_cog(StandingsCommands(bot))