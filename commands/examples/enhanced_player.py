"""
Enhanced Player Command Example using Views v2.0

Demonstrates modern Discord UI components with the new view system.
This is an example of how to upgrade existing commands to use the new views.
"""
from typing import Optional, List

import discord
from discord.ext import commands

from services.player_service import player_service
from models.player import Player
from constants import SBA_CURRENT_SEASON
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from exceptions import BotException

# Import our new view components
from views import (
    SBAEmbedTemplate,
    EmbedTemplate,
    EmbedColors,
    PlayerSelectionView,
    DetailedInfoView,
    SearchResultsView,
    PlayerSearchModal,
    PaginationView
)


class EnhancedPlayerCommands(commands.Cog):
    """Enhanced player commands using modern view system."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.EnhancedPlayerCommands')
        self.logger.info("EnhancedPlayerCommands cog initialized")
    
    @discord.app_commands.command(
        name="player-enhanced",
        description="Enhanced player search with modern UI"
    )
    @discord.app_commands.describe(
        name="Player name to search for (optional - leave blank for advanced search)",
        season="Season to show stats for (defaults to current season)"
    )
    @logged_command("/player-enhanced")
    async def enhanced_player_info(
        self,
        interaction: discord.Interaction,
        name: Optional[str] = None,
        season: Optional[int] = None
    ):
        """Enhanced player search with modern UI components."""
        await interaction.response.defer()
        
        # If no name provided, show search modal
        if not name:
            modal = PlayerSearchModal()
            await interaction.followup.send("Please fill out the search form:", ephemeral=True)
            await interaction.user.send("Opening player search form...")
            
            # Note: In real implementation, you'd handle modal differently
            # This is just for demonstration
            embed = EmbedTemplate.info(
                title="Advanced Player Search",
                description="Use the `/player-enhanced` command with a name, or we'll add modal support soon!"
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Use current season if not specified
        search_season = season or SBA_CURRENT_SEASON
        
        # Search for players
        players = await player_service.get_players_by_name(name, search_season)
        
        if not players:
            # Try fuzzy search
            fuzzy_players = await player_service.search_players_fuzzy(name, limit=25)
            
            if not fuzzy_players:
                embed = EmbedTemplate.error(
                    title="No Players Found",
                    description=f"No players found matching '{name}' in season {search_season}."
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Show search results with selection
            await self._show_search_results(interaction, fuzzy_players, name, search_season)
            return
        
        # Handle multiple exact matches
        if len(players) > 1:
            await self._show_player_selection(interaction, players, search_season)
            return
        
        # Single player found - show detailed view
        await self._show_player_details(interaction, players[0], search_season)
    
    async def _show_search_results(
        self,
        interaction: discord.Interaction,
        players: List[Player],
        search_term: str,
        season: int
    ):
        """Show search results with modern pagination and selection."""
        # Prepare results for SearchResultsView
        results = []
        for player in players:
            results.append({
                'name': player.name,
                'detail': f"{player.primary_position} • WARA: {player.wara:.1f}",
                'player_obj': player
            })
        
        async def handle_selection(interaction: discord.Interaction, result: dict):
            """Handle player selection from search results."""
            selected_player = result['player_obj']
            await self._show_player_details(interaction, selected_player, season)
        
        # Create search results view with selection
        view = SearchResultsView(
            results=results,
            search_term=search_term,
            user_id=interaction.user.id,
            selection_callback=handle_selection,
            results_per_page=10
        )
        
        # Send with first page
        embed = view.get_current_embed()
        await interaction.followup.send(embed=embed, view=view)
    
    async def _show_player_selection(
        self,
        interaction: discord.Interaction,
        players: List[Player],
        season: int
    ):
        """Show player selection dropdown for multiple exact matches."""
        async def handle_player_choice(interaction: discord.Interaction, player: Player):
            """Handle player selection."""
            await self._show_player_details(interaction, player, season)
        
        # Create player selection view
        view = PlayerSelectionView(
            players=players,
            user_id=interaction.user.id,
            callback=handle_player_choice
        )
        
        # Setup the select options
        view.setup_options()
        
        # Create embed for selection
        embed = EmbedTemplate.info(
            title="Multiple Players Found",
            description=f"Found {len(players)} players matching your search. Please select one:"
        )
        
        await interaction.followup.send(embed=embed, view=view)
    
    async def _show_player_details(
        self,
        interaction: discord.Interaction,
        player: Player,
        season: int
    ):
        """Show detailed player information with action buttons."""
        # Get full player data with team information
        player_with_team = await player_service.get_player_with_team(player.id)
        if player_with_team is None:
            player_with_team = player
        
        # Create comprehensive player embed
        embed = self._create_enhanced_player_embed(player_with_team, season)
        
        # Create detailed info view with action buttons
        async def refresh_player_data(interaction: discord.Interaction) -> discord.Embed:
            """Refresh player data."""
            updated_player = await player_service.get_player_with_team(player.id)
            return self._create_enhanced_player_embed(updated_player or player, season)
        
        async def show_more_details(interaction: discord.Interaction):
            """Show additional player details."""
            # Create detailed stats embed
            stats_embed = self._create_player_stats_embed(player_with_team, season)
            await interaction.response.send_message(embed=stats_embed, ephemeral=True)
        
        view = DetailedInfoView(
            embed=embed,
            user_id=interaction.user.id,
            show_refresh=True,
            show_details=True,
            refresh_callback=refresh_player_data,
            details_callback=show_more_details
        )
        
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view)
    
    def _create_enhanced_player_embed(self, player: Player, season: int) -> discord.Embed:
        """Create enhanced player embed with additional information."""
        # Get team info if available
        team_abbrev = None
        team_name = None
        team_color = None
        
        if hasattr(player, 'team') and player.team:
            team_abbrev = player.team.abbrev
            team_name = player.team.sname
            team_color = getattr(player.team, 'color', None)
        
        # Create base embed
        embed = SBAEmbedTemplate.player_card(
            player_name=player.name,
            position=player.primary_position,
            team_abbrev=team_abbrev,
            team_name=team_name,
            wara=player.wara,
            season=season,
            player_image=getattr(player, 'image', None),
            team_color=team_color
        )
        
        # Add additional fields
        additional_fields = []
        
        # All positions if multiple
        if len(player.positions) > 1:
            additional_fields.append({
                'name': 'All Positions',
                'value': ', '.join(player.positions),
                'inline': True
            })
        
        # Add salary info if available
        if hasattr(player, 'salary') and player.salary:
            additional_fields.append({
                'name': 'Salary',
                'value': f"${player.salary:,}",
                'inline': True
            })
        
        # Add contract info if available
        if hasattr(player, 'contract_years') and player.contract_years:
            additional_fields.append({
                'name': 'Contract',
                'value': f"{player.contract_years} years",
                'inline': True
            })
        
        # Add the additional fields to embed
        for field in additional_fields:
            embed.add_field(
                name=field['name'],
                value=field['value'],
                inline=field['inline']
            )
        
        # Add footer with player ID
        embed.set_footer(text=f"Player ID: {player.id} • Use buttons below for more options")
        
        return embed
    
    def _create_player_stats_embed(self, player: Player, season: int) -> discord.Embed:
        """Create detailed player statistics embed."""
        embed = EmbedTemplate.create_base_embed(
            title=f"📊 {player.name} - Detailed Stats",
            description=f"Season {season} Statistics",
            color=EmbedColors.INFO
        )
        
        # Add batting stats if available
        if hasattr(player, 'batting_avg') and player.batting_avg is not None:
            embed.add_field(
                name="Batting Average",
                value=f"{player.batting_avg:.3f}",
                inline=True
            )
        
        if hasattr(player, 'home_runs') and player.home_runs is not None:
            embed.add_field(
                name="Home Runs",
                value=str(player.home_runs),
                inline=True
            )
        
        if hasattr(player, 'rbi') and player.rbi is not None:
            embed.add_field(
                name="RBI",
                value=str(player.rbi),
                inline=True
            )
        
        # Add pitching stats if available
        if hasattr(player, 'era') and player.era is not None:
            embed.add_field(
                name="ERA",
                value=f"{player.era:.2f}",
                inline=True
            )
        
        if hasattr(player, 'wins') and player.wins is not None:
            embed.add_field(
                name="Wins",
                value=str(player.wins),
                inline=True
            )
        
        if hasattr(player, 'strikeouts') and player.strikeouts is not None:
            embed.add_field(
                name="Strikeouts",
                value=str(player.strikeouts),
                inline=True
            )
        
        return embed

    @discord.app_commands.command(
        name="player-search-modal",
        description="Advanced player search using modal form"
    )
    @logged_command("/player-search-modal")
    async def player_search_modal(self, interaction: discord.Interaction):
        """Demonstrate modal-based player search."""
        modal = PlayerSearchModal()
        await interaction.response.send_modal(modal)
        
        # Wait for modal completion
        await modal.wait()
        
        if modal.is_submitted and modal.result:
            search_criteria = modal.result
            
            # Perform search based on criteria
            players = await player_service.get_players_by_name(
                search_criteria['name'], 
                search_criteria['season'] or SBA_CURRENT_SEASON
            )
            
            if players:
                # Show results using our views
                if len(players) == 1:
                    await self._show_player_details(
                        interaction, 
                        players[0], 
                        search_criteria['season'] or SBA_CURRENT_SEASON
                    )
                else:
                    await self._show_player_selection(
                        interaction, 
                        players, 
                        search_criteria['season'] or SBA_CURRENT_SEASON
                    )
            else:
                embed = EmbedTemplate.warning(
                    title="No Results",
                    description=f"No players found matching your search criteria."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Load the enhanced player commands cog."""
    await bot.add_cog(EnhancedPlayerCommands(bot))