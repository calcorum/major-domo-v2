"""
Common Discord View Components for Bot v2.0

Specialized views for frequent use cases including player/team selection,
detailed information displays, and interactive menus.
"""
from typing import Optional, List, Dict, Any, Callable, Awaitable, Union
import asyncio

import discord
from discord.ext import commands

from .base import BaseView, PaginationView, SelectMenuView
from .embeds import SBAEmbedTemplate, EmbedTemplate, EmbedColors
from models.player import Player
from models.team import Team
from utils.logging import get_contextual_logger


class PlayerSelectionView(SelectMenuView):
    """Select menu for choosing from multiple players."""
    
    def __init__(
        self,
        players: List[Player],
        *,
        user_id: int,
        callback: Optional[Callable[[discord.Interaction, Player], Awaitable[None]]] = None,
        timeout: float = 60.0,
        max_players: int = 25
    ):
        super().__init__(
            user_id=user_id,
            timeout=timeout,
            placeholder="Select a player...",
            logger_name=f'{__name__}.PlayerSelectionView'
        )
        
        self.players = players[:max_players]  # Discord limit
        self.callback = callback
        self.selected_player: Optional[Player] = None
        
        # Create select menu options
        self.add_item(self.player_select)
    
    @discord.ui.select(placeholder="Choose a player...")
    async def player_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle player selection."""
        self.increment_interaction_count()
        
        # Find selected player
        selected_id = int(select.values[0])
        self.selected_player = next(
            (p for p in self.players if p.id == selected_id), 
            None
        )
        
        if self.selected_player is None:
            await interaction.response.send_message(
                "❌ Player not found.",
                ephemeral=True
            )
            return
        
        # Disable the select menu
        select.disabled = True
        
        if self.callback:
            await self.callback(interaction, self.selected_player)
        else:
            # Default behavior: show player card
            embed = SBAEmbedTemplate.player_card(
                player_name=self.selected_player.name,
                position=self.selected_player.primary_position,
                wara=self.selected_player.wara,
                season=self.selected_player.season,
                player_image=getattr(self.selected_player, 'image', None)
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
        
        self.stop()
    
    def setup_options(self):
        """Setup select menu options from players."""
        options = []
        for player in self.players:
            # Create option label
            label = player.name[:100]  # Discord limit
            description = f"{player.primary_position}"
            
            if hasattr(player, 'team') and player.team:
                description += f" • {player.team.abbrev}"
            
            # Add WARA if available
            if player.wara is not None:
                description += f" • WARA: {player.wara:.2f}"
            
            options.append(discord.SelectOption(
                label=label,
                description=description[:100],  # Discord limit
                value=str(player.id)
            ))
        
        self.player_select.options = options


class TeamSelectionView(SelectMenuView):
    """Select menu for choosing from multiple teams."""
    
    def __init__(
        self,
        teams: List[Team],
        *,
        user_id: int,
        callback: Optional[Callable[[discord.Interaction, Team], Awaitable[None]]] = None,
        timeout: float = 60.0,
        max_teams: int = 25
    ):
        super().__init__(
            user_id=user_id,
            timeout=timeout,
            placeholder="Select a team...",
            logger_name=f'{__name__}.TeamSelectionView'
        )
        
        self.teams = teams[:max_teams]  # Discord limit
        self.callback = callback
        self.selected_team: Optional[Team] = None
        
        # Create select menu options
        self.add_item(self.team_select)
        self.setup_options()
    
    @discord.ui.select(placeholder="Choose a team...")
    async def team_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle team selection."""
        self.increment_interaction_count()
        
        # Find selected team
        selected_id = int(select.values[0])
        self.selected_team = next(
            (t for t in self.teams if t.id == selected_id), 
            None
        )
        
        if self.selected_team is None:
            await interaction.response.send_message(
                "❌ Team not found.",
                ephemeral=True
            )
            return
        
        # Disable the select menu
        select.disabled = True
        
        if self.callback:
            await self.callback(interaction, self.selected_team)
        else:
            # Default behavior: show team info
            embed = SBAEmbedTemplate.team_info(
                team_abbrev=self.selected_team.abbrev,
                team_name=self.selected_team.lname,
                season=self.selected_team.season,
                short_name=getattr(self.selected_team, 'sname', None),
                stadium=getattr(self.selected_team, 'stadium', None),
                team_color=getattr(self.selected_team, 'color', None),
                team_thumbnail=getattr(self.selected_team, 'thumbnail', None)
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
        
        self.stop()
    
    def setup_options(self):
        """Setup select menu options from teams."""
        options = []
        for team in self.teams:
            # Create option label
            label = f"{team.abbrev} - {team.lname}"[:100]  # Discord limit
            description = f"Season {team.season}"
            
            if hasattr(team, 'division_id') and team.division_id:
                description += f" • Division {team.division_id}"
            
            options.append(discord.SelectOption(
                label=label,
                description=description[:100],  # Discord limit
                value=str(team.id)
            ))
        
        self.team_select.options = options


class DetailedInfoView(BaseView):
    """View for displaying detailed information with action buttons."""
    
    def __init__(
        self,
        embed: discord.Embed,
        *,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        show_refresh: bool = False,
        show_details: bool = False,
        refresh_callback: Optional[Callable[[discord.Interaction], Awaitable[discord.Embed]]] = None,
        details_callback: Optional[Callable[[discord.Interaction], Awaitable[None]]] = None
    ):
        super().__init__(
            timeout=timeout,
            user_id=user_id,
            logger_name=f'{__name__}.DetailedInfoView'
        )
        
        self.embed = embed
        self.refresh_callback = refresh_callback
        self.details_callback = details_callback
        
        if show_refresh and refresh_callback:
            self.add_item(self.refresh_button)
        
        if show_details and details_callback:
            self.add_item(self.details_button)
    
    @discord.ui.button(
        label="Refresh",
        emoji="🔄",
        style=discord.ButtonStyle.secondary,
        row=0
    )
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the information."""
        self.increment_interaction_count()
        
        if self.refresh_callback:
            # Show loading state
            button.disabled = True
            button.label = "Refreshing..."
            await interaction.response.edit_message(view=self)
            
            try:
                # Get updated embed
                new_embed = await self.refresh_callback(interaction)
                self.embed = new_embed
                
                # Re-enable button
                button.disabled = False
                button.label = "Refresh"
                
                await interaction.edit_original_response(embed=new_embed, view=self)
                
            except Exception as e:
                self.logger.error("Failed to refresh data", error=e)
                button.disabled = False
                button.label = "Refresh"
                
                error_embed = EmbedTemplate.error(
                    title="Refresh Failed",
                    description="Unable to refresh data. Please try again."
                )
                
                await interaction.edit_original_response(embed=error_embed, view=self)
    
    @discord.ui.button(
        label="More Details",
        emoji="📊",
        style=discord.ButtonStyle.primary,
        row=0
    )
    async def details_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show more details."""
        self.increment_interaction_count()
        
        if self.details_callback:
            await self.details_callback(interaction)


class SearchResultsView(PaginationView):
    """Paginated view for search results with selection capability."""
    
    def __init__(
        self,
        results: List[Dict[str, Any]],
        search_term: str,
        *,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        results_per_page: int = 10,
        selection_callback: Optional[Callable[[discord.Interaction, Dict[str, Any]], Awaitable[None]]] = None
    ):
        self.results = results
        self.search_term = search_term
        self.results_per_page = results_per_page
        self.selection_callback = selection_callback
        
        # Create pages
        pages = self._create_pages()
        
        super().__init__(
            pages=pages,
            user_id=user_id,
            timeout=timeout,
            logger_name=f'{__name__}.SearchResultsView'
        )
        
        # Add selection dropdown if callback provided
        if selection_callback and results:
            self.add_item(self.result_select)
            self.setup_selection_options()
    
    def _create_pages(self) -> List[discord.Embed]:
        """Create embed pages from search results."""
        pages = []
        
        for i in range(0, len(self.results), self.results_per_page):
            page_results = self.results[i:i + self.results_per_page]
            
            embed = SBAEmbedTemplate.search_results(
                search_term=self.search_term,
                results=page_results,
                max_results=self.results_per_page
            )
            
            pages.append(embed)
        
        if not pages:
            # No results page
            embed = SBAEmbedTemplate.search_results(
                search_term=self.search_term,
                results=[],
                max_results=self.results_per_page
            )
            pages.append(embed)
        
        return pages
    
    @discord.ui.select(placeholder="Select a result...", row=1)
    async def result_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle result selection."""
        self.increment_interaction_count()
        
        if self.selection_callback:
            # Find selected result
            selected_index = int(select.values[0])
            if 0 <= selected_index < len(self.results):
                selected_result = self.results[selected_index]
                await self.selection_callback(interaction, selected_result)
            else:
                await interaction.response.send_message(
                    "❌ Invalid selection.",
                    ephemeral=True
                )
    
    def setup_selection_options(self):
        """Setup selection dropdown options."""
        options = []
        
        # Show results for current page
        start_idx = self.current_page * self.results_per_page
        end_idx = min(start_idx + self.results_per_page, len(self.results))
        
        for i in range(start_idx, end_idx):
            result = self.results[i]
            
            label = result.get('name', f'Result {i + 1}')[:100]
            description = result.get('detail', '')[:100]
            
            options.append(discord.SelectOption(
                label=label,
                description=description,
                value=str(i)
            ))
        
        if options:
            self.result_select.options = options
            self.result_select.disabled = False
        else:
            self.result_select.disabled = True


class QuickActionView(BaseView):
    """View with quick action buttons for common operations."""
    
    def __init__(
        self,
        *,
        user_id: Optional[int] = None,
        timeout: float = 180.0,
        actions: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(
            timeout=timeout,
            user_id=user_id,
            logger_name=f'{__name__}.QuickActionView'
        )
        
        self.actions = actions or []
        self._setup_action_buttons()
    
    def _setup_action_buttons(self):
        """Setup action buttons from actions list."""
        for i, action in enumerate(self.actions[:25]):  # Discord limit
            button = discord.ui.Button(
                label=action.get('label', f'Action {i + 1}'),
                emoji=action.get('emoji'),
                style=getattr(discord.ButtonStyle, action.get('style', 'secondary')),
                custom_id=f'action_{i}',
                row=i // 5  # 5 buttons per row
            )
            
            async def button_callback(interaction: discord.Interaction, btn=button, act=action):
                self.increment_interaction_count()
                callback = act.get('callback')
                if callback:
                    await callback(interaction)
            
            button.callback = button_callback
            self.add_item(button)


class SettingsView(BaseView):
    """View for displaying and modifying settings."""
    
    def __init__(
        self,
        settings: Dict[str, Any],
        *,
        user_id: int,
        timeout: float = 300.0,
        save_callback: Optional[Callable[[Dict[str, Any]], Awaitable[bool]]] = None
    ):
        super().__init__(
            timeout=timeout,
            user_id=user_id,
            logger_name=f'{__name__}.SettingsView'
        )
        
        self.settings = settings.copy()
        self.original_settings = settings.copy()
        self.save_callback = save_callback
        self.has_changes = False
    
    def create_settings_embed(self) -> discord.Embed:
        """Create embed showing current settings."""
        embed = EmbedTemplate.create_base_embed(
            title="⚙️ Settings",
            color=EmbedColors.SECONDARY
        )
        
        for key, value in self.settings.items():
            embed.add_field(
                name=key.replace('_', ' ').title(),
                value=str(value),
                inline=True
            )
        
        if self.has_changes:
            embed.set_footer(text="⚠️ You have unsaved changes")
        
        return embed
    
    @discord.ui.button(
        label="Save Changes",
        emoji="💾",
        style=discord.ButtonStyle.success,
        row=0
    )
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Save settings changes."""
        self.increment_interaction_count()
        
        if not self.has_changes:
            await interaction.response.send_message(
                "ℹ️ No changes to save.",
                ephemeral=True
            )
            return
        
        if self.save_callback:
            button.disabled = True
            await interaction.response.edit_message(view=self)
            
            try:
                success = await self.save_callback(self.settings)
                
                if success:
                    self.has_changes = False
                    self.original_settings = self.settings.copy()
                    
                    embed = EmbedTemplate.success(
                        title="Settings Saved",
                        description="Your settings have been saved successfully."
                    )
                else:
                    embed = EmbedTemplate.error(
                        title="Save Failed",
                        description="Failed to save settings. Please try again."
                    )
                
                button.disabled = False
                await interaction.edit_original_response(embed=embed, view=self)
                
            except Exception as e:
                self.logger.error("Failed to save settings", error=e)
                button.disabled = False
                
                embed = EmbedTemplate.error(
                    title="Save Error",
                    description="An error occurred while saving settings."
                )
                
                await interaction.edit_original_response(embed=embed, view=self)
    
    @discord.ui.button(
        label="Reset",
        emoji="🔄",
        style=discord.ButtonStyle.danger,
        row=0
    )
    async def reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reset settings to original values."""
        self.increment_interaction_count()
        
        self.settings = self.original_settings.copy()
        self.has_changes = False
        
        embed = self.create_settings_embed()
        await interaction.response.edit_message(embed=embed, view=self)