"""
Interactive Trade Embed Views

Handles the Discord embed and button interfaces for the multi-team trade builder.
"""
import discord
from typing import Optional, List
from datetime import datetime, timezone

from services.trade_builder import TradeBuilder, TradeValidationResult
from models.team import Team, RosterType
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
    """Modal for confirming trade submission - posts acceptance request to trade channel."""

    def __init__(self, builder: TradeBuilder, trade_channel: Optional[discord.TextChannel] = None):
        super().__init__(title="Confirm Trade Submission")
        self.builder = builder
        self.trade_channel = trade_channel

        self.confirmation = discord.ui.TextInput(
            label="Type 'CONFIRM' to submit for approval",
            placeholder="CONFIRM",
            required=True,
            max_length=7
        )

        self.add_item(self.confirmation)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle confirmation submission - posts acceptance view to trade channel."""
        if self.confirmation.value.upper() != "CONFIRM":
            await interaction.response.send_message(
                "❌ Trade not submitted. You must type 'CONFIRM' exactly.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Update trade status to PROPOSED
            from models.trade import TradeStatus
            self.builder.trade.status = TradeStatus.PROPOSED

            # Create acceptance embed and view
            acceptance_embed = await create_trade_acceptance_embed(self.builder)
            acceptance_view = TradeAcceptanceView(self.builder)

            # Find the trade channel to post to
            channel = self.trade_channel
            if not channel:
                # Try to find trade channel by name pattern
                trade_channel_name = f"trade-{'-'.join(t.abbrev.lower() for t in self.builder.participating_teams)}"
                for ch in interaction.guild.text_channels:  # type: ignore
                    if ch.name.startswith("trade-") and self.builder.trade_id[:4] in ch.name:
                        channel = ch
                        break

            if channel:
                # Post acceptance request to trade channel
                await channel.send(
                    content="📋 **Trade submitted for approval!** All teams must accept to complete the trade.",
                    embed=acceptance_embed,
                    view=acceptance_view
                )
                await interaction.followup.send(
                    f"✅ Trade submitted for approval!\n\nThe acceptance request has been posted to {channel.mention}.\n"
                    f"All participating teams must click **Accept Trade** to finalize.",
                    ephemeral=True
                )
            else:
                # No trade channel found, post in current channel
                await interaction.followup.send(
                    content="📋 **Trade submitted for approval!** All teams must accept to complete the trade.",
                    embed=acceptance_embed,
                    view=acceptance_view
                )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Error submitting trade: {str(e)}",
                ephemeral=True
            )


class TradeAcceptanceView(discord.ui.View):
    """View for accepting or rejecting a proposed trade."""

    def __init__(self, builder: TradeBuilder):
        super().__init__(timeout=3600.0)  # 1 hour timeout
        self.builder = builder

    async def _get_user_team(self, interaction: discord.Interaction) -> Optional[Team]:
        """Get the team owned by the interacting user."""
        from services.team_service import team_service
        from config import get_config
        config = get_config()
        return await team_service.get_team_by_owner(interaction.user.id, config.sba_season)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user is a GM of a participating team."""
        user_team = await self._get_user_team(interaction)

        if not user_team:
            await interaction.response.send_message(
                "❌ You don't own a team in the league.",
                ephemeral=True
            )
            return False

        # Check if their team (or organization) is participating
        participant = self.builder.trade.get_participant_by_organization(user_team)
        if not participant:
            await interaction.response.send_message(
                "❌ Your team is not part of this trade.",
                ephemeral=True
            )
            return False

        return True

    async def on_timeout(self) -> None:
        """Handle view timeout - disable buttons but keep trade in memory."""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    @discord.ui.button(label="Accept Trade", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle accept button click."""
        user_team = await self._get_user_team(interaction)
        if not user_team:
            return

        # Find the participating team (could be org affiliate)
        participant = self.builder.trade.get_participant_by_organization(user_team)
        if not participant:
            return

        team_id = participant.team.id

        # Check if already accepted
        if self.builder.has_team_accepted(team_id):
            await interaction.response.send_message(
                f"✅ {participant.team.abbrev} has already accepted this trade.",
                ephemeral=True
            )
            return

        # Record acceptance
        all_accepted = self.builder.accept_trade(team_id)

        if all_accepted:
            # All teams accepted - finalize the trade
            await self._finalize_trade(interaction)
        else:
            # Update embed to show new acceptance status
            embed = await create_trade_acceptance_embed(self.builder)
            await interaction.response.edit_message(embed=embed, view=self)

            # Send confirmation to channel
            await interaction.followup.send(
                f"✅ **{participant.team.abbrev}** has accepted the trade! "
                f"({len(self.builder.accepted_teams)}/{self.builder.team_count} teams)"
            )

    @discord.ui.button(label="Reject Trade", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle reject button click - moves trade back to DRAFT."""
        user_team = await self._get_user_team(interaction)
        if not user_team:
            return

        participant = self.builder.trade.get_participant_by_organization(user_team)
        if not participant:
            return

        # Reject the trade
        self.builder.reject_trade()

        # Disable buttons
        self.accept_button.disabled = True
        self.reject_button.disabled = True

        # Update embed to show rejection
        embed = await create_trade_rejection_embed(self.builder, participant.team)
        await interaction.response.edit_message(embed=embed, view=self)

        # Notify the channel
        await interaction.followup.send(
            f"❌ **{participant.team.abbrev}** has rejected the trade.\n\n"
            f"The trade has been moved back to **DRAFT** status. "
            f"Teams can continue negotiating using `/trade` commands."
        )

        self.stop()

    async def _finalize_trade(self, interaction: discord.Interaction) -> None:
        """Finalize the trade - create transactions and complete."""
        from services.league_service import league_service
        from services.transaction_service import transaction_service
        from services.trade_builder import clear_trade_builder_by_team
        from models.transaction import Transaction
        from models.trade import TradeStatus
        from utils.transaction_logging import post_trade_to_log
        from config import get_config

        try:
            await interaction.response.defer()

            config = get_config()

            # Get next week for transactions
            current = await league_service.get_current_state()
            next_week = current.week + 1 if current else 1

            # Create FA team for reference
            fa_team = Team(
                id=config.free_agent_team_id,
                abbrev="FA",
                sname="Free Agents",
                lname="Free Agency",
                season=self.builder.trade.season
            )  # type: ignore

            # Create transactions from all moves
            transactions: List[Transaction] = []
            move_id = f"Trade-{self.builder.trade_id}-{int(datetime.now(timezone.utc).timestamp())}"

            # Process cross-team moves
            for move in self.builder.trade.cross_team_moves:
                # Get actual team affiliates for from/to based on roster type
                if move.from_roster == RosterType.MAJOR_LEAGUE:
                    old_team = move.source_team
                elif move.from_roster == RosterType.MINOR_LEAGUE:
                    old_team = await move.source_team.minor_league_affiliate() if move.source_team else None
                elif move.from_roster == RosterType.INJURED_LIST:
                    old_team = await move.source_team.injured_list_affiliate() if move.source_team else None
                else:
                    old_team = move.source_team

                if move.to_roster == RosterType.MAJOR_LEAGUE:
                    new_team = move.destination_team
                elif move.to_roster == RosterType.MINOR_LEAGUE:
                    new_team = await move.destination_team.minor_league_affiliate() if move.destination_team else None
                elif move.to_roster == RosterType.INJURED_LIST:
                    new_team = await move.destination_team.injured_list_affiliate() if move.destination_team else None
                else:
                    new_team = move.destination_team

                if old_team and new_team:
                    transaction = Transaction(
                        id=0,
                        week=next_week,
                        season=self.builder.trade.season,
                        moveid=move_id,
                        player=move.player,
                        oldteam=old_team,
                        newteam=new_team,
                        cancelled=False,
                        frozen=False  # Trades are NOT frozen - immediately effective
                    )
                    transactions.append(transaction)

            # Process supplementary moves
            for move in self.builder.trade.supplementary_moves:
                if move.from_roster == RosterType.MAJOR_LEAGUE:
                    old_team = move.source_team
                elif move.from_roster == RosterType.MINOR_LEAGUE:
                    old_team = await move.source_team.minor_league_affiliate() if move.source_team else None
                elif move.from_roster == RosterType.INJURED_LIST:
                    old_team = await move.source_team.injured_list_affiliate() if move.source_team else None
                elif move.from_roster == RosterType.FREE_AGENCY:
                    old_team = fa_team
                else:
                    old_team = move.source_team

                if move.to_roster == RosterType.MAJOR_LEAGUE:
                    new_team = move.destination_team
                elif move.to_roster == RosterType.MINOR_LEAGUE:
                    new_team = await move.destination_team.minor_league_affiliate() if move.destination_team else None
                elif move.to_roster == RosterType.INJURED_LIST:
                    new_team = await move.destination_team.injured_list_affiliate() if move.destination_team else None
                elif move.to_roster == RosterType.FREE_AGENCY:
                    new_team = fa_team
                else:
                    new_team = move.destination_team

                if old_team and new_team:
                    transaction = Transaction(
                        id=0,
                        week=next_week,
                        season=self.builder.trade.season,
                        moveid=move_id,
                        player=move.player,
                        oldteam=old_team,
                        newteam=new_team,
                        cancelled=False,
                        frozen=False  # Trades are NOT frozen - immediately effective
                    )
                    transactions.append(transaction)

            # POST transactions to database
            if transactions:
                created_transactions = await transaction_service.create_transaction_batch(transactions)
            else:
                created_transactions = []

            # Post to #transaction-log channel
            if created_transactions and interaction.client:
                await post_trade_to_log(
                    bot=interaction.client,
                    builder=self.builder,
                    transactions=created_transactions,
                    effective_week=next_week
                )

            # Update trade status
            self.builder.trade.status = TradeStatus.ACCEPTED

            # Disable buttons
            self.accept_button.disabled = True
            self.reject_button.disabled = True

            # Update embed to show completion
            embed = await create_trade_complete_embed(self.builder, len(created_transactions), next_week)
            await interaction.edit_original_response(embed=embed, view=self)

            # Send completion message
            await interaction.followup.send(
                f"🎉 **Trade Complete!**\n\n"
                f"All {self.builder.team_count} teams have accepted the trade.\n"
                f"**{len(created_transactions)} transactions** have been created for **Week {next_week}**.\n\n"
                f"Trade ID: `{self.builder.trade_id}`"
            )

            # Clear the trade builder
            for team in self.builder.participating_teams:
                clear_trade_builder_by_team(team.id)

            self.stop()

        except Exception as e:
            await interaction.followup.send(
                f"❌ Error finalizing trade: {str(e)}",
                ephemeral=True
            )


async def create_trade_acceptance_embed(builder: TradeBuilder) -> discord.Embed:
    """Create embed showing trade details and acceptance status."""
    embed = EmbedTemplate.create_base_embed(
        title=f"📋 Trade Pending Acceptance - {builder.trade.get_trade_summary()}",
        description="All participating teams must accept to complete the trade.",
        color=EmbedColors.WARNING
    )

    # Show participating teams
    team_list = [f"• {team.abbrev} - {team.sname}" for team in builder.participating_teams]
    embed.add_field(
        name=f"🏟️ Participating Teams ({builder.team_count})",
        value="\n".join(team_list),
        inline=False
    )

    # Show cross-team moves
    if builder.trade.cross_team_moves:
        moves_text = ""
        for move in builder.trade.cross_team_moves[:10]:
            moves_text += f"• {move.description}\n"
        if len(builder.trade.cross_team_moves) > 10:
            moves_text += f"... and {len(builder.trade.cross_team_moves) - 10} more"
        embed.add_field(
            name=f"🔄 Player Exchanges ({len(builder.trade.cross_team_moves)})",
            value=moves_text,
            inline=False
        )

    # Show supplementary moves if any
    if builder.trade.supplementary_moves:
        supp_text = ""
        for move in builder.trade.supplementary_moves[:5]:
            supp_text += f"• {move.description}\n"
        if len(builder.trade.supplementary_moves) > 5:
            supp_text += f"... and {len(builder.trade.supplementary_moves) - 5} more"
        embed.add_field(
            name=f"⚙️ Supplementary Moves ({len(builder.trade.supplementary_moves)})",
            value=supp_text,
            inline=False
        )

    # Show acceptance status
    status_lines = []
    for team in builder.participating_teams:
        if team.id in builder.accepted_teams:
            status_lines.append(f"✅ **{team.abbrev}** - Accepted")
        else:
            status_lines.append(f"⏳ **{team.abbrev}** - Pending")

    embed.add_field(
        name="📊 Acceptance Status",
        value="\n".join(status_lines),
        inline=False
    )

    # Add footer
    embed.set_footer(text=f"Trade ID: {builder.trade_id} • {len(builder.accepted_teams)}/{builder.team_count} teams accepted")

    return embed


async def create_trade_rejection_embed(builder: TradeBuilder, rejecting_team: Team) -> discord.Embed:
    """Create embed showing trade was rejected."""
    embed = EmbedTemplate.create_base_embed(
        title=f"❌ Trade Rejected - {builder.trade.get_trade_summary()}",
        description=f"**{rejecting_team.abbrev}** has rejected the trade.\n\n"
                    f"The trade has been moved back to **DRAFT** status.\n"
                    f"Teams can continue negotiating using `/trade` commands.",
        color=EmbedColors.ERROR
    )

    embed.set_footer(text=f"Trade ID: {builder.trade_id}")

    return embed


async def create_trade_complete_embed(builder: TradeBuilder, transaction_count: int, effective_week: int) -> discord.Embed:
    """Create embed showing trade was completed."""
    embed = EmbedTemplate.create_base_embed(
        title=f"🎉 Trade Complete! - {builder.trade.get_trade_summary()}",
        description=f"All {builder.team_count} teams have accepted the trade!\n\n"
                    f"**{transaction_count} transactions** created for **Week {effective_week}**.",
        color=EmbedColors.SUCCESS
    )

    # Show final acceptance status (all green)
    status_lines = [f"✅ **{team.abbrev}** - Accepted" for team in builder.participating_teams]
    embed.add_field(
        name="📊 Final Status",
        value="\n".join(status_lines),
        inline=False
    )

    # Show cross-team moves
    if builder.trade.cross_team_moves:
        moves_text = ""
        for move in builder.trade.cross_team_moves[:8]:
            moves_text += f"• {move.description}\n"
        if len(builder.trade.cross_team_moves) > 8:
            moves_text += f"... and {len(builder.trade.cross_team_moves) - 8} more"
        embed.add_field(
            name=f"🔄 Player Exchanges",
            value=moves_text,
            inline=False
        )

    embed.set_footer(text=f"Trade ID: {builder.trade_id} • Effective: Week {effective_week}")

    return embed


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