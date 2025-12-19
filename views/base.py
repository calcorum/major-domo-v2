"""
Base View Classes for Discord Bot v2.0

Provides foundational view components with consistent styling and behavior.
"""
import logging
from typing import List, Optional, Any, Callable, Awaitable, Union
from datetime import datetime, timezone

import discord
from discord.ext import commands

from utils.logging import get_contextual_logger


class BaseView(discord.ui.View):
    """Base view class with consistent styling and error handling."""
    
    def __init__(
        self, 
        *,
        timeout: float = 180.0,
        user_id: Optional[int] = None,
        responders: Optional[List[int | None]] = None,
        logger_name: Optional[str] = None
    ):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.responders = responders
        self.logger = get_contextual_logger(logger_name or f'{__name__}.BaseView')
        self.interaction_count = 0
        self.created_at = datetime.now(timezone.utc)
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user is authorized to interact with this view.

        Authorization logic:
        - If no restrictions set (user_id and responders both None), allow all
        - If user_id is set, the original command user can interact
        - If responders is set, anyone in the responders list can interact
        - User only needs to match ONE condition to be authorized
        """
        # No restrictions - allow everyone
        if self.user_id is None and self.responders is None:
            return True

        # Check if user is authorized by either condition
        is_command_user = self.user_id is not None and interaction.user.id == self.user_id
        is_authorized_responder = (
            self.responders is not None and
            interaction.user.id in [r for r in self.responders if r is not None]
        )

        if is_command_user or is_authorized_responder:
            return True

        await interaction.response.send_message(
            "❌ You cannot interact with this menu.",
            ephemeral=True
        )
        return False
    
    async def on_timeout(self) -> None:
        """Handle view timeout."""
        self.logger.info("View timed out", 
                        user_id=self.user_id,
                        interaction_count=self.interaction_count,
                        timeout=self.timeout)
        
        # Disable all items
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True # type: ignore
            else:
                self.logger.info(f'Item {item} has no "disabled" attribute')
    
    async def on_error(
        self, 
        interaction: discord.Interaction, 
        error: Exception, 
        item: discord.ui.Item[Any]
    ) -> None:
        """Handle view errors."""
        self.logger.error("View error occurred",
                         user_id=interaction.user.id,
                         error=error,
                         item_type=type(item).__name__,
                         interaction_count=self.interaction_count)
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing your interaction.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ An error occurred while processing your interaction.",
                    ephemeral=True
                )
        except Exception as e:
            self.logger.error("Failed to send error message", error=e)
    
    def increment_interaction_count(self) -> None:
        """Increment the interaction counter."""
        self.interaction_count += 1


class ConfirmationView(BaseView):
    """Standard confirmation dialog with Yes/No buttons."""
    
    def __init__(
        self,
        *,
        user_id: Optional[int] = None,
        responders: Optional[List[int | None]] = None,
        timeout: float = 60.0,
        confirm_callback: Optional[Callable[[discord.Interaction], Awaitable[None]]] = None,
        cancel_callback: Optional[Callable[[discord.Interaction], Awaitable[None]]] = None,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel"
    ):
        super().__init__(timeout=timeout, user_id=user_id, responders=responders, logger_name=f'{__name__}.ConfirmationView')
        self.confirm_callback = confirm_callback
        self.cancel_callback = cancel_callback
        self.result: Optional[bool] = None
        
        # Update button labels
        self.confirm_button.label = confirm_label
        self.cancel_button.label = cancel_label
    
    @discord.ui.button(
        label="Confirm",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle confirmation."""
        self.increment_interaction_count()
        self.result = True
        
        # Disable all buttons
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True # type: ignore
            else:
                self.logger.info(f'Item {item} has no "disabled" attribute')
        
        if self.confirm_callback:
            await self.confirm_callback(interaction)
        else:
            await interaction.response.edit_message(
                content="✅ Confirmed!",
                view=self
            )
        
        self.stop()
    
    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        emoji="❌"
    )
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle cancellation."""
        self.increment_interaction_count()
        self.result = False
        
        # Disable all buttons
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True # type: ignore
            else:
                self.logger.info(f'Item {item} has no "disabled" attribute')
        
        if self.cancel_callback:
            await self.cancel_callback(interaction)
        else:
            await interaction.response.edit_message(
                content="❌ Cancelled.",
                view=self
            )
        
        self.stop()


class PaginationView(BaseView):
    """Pagination view for navigating through multiple pages."""
    
    def __init__(
        self,
        *,
        pages: list[discord.Embed],
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        show_page_numbers: bool = True,
        logger_name: Optional[str] = None
    ):
        super().__init__(timeout=timeout, user_id=user_id, logger_name=logger_name or f'{__name__}.PaginationView')
        self.pages = pages
        self.current_page = 0
        self.show_page_numbers = show_page_numbers
        
        # Update button states
        self._update_buttons()
    
    def _update_buttons(self) -> None:
        """Update button enabled/disabled states."""
        self.first_page.disabled = self.current_page == 0
        self.previous_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == len(self.pages) - 1
        self.last_page.disabled = self.current_page == len(self.pages) - 1
        
        if self.show_page_numbers:
            self.page_info.label = f"{self.current_page + 1}/{len(self.pages)}"
    
    def get_current_embed(self) -> discord.Embed:
        """Get the current page embed with footer."""
        embed = self.pages[self.current_page].copy()
        
        if self.show_page_numbers:
            footer_text = f"Page {self.current_page + 1} of {len(self.pages)}"
            if embed.footer.text:
                footer_text = f"{embed.footer.text} • {footer_text}"
            embed.set_footer(text=footer_text, icon_url=embed.footer.icon_url)
        
        return embed
    
    @discord.ui.button(emoji="⏪", style=discord.ButtonStyle.secondary, row=0)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Jump to first page."""
        self.increment_interaction_count()
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.primary, row=0)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page."""
        self.increment_interaction_count()
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True, row=0)
    async def page_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Page info button (disabled)."""
        pass
    
    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.primary, row=0)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page."""
        self.increment_interaction_count()
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(emoji="⏩", style=discord.ButtonStyle.secondary, row=0)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Jump to last page."""
        self.increment_interaction_count()
        self.current_page = len(self.pages) - 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(emoji="🗑️", style=discord.ButtonStyle.danger, row=1)
    async def delete_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete the message."""
        self.increment_interaction_count()
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()


class SelectMenuView(BaseView):
    """Base class for views with select menus."""
    
    def __init__(
        self,
        *,
        user_id: Optional[int] = None,
        timeout: float = 180.0,
        placeholder: str = "Select an option...",
        min_values: int = 1,
        max_values: int = 1,
        logger_name: Optional[str] = None
    ):
        super().__init__(timeout=timeout, user_id=user_id, logger_name=logger_name or f'{__name__}.SelectMenuView')
        self.placeholder = placeholder
        self.min_values = min_values
        self.max_values = max_values
        self.selected_values: list[str] = []