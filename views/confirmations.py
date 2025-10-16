"""
Confirmation Views

Reusable confirmation dialogs for user interactions.
"""
import discord
from typing import List, Optional, Union


class ConfirmationView(discord.ui.View):
    """
    Reusable confirmation dialog with Confirm/Cancel buttons.

    Usage:
        view = ConfirmationView(responders=[interaction.user])
        await interaction.edit_original_response(
            content="Are you sure?",
            view=view
        )
        await view.wait()

        if view.confirmed:
            # User clicked Confirm
        elif view.confirmed is False:
            # User clicked Cancel
        else:
            # Timeout (view.confirmed is None)

    Attributes:
        confirmed: True if confirmed, False if cancelled, None if timeout
    """

    def __init__(
        self,
        responders: List[Union[discord.User, discord.Member]],
        timeout: float = 30.0,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        confirm_style: discord.ButtonStyle = discord.ButtonStyle.green,
        cancel_style: discord.ButtonStyle = discord.ButtonStyle.grey
    ):
        """
        Initialize confirmation view.

        Args:
            responders: List of users/members who can interact with this view
            timeout: Timeout in seconds (default 30)
            confirm_label: Label for confirm button
            cancel_label: Label for cancel button
            confirm_style: Button style for confirm
            cancel_style: Button style for cancel
        """
        super().__init__(timeout=timeout)

        if not isinstance(responders, list):
            raise TypeError('responders must be a list of discord.User or discord.Member objects')

        self.confirmed: Optional[bool] = None
        self.responders: List[Union[discord.User, discord.Member]] = responders

        # Create buttons with custom labels and styles
        self.confirm_button.label = confirm_label
        self.confirm_button.style = confirm_style
        self.cancel_button.label = cancel_label
        self.cancel_button.style = cancel_style

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Handle confirm button click."""
        if interaction.user not in self.responders:
            await interaction.response.send_message(
                "❌ You cannot interact with this confirmation.",
                ephemeral=True
            )
            return

        self.confirmed = True
        self.clear_items()
        self.stop()

        # Defer to prevent "interaction failed" message
        await interaction.response.defer()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Handle cancel button click."""
        if interaction.user not in self.responders:
            await interaction.response.send_message(
                "❌ You cannot interact with this confirmation.",
                ephemeral=True
            )
            return

        self.confirmed = False
        self.clear_items()
        self.stop()

        # Defer to prevent "interaction failed" message
        await interaction.response.defer()

    async def on_timeout(self):
        """Handle timeout - confirmed remains None."""
        self.clear_items()
