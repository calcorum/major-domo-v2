"""
Interactive Transaction Embed Views

Handles the Discord embed and button interfaces for the transaction builder.
"""
import discord
from typing import Optional, List
from datetime import datetime

from services.transaction_builder import TransactionBuilder, RosterValidationResult
from views.embeds import EmbedColors, EmbedTemplate
from utils.transaction_logging import post_transaction_to_log


class TransactionEmbedView(discord.ui.View):
    """Interactive view for the transaction builder embed."""

    def __init__(self, builder: TransactionBuilder, user_id: int, submission_handler: str = "scheduled", command_name: str = "/dropadd"):
        """
        Initialize the transaction embed view.

        Args:
            builder: TransactionBuilder instance
            user_id: Discord user ID (for permission checking)
            submission_handler: Type of submission ("scheduled" for /dropadd, "immediate" for /ilmove)
            command_name: Name of the command being used (for UI instructions)
        """
        super().__init__(timeout=900.0)  # 15 minute timeout
        self.builder = builder
        self.user_id = user_id
        self.submission_handler = submission_handler
        self.command_name = command_name
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to interact with this view."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ You don't have permission to use this transaction builder.",
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
        select_view = RemoveMoveView(self.builder, self.user_id, self.command_name)
        embed = await create_transaction_embed(self.builder, self.command_name)

        await interaction.response.edit_message(embed=embed, view=select_view)
    
    @discord.ui.button(label="Submit Transaction", style=discord.ButtonStyle.primary, emoji="📤")
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle submit transaction button click."""
        if self.builder.is_empty:
            await interaction.response.send_message(
                "❌ Cannot submit empty transaction. Add some moves first!",
                ephemeral=True
            )
            return
        
        # Validate before submission
        validation = await self.builder.validate_transaction()
        if not validation.is_legal:
            error_msg = "❌ **Cannot submit illegal transaction:**\n"
            error_msg += "\n".join([f"• {error}" for error in validation.errors])
            
            if validation.suggestions:
                error_msg += "\n\n**Suggestions:**\n"
                error_msg += "\n".join([f"💡 {suggestion}" for suggestion in validation.suggestions])
            
            await interaction.response.send_message(error_msg, ephemeral=True)
            return
        
        # Show confirmation modal
        modal = SubmitConfirmationModal(self.builder, self.submission_handler)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle cancel button click."""
        self.builder.clear_moves()
        embed = await create_transaction_embed(self.builder, self.command_name)

        # Disable all buttons after cancellation
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        await interaction.response.edit_message(
            content="❌ **Transaction cancelled and cleared.**",
            embed=embed,
            view=self
        )
        self.stop()


class RemoveMoveView(discord.ui.View):
    """View for selecting which move to remove."""

    def __init__(self, builder: TransactionBuilder, user_id: int, command_name: str = "/dropadd"):
        super().__init__(timeout=300.0)  # 5 minute timeout
        self.builder = builder
        self.user_id = user_id
        self.command_name = command_name

        # Create select menu with current moves
        if not builder.is_empty:
            self.add_item(RemoveMoveSelect(builder, command_name))

        # Add back button
        back_button = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, emoji="⬅️")
        back_button.callback = self.back_callback
        self.add_item(back_button)

    async def back_callback(self, interaction: discord.Interaction):
        """Handle back button to return to main view."""
        # Determine submission_handler from command_name
        submission_handler = "immediate" if self.command_name == "/ilmove" else "scheduled"
        main_view = TransactionEmbedView(self.builder, self.user_id, submission_handler, self.command_name)
        embed = await create_transaction_embed(self.builder, self.command_name)
        await interaction.response.edit_message(embed=embed, view=main_view)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to interact with this view."""
        return interaction.user.id == self.user_id


class RemoveMoveSelect(discord.ui.Select):
    """Select menu for choosing which move to remove."""

    def __init__(self, builder: TransactionBuilder, command_name: str = "/dropadd"):
        self.builder = builder
        self.command_name = command_name

        # Create options from current moves
        options = []
        for i, move in enumerate(builder.moves[:25]):  # Discord limit of 25 options
            options.append(discord.SelectOption(
                label=f"{move.player.name}",
                description=move.description[:100],  # Discord description limit
                value=str(move.player.id)
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
        move = self.builder.get_move_for_player(player_id)

        if move:
            self.builder.remove_move(player_id)
            await interaction.response.send_message(
                f"✅ Removed: {move.description}",
                ephemeral=True
            )

            # Update the embed
            # Determine submission_handler from command_name
            submission_handler = "immediate" if self.command_name == "/ilmove" else "scheduled"
            main_view = TransactionEmbedView(self.builder, interaction.user.id, submission_handler, self.command_name)
            embed = await create_transaction_embed(self.builder, self.command_name)

            # Edit the original message
            await interaction.edit_original_response(embed=embed, view=main_view)
        else:
            await interaction.response.send_message(
                "❌ Could not find that move to remove.",
                ephemeral=True
            )



class SubmitConfirmationModal(discord.ui.Modal):
    """Modal for confirming transaction submission."""

    def __init__(self, builder: TransactionBuilder, submission_handler: str = "scheduled"):
        super().__init__(title="Confirm Transaction Submission")
        self.builder = builder
        self.submission_handler = submission_handler
        
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
                "❌ Transaction not submitted. You must type 'CONFIRM' exactly.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from services.league_service import league_service
            from services.transaction_service import transaction_service
            from services.player_service import player_service

            # Get current league state
            current_state = await league_service.get_current_state()

            if not current_state:
                await interaction.followup.send(
                    "❌ Could not get current league state. Please try again later.",
                    ephemeral=True
                )
                return

            if self.submission_handler == "scheduled":
                # SCHEDULED SUBMISSION (/dropadd behavior)
                # Submit the transaction for NEXT week
                transactions = await self.builder.submit_transaction(week=current_state.week + 1)

                # Mark transactions as frozen for weekly processing
                for txn in transactions:
                    txn.frozen = True

                # POST transactions to database
                created_transactions = await transaction_service.create_transaction_batch(transactions)

                # Post to #transaction-log channel
                bot = interaction.client
                await post_transaction_to_log(bot, created_transactions, team=self.builder.team)

                # Create success message
                success_msg = f"✅ **Transaction Submitted Successfully!**\n\n"
                success_msg += f"**Move ID:** `{created_transactions[0].moveid}`\n"
                success_msg += f"**Moves:** {len(created_transactions)}\n"
                success_msg += f"**Effective Week:** {created_transactions[0].week}\n\n"

                success_msg += "**Transaction Details:**\n"
                for move in self.builder.moves:
                    success_msg += f"• {move.description}\n"

                success_msg += f"\n💡 Use `/mymoves` to check transaction status"

                await interaction.followup.send(success_msg, ephemeral=True)

            elif self.submission_handler == "immediate":
                # IMMEDIATE SUBMISSION (/ilmove behavior)
                # Submit the transaction for THIS week
                # Don't check existing transactions - they're already in DB and would cause double-counting
                transactions = await self.builder.submit_transaction(
                    week=current_state.week,
                    check_existing_transactions=False
                )

                # POST transactions to database
                created_transactions = await transaction_service.create_transaction_batch(transactions)

                # Update each player's team assignment
                player_updates = []
                for txn in created_transactions:
                    updated_player = await player_service.update_player_team(
                        txn.player.id,
                        txn.newteam.id
                    )
                    player_updates.append(updated_player)

                # Post to #transaction-log channel
                bot = interaction.client
                await post_transaction_to_log(bot, created_transactions, team=self.builder.team)

                # Create success message
                success_msg = f"✅ **IL Move Executed Successfully!**\n\n"
                success_msg += f"**Move ID:** `{created_transactions[0].moveid}`\n"
                success_msg += f"**Moves:** {len(created_transactions)}\n"
                success_msg += f"**Week:** {created_transactions[0].week} (Current)\n\n"

                success_msg += "**Executed Moves:**\n"
                for txn in created_transactions:
                    success_msg += f"• {txn.move_description}\n"

                success_msg += f"\n✅ **All players have been moved to their new teams immediately**"

                await interaction.followup.send(success_msg, ephemeral=True)

            # Clear the builder after successful submission
            from services.transaction_builder import clear_transaction_builder
            clear_transaction_builder(interaction.user.id)

            # Update the original embed to show completion
            completion_title = "✅ Transaction Submitted" if self.submission_handler == "scheduled" else "✅ IL Move Executed"
            completion_embed = discord.Embed(
                title=completion_title,
                description=f"Your transaction has been processed successfully!",
                color=0x00ff00
            )

            # Disable all buttons
            view = discord.ui.View()

            try:
                # Find and update the original message
                async for message in interaction.channel.history(limit=50): # type: ignore
                    if message.author == interaction.client.user and message.embeds:
                        if "Transaction Builder" in message.embeds[0].title: # type: ignore
                            await message.edit(embed=completion_embed, view=view)
                            break
            except:
                pass

        except Exception as e:
            await interaction.followup.send(
                f"❌ Error submitting transaction: {str(e)}",
                ephemeral=True
            )


async def create_transaction_embed(builder: TransactionBuilder, command_name: str = "/dropadd") -> discord.Embed:
    """
    Create the main transaction builder embed.

    Args:
        builder: TransactionBuilder instance
        command_name: Name of the command to use for adding more moves (default: "/dropadd")

    Returns:
        Discord embed with current transaction state
    """
    # Determine description based on command
    if command_name == "/ilmove":
        description = "Build your real-time roster move for this week"
    else:
        description = "Build your transaction for next week"

    embed = EmbedTemplate.create_base_embed(
        title=f"📋 Transaction Builder - {builder.team.abbrev}",
        description=description,
        color=EmbedColors.PRIMARY
    )
    
    # Add current moves section
    if builder.is_empty:
        embed.add_field(
            name="Current Moves",
            value="*No moves yet. Use the buttons below to build your transaction.*",
            inline=False
        )
    else:
        moves_text = ""
        for i, move in enumerate(builder.moves[:10], 1):  # Limit display
            moves_text += f"{i}. {move.description}\n"
        
        if len(builder.moves) > 10:
            moves_text += f"... and {len(builder.moves) - 10} more moves"
        
        embed.add_field(
            name=f"Current Moves ({builder.move_count})",
            value=moves_text,
            inline=False
        )
    
    # Add roster validation
    validation = await builder.validate_transaction()
    
    roster_status = f"{validation.major_league_status}\n{validation.minor_league_status}"
    
    embed.add_field(
        name="Roster Status",
        value=roster_status,
        inline=False
    )

    # Add sWAR status
    swar_status = f"{validation.major_league_swar_status}\n{validation.minor_league_swar_status}"
    embed.add_field(
        name="Team sWAR",
        value=swar_status,
        inline=False
    )

    # Add pre-existing transactions note if applicable
    if validation.pre_existing_transactions_note:
        embed.add_field(
            name="📋 Transaction Context",
            value=validation.pre_existing_transactions_note,
            inline=False
        )

    # Add suggestions/errors
    if validation.errors:
        error_text = "\n".join([f"• {error}" for error in validation.errors])
        embed.add_field(
            name="❌ Errors",
            value=error_text,
            inline=False
        )
    
    if validation.suggestions:
        suggestion_text = "\n".join([f"💡 {suggestion}" for suggestion in validation.suggestions])
        embed.add_field(
            name="Suggestions",
            value=suggestion_text,
            inline=False
        )

    # Add instructions for adding more moves
    embed.add_field(
        name="➕ Add More Moves",
        value=f"Use `{command_name}` to add more moves",
        inline=False
    )

    # Add footer with timestamp
    embed.set_footer(text=f"Created at {builder.created_at.strftime('%H:%M:%S')}")

    return embed


