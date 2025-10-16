"""
Migration Example: Before and After Views v2.0

Shows how to upgrade existing commands to use the modern view system.
This demonstrates the transformation from basic embeds to interactive views.
"""
from typing import Optional, List

import discord
from discord.ext import commands

from services.team_service import team_service
from models.team import Team
from utils.logging import get_contextual_logger
from views.embeds import EmbedTemplate, EmbedColors
from utils.decorators import logged_command

# Import new view components
from views import (
    SBAEmbedTemplate,
    EmbedTemplate,
    EmbedColors,
    TeamSelectionView,
    PaginationView,
    ConfirmationView,
    DetailedInfoView
)


class MigrationExampleCommands(commands.Cog):
    """Example showing before/after migration to Views v2.0."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.MigrationExampleCommands')
    
    # ========================================
    # BEFORE: Traditional approach
    # ========================================
    
    @discord.app_commands.command(
        name="teams-old",
        description="List teams (old style - basic embed)"
    )
    @logged_command("/teams-old")
    async def teams_old_style(self, interaction: discord.Interaction, season: Optional[int] = None):
        """Old style team listing - basic embed only."""
        await interaction.response.defer()
        
        season = season or get_config().sba_current_season
        teams = await team_service.get_teams_by_season(season)
        
        if not teams:
            embed = EmbedTemplate.error(
                title="No Teams Found",
                description=f"No teams found for season {season}"
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Sort teams by abbreviation
        teams.sort(key=lambda t: t.abbrev)
        
        # Create basic embed
        embed = EmbedTemplate.create_base_embed(
            title=f"SBA Teams - Season {season}",
            color=EmbedColors.PRIMARY
        )
        
        # Simple list - limited functionality
        team_list = "\n".join([f"**{team.abbrev}** - {team.lname}" for team in teams[:20]])
        if len(teams) > 20:
            team_list += f"\n... and {len(teams) - 20} more teams"
        
        embed.add_field(name="Teams", value=team_list, inline=False)
        embed.set_footer(text=f"Total: {len(teams)} teams")
        
        await interaction.followup.send(embed=embed)
    
    # ========================================
    # AFTER: Modern Views v2.0 approach
    # ========================================
    
    @discord.app_commands.command(
        name="teams-new",
        description="List teams (new style - interactive with views)"
    )
    @logged_command("/teams-new")
    async def teams_new_style(self, interaction: discord.Interaction, season: Optional[int] = None):
        """New style team listing - interactive with pagination and selection."""
        await interaction.response.defer()
        
        season = season or get_config().sba_current_season
        teams = await team_service.get_teams_by_season(season)
        
        if not teams:
            embed = EmbedTemplate.warning(
                title="No Teams Found",
                description=f"No teams found for season {season}"
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Sort teams by abbreviation
        teams.sort(key=lambda t: t.abbrev)
        
        # Create paginated view with team selection
        await self._create_interactive_team_list(interaction, teams, season)
    
    async def _create_interactive_team_list(
        self,
        interaction: discord.Interaction,
        teams: List[Team],
        season: int
    ):
        """Create interactive team list with pagination and selection."""
        teams_per_page = 10
        pages = []
        
        # Create pages
        for i in range(0, len(teams), teams_per_page):
            page_teams = teams[i:i + teams_per_page]
            
            embed = SBAEmbedTemplate.league_status(
                season=season,
                teams_count=len(teams),
                additional_info=f"Showing teams {i + 1}-{min(i + teams_per_page, len(teams))} of {len(teams)}"
            )
            embed.title = f"🏟️ SBA Teams - Season {season}"
            
            # Group teams by division if available
            if any(getattr(team, 'division_id', None) for team in page_teams):
                divisions = {}
                for team in page_teams:
                    div_id = getattr(team, 'division_id', 0) or 0
                    if div_id not in divisions:
                        divisions[div_id] = []
                    divisions[div_id].append(team)
                
                for div_id, div_teams in sorted(divisions.items()):
                    div_name = f"Division {div_id}" if div_id > 0 else "Unassigned"
                    team_list = "\n".join([
                        f"**{team.abbrev}** - {team.lname}"
                        for team in div_teams
                    ])
                    embed.add_field(name=div_name, value=team_list, inline=True)
            else:
                # Simple list if no divisions
                team_list = "\n".join([
                    f"**{team.abbrev}** - {team.lname}"
                    for team in page_teams
                ])
                embed.add_field(name="Teams", value=team_list, inline=False)
            
            pages.append(embed)
        
        # Create pagination view
        view = PaginationView(
            pages=pages,
            user_id=interaction.user.id,
            show_page_numbers=True
        )
        
        # Add team selection dropdown to first row
        if len(teams) <= 25:  # Discord limit for select options
            team_select = TeamSelectionView(
                teams=teams,
                user_id=interaction.user.id,
                callback=self._handle_team_selection
            )
            
            # Combine pagination with selection (would need custom view for this)
            # For now, show them separately
            
        await interaction.followup.send(embed=view.get_current_embed(), view=view)
        
        # Also provide team selection if reasonable number
        if len(teams) <= 25:
            await self._add_team_selection_followup(interaction, teams)
    
    async def _add_team_selection_followup(
        self,
        interaction: discord.Interaction,
        teams: List[Team]
    ):
        """Add team selection as follow-up message."""
        view = TeamSelectionView(
            teams=teams,
            user_id=interaction.user.id,
            callback=self._handle_team_selection
        )
        
        embed = EmbedTemplate.info(
            title="Team Selection",
            description="Select a team below to view detailed information:"
        )
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    async def _handle_team_selection(
        self,
        interaction: discord.Interaction,
        team: Team
    ):
        """Handle team selection from dropdown."""
        # Get additional team data
        standings_data = await team_service.get_team_standings_position(team.id, team.season)
        
        # Create detailed team embed
        embed = SBAEmbedTemplate.team_info(
            team_abbrev=team.abbrev,
            team_name=team.lname,
            season=team.season,
            short_name=getattr(team, 'sname', None),
            stadium=getattr(team, 'stadium', None),
            division=f"Division {team.division_id}" if getattr(team, 'division_id', None) else None,
            team_color=getattr(team, 'color', None),
            team_thumbnail=getattr(team, 'thumbnail', None)
        )
        
        # Add standings info if available
        if standings_data:
            try:
                wins = standings_data.get('wins', 'N/A')
                losses = standings_data.get('losses', 'N/A')
                pct = standings_data.get('pct', 'N/A')
                gb = standings_data.get('gb', 'N/A')
                
                record_text = f"{wins}-{losses}"
                if pct != 'N/A':
                    record_text += f" ({pct:.3f})"
                if gb != 'N/A' and gb != 0:
                    record_text += f" • {gb} GB"
                
                embed.add_field(name="Record", value=record_text, inline=False)
            except (KeyError, TypeError):
                pass
        
        # Create detailed info view with actions
        async def refresh_team_data(interaction: discord.Interaction) -> discord.Embed:
            """Refresh team data."""
            updated_standings = await team_service.get_team_standings_position(team.id, team.season)
            # Recreate embed with updated data
            return embed  # Simplified for example
        
        async def show_roster(interaction: discord.Interaction):
            """Show team roster."""
            roster_embed = EmbedTemplate.info(
                title=f"{team.abbrev} Roster",
                description="Roster functionality would go here..."
            )
            await interaction.response.send_message(embed=roster_embed, ephemeral=True)
        
        view = DetailedInfoView(
            embed=embed,
            user_id=interaction.user.id,
            show_refresh=True,
            show_details=True,
            refresh_callback=refresh_team_data,
            details_callback=show_roster
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    # ========================================
    # Additional Examples
    # ========================================
    
    @discord.app_commands.command(
        name="confirmation-example",
        description="Example of confirmation dialog"
    )
    @logged_command("/confirmation-example")
    async def confirmation_example(self, interaction: discord.Interaction):
        """Example of modern confirmation dialog."""
        embed = EmbedTemplate.warning(
            title="Confirm Action",
            description="This is an example confirmation dialog. Do you want to proceed?"
        )
        
        async def handle_confirm(interaction: discord.Interaction):
            """Handle confirmation."""
            success_embed = EmbedTemplate.success(
                title="Action Confirmed",
                description="The action has been completed successfully!"
            )
            await interaction.response.edit_message(embed=success_embed, view=None)
        
        async def handle_cancel(interaction: discord.Interaction):
            """Handle cancellation."""
            cancel_embed = EmbedTemplate.error(
                title="Action Cancelled",
                description="The action has been cancelled."
            )
            await interaction.response.edit_message(embed=cancel_embed, view=None)
        
        view = ConfirmationView(
            user_id=interaction.user.id,
            confirm_callback=handle_confirm,
            cancel_callback=handle_cancel,
            confirm_label="Yes, Proceed",
            cancel_label="No, Cancel"
        )
        
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    """Load the migration example commands cog."""
from config import get_config
    await bot.add_cog(MigrationExampleCommands(bot))