"""
Interactive Trade Embed Views

Handles the Discord embed and button interfaces for the multi-team trade builder.
"""
import discord
from typing import Optional, List
from datetime import datetime

from services.trade_builder import TradeBuilder, TradeValidationResult
from views.embeds import EmbedColors, EmbedTemplate


class TradeEmbedView(discord.ui.View):
    """Interactive view for the trade builder embed."""

    def __init__(self, builder: TradeBuilder, user_id: int):
        """
        Initialize the trade embed view.

        Args:
            builder: TradeBuilder instance
            user_id: Discord user ID (for permission checking)
        """
        super().__init__(timeout=900.0)  # 15 minute timeout
        self.builder = builder
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to interact with this view."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ You don't have permission to use this trade builder.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Handle view timeout."""
        # Disable all buttons when timeout occurs
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    @discord.ui.button(label="Remove Move", style=discord.ButtonStyle.red, emoji="➖")
    async def remove_move_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle remove move button click."""
        if self.builder.is_empty:
            await interaction.response.send_message(
                "❌ No moves to remove. Add some moves first!",
                ephemeral=True
            )
            return

        # Create select menu for move removal
        select_view = RemoveTradeMovesView(self.builder, self.user_id)
        embed = await create_trade_embed(self.builder)

        await interaction.response.edit_message(embed=embed, view=select_view)

    @discord.ui.button(label="Validate Trade", style=discord.ButtonStyle.secondary, emoji="🔍")
    async def validate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle validate trade button click."""
        await interaction.response.defer(ephemeral=True)

        # Perform detailed validation
        validation = await self.builder.validate_trade()

        # Create validation report
        if validation.is_legal:
            status_emoji = "✅"
            status_text = "**Trade is LEGAL**"
            color = EmbedColors.SUCCESS
        else:
            status_emoji = "❌"
            status_text = "**Trade has ERRORS**"
            color = EmbedColors.ERROR

        embed = EmbedTemplate.create_base_embed(
            title=f"{status_emoji} Trade Validation Report",
            description=status_text,
            color=color
        )

        # Add team-by-team validation
        for participant in self.builder.trade.participants:
            team_validation = validation.get_participant_validation(participant.team.id)
            if team_validation:
                team_status = []
                team_status.append(team_validation.major_league_status)
                team_status.append(team_validation.minor_league_status)
                team_status.append(team_validation.major_league_swar_status)
                team_status.append(team_validation.minor_league_swar_status)

                if team_validation.pre_existing_transactions_note:
                    team_status.append(team_validation.pre_existing_transactions_note)

                embed.add_field(
                    name=f"🏟️ {participant.team.abbrev} - {participant.team.sname}",
                    value="\n".join(team_status),
                    inline=False
                )

        # Add overall errors and suggestions
        if validation.all_errors:
            error_text = "\n".join([f"• {error}" for error in validation.all_errors])
            embed.add_field(
                name="❌ Errors",
                value=error_text,
                inline=False
            )

        if validation.all_suggestions:
            suggestion_text = "\n".join([f"💡 {suggestion}" for suggestion in validation.all_suggestions])
            embed.add_field(
                name="💡 Suggestions",
                value=suggestion_text,
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Submit Trade", style=discord.ButtonStyle.primary, emoji="📤")
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle submit trade button click."""
        if self.builder.is_empty:
            await interaction.response.send_message(
                "❌ Cannot submit empty trade. Add some moves first!",
                ephemeral=True
            )
            return

        # Validate before submission
        validation = await self.builder.validate_trade()
        if not validation.is_legal:
            error_msg = "❌ **Cannot submit illegal trade:**\n"
            error_msg += "\n".join([f"• {error}" for error in validation.all_errors])

            if validation.all_suggestions:
                error_msg += "\n\n**Suggestions:**\n"
                error_msg += "\n".join([f"💡 {suggestion}" for suggestion in validation.all_suggestions])

            await interaction.response.send_message(error_msg, ephemeral=True)
            return

        # Show confirmation modal
        modal = SubmitTradeConfirmationModal(self.builder)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cancel Trade", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle cancel trade button click."""
        self.builder.clear_trade()
        embed = await create_trade_embed(self.builder)

        # Disable all buttons after cancellation
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        await interaction.response.edit_message(
            content="❌ **Trade cancelled and cleared.**",
            embed=embed,
            view=self
        )
        self.stop()


class RemoveTradeMovesView(discord.ui.View):
    """View for selecting which trade move to remove."""

    def __init__(self, builder: TradeBuilder, user_id: int):
        super().__init__(timeout=300.0)  # 5 minute timeout
        self.builder = builder
        self.user_id = user_id

        # Create select menu with current moves
        if not builder.is_empty:
            self.add_item(RemoveTradeMovesSelect(builder))

        # Add back button
        back_button = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, emoji="⬅️")
        back_button.callback = self.back_callback
        self.add_item(back_button)

    async def back_callback(self, interaction: discord.Interaction):
        """Handle back button to return to main view."""
        main_view = TradeEmbedView(self.builder, self.user_id)
        embed = await create_trade_embed(self.builder)
        await interaction.response.edit_message(embed=embed, view=main_view)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to interact with this view."""
        return interaction.user.id == self.user_id


class RemoveTradeMovesSelect(discord.ui.Select):
    """Select menu for choosing which trade move to remove."""

    def __init__(self, builder: TradeBuilder):
        self.builder = builder

        # Create options from all moves (cross-team and supplementary)
        options = []
        move_count = 0

        # Add cross-team moves
        for move in builder.trade.cross_team_moves[:20]:  # Limit to avoid Discord's 25 option limit
            options.append(discord.SelectOption(
                label=f"{move.player.name}",
                description=move.description[:100],  # Discord description limit
                value=str(move.player.id),
                emoji="🔄"
            ))
            move_count += 1

        # Add supplementary moves if there's room
        remaining_slots = 25 - move_count
        for move in builder.trade.supplementary_moves[:remaining_slots]:
            options.append(discord.SelectOption(
                label=f"{move.player.name}",
                description=move.description[:100],
                value=str(move.player.id),
                emoji="⚙️"
            ))

        super().__init__(
            placeholder="Select a move to remove...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle move removal selection."""
        player_id = int(self.values[0])

        success, error_msg = await self.builder.remove_move(player_id)

        if success:
            await interaction.response.send_message(
                f"✅ Removed move for player ID {player_id}",
                ephemeral=True
            )

            # Update the embed
            main_view = TradeEmbedView(self.builder, interaction.user.id)
            embed = await create_trade_embed(self.builder)

            # Edit the original message
            await interaction.edit_original_response(embed=embed, view=main_view)
        else:
            await interaction.response.send_message(
                f"❌ Could not remove move: {error_msg}",
                ephemeral=True
            )


class SubmitTradeConfirmationModal(discord.ui.Modal):
    """Modal for confirming trade submission."""

    def __init__(self, builder: TradeBuilder):
        super().__init__(title="Confirm Trade Submission")
        self.builder = builder

        self.confirmation = discord.ui.TextInput(
            label="Type 'CONFIRM' to submit",
            placeholder="CONFIRM",
            required=True,
            max_length=7
        )

        self.add_item(self.confirmation)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle confirmation submission."""
        if self.confirmation.value.upper() != "CONFIRM":
            await interaction.response.send_message(
                "❌ Trade not submitted. You must type 'CONFIRM' exactly.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # For now, just show success message since actual submission
            # would require integration with the transaction processing system

            # Create success message
            success_msg = f"✅ **Trade Submitted Successfully!**\n\n"
            success_msg += f"**Trade ID:** `{self.builder.trade_id}`\n"
            success_msg += f"**Teams:** {self.builder.trade.get_trade_summary()}\n"
            success_msg += f"**Total Moves:** {self.builder.move_count}\n\n"

            success_msg += "**Trade Details:**\n"

            # Show cross-team moves
            if self.builder.trade.cross_team_moves:
                success_msg += "**Player Exchanges:**\n"
                for move in self.builder.trade.cross_team_moves:
                    success_msg += f"• {move.description}\n"

            # Show supplementary moves
            if self.builder.trade.supplementary_moves:
                success_msg += "\n**Supplementary Moves:**\n"
                for move in self.builder.trade.supplementary_moves:
                    success_msg += f"• {move.description}\n"

            success_msg += f"\n💡 Use `/trade view` to check trade status"

            await interaction.followup.send(success_msg, ephemeral=True)

            # Clear the builder after successful submission
            from services.trade_builder import clear_trade_builder
            clear_trade_builder(interaction.user.id)

            # Update the original embed to show completion
            completion_embed = discord.Embed(
                title="✅ Trade Submitted",
                description=f"Your trade has been submitted successfully!\n\nTrade ID: `{self.builder.trade_id}`",
                color=0x00ff00
            )

            # Disable all buttons
            view = discord.ui.View()

            try:
                # Find and update the original message
                async for message in interaction.channel.history(limit=50): # type: ignore
                    if message.author == interaction.client.user and message.embeds:
                        if "Trade Builder" in message.embeds[0].title: # type: ignore
                            await message.edit(embed=completion_embed, view=view)
                            break
            except:
                pass

        except Exception as e:
            await interaction.followup.send(
                f"❌ Error submitting trade: {str(e)}",
                ephemeral=True
            )


async def create_trade_embed(builder: TradeBuilder) -> discord.Embed:
    """
    Create the main trade builder embed.

    Args:
        builder: TradeBuilder instance

    Returns:
        Discord embed with current trade state
    """
    # Determine embed color based on trade status
    if builder.is_empty:
        color = EmbedColors.SECONDARY
    else:
        validation = await builder.validate_trade()
        color = EmbedColors.SUCCESS if validation.is_legal else EmbedColors.WARNING

    embed = EmbedTemplate.create_base_embed(
        title=f"📋 Trade Builder - {builder.trade.get_trade_summary()}",
        description=f"Build your multi-team trade",
        color=color
    )

    # Add participating teams section
    team_list = [f"• {team.abbrev} - {team.sname}" for team in builder.participating_teams]
    embed.add_field(
        name=f"🏟️ Participating Teams ({builder.team_count})",
        value="\n".join(team_list) if team_list else "*No teams yet*",
        inline=False
    )

    # Add current moves section
    if builder.is_empty:
        embed.add_field(
            name="Current Moves",
            value="*No moves yet. Use the `/trade` commands to build your trade.*",
            inline=False
        )
    else:
        # Show cross-team moves
        if builder.trade.cross_team_moves:
            moves_text = ""
            for i, move in enumerate(builder.trade.cross_team_moves[:8], 1):  # Limit display
                moves_text += f"{i}. {move.description}\n"

            if len(builder.trade.cross_team_moves) > 8:
                moves_text += f"... and {len(builder.trade.cross_team_moves) - 8} more"

            embed.add_field(
                name=f"🔄 Player Exchanges ({len(builder.trade.cross_team_moves)})",
                value=moves_text,
                inline=False
            )

        # Show supplementary moves
        if builder.trade.supplementary_moves:
            supp_text = ""
            for i, move in enumerate(builder.trade.supplementary_moves[:5], 1):  # Limit display
                supp_text += f"{i}. {move.description}\n"

            if len(builder.trade.supplementary_moves) > 5:
                supp_text += f"... and {len(builder.trade.supplementary_moves) - 5} more"

            embed.add_field(
                name=f"⚙️ Supplementary Moves ({len(builder.trade.supplementary_moves)})",
                value=supp_text,
                inline=False
            )

    # Add quick validation summary
    validation = await builder.validate_trade()
    if validation.is_legal:
        status_text = "✅ Trade appears legal"
    else:
        error_count = len(validation.all_errors)
        status_text = f"❌ {error_count} error{'s' if error_count != 1 else ''} found"

    embed.add_field(
        name="🔍 Quick Status",
        value=status_text,
        inline=False
    )

    # Add instructions for adding more moves
    embed.add_field(
        name="➕ Build Your Trade",
        value="• `/trade add-player` - Add player exchanges\n• `/trade supplementary` - Add internal moves\n• `/trade add-team` - Add more teams",
        inline=False
    )

    # Add footer with trade ID and timestamp
    embed.set_footer(text=f"Trade ID: {builder.trade_id} • Created: {datetime.fromisoformat(builder.trade.created_at).strftime('%H:%M:%S')}")

    return embed