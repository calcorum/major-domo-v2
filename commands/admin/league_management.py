"""
Admin League Management Commands

Administrative commands for manual control of league state and transaction processing.
Provides manual override capabilities for the automated freeze/thaw system.
"""
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from config import get_config
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.permissions import league_admin_only
from views.embeds import EmbedColors, EmbedTemplate
from services.league_service import league_service
from services.transaction_service import transaction_service
from tasks.transaction_freeze import resolve_contested_transactions


class LeagueManagementCommands(commands.Cog):
    """Administrative commands for league state and transaction management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.LeagueManagementCommands')

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need administrator permissions to use admin commands.",
                ephemeral=True
            )
            return False
        return True

    @app_commands.command(
        name="admin-freeze-begin",
        description="[ADMIN] Manually trigger freeze begin (increment week, set freeze)"
    )
    @league_admin_only()
    @logged_command("/admin-freeze-begin")
    async def admin_freeze_begin(self, interaction: discord.Interaction):
        """Manually trigger the freeze begin process."""
        await interaction.response.defer()

        # Get current state
        current = await league_service.get_current_state()
        if not current:
            await interaction.followup.send(
                "❌ Could not retrieve current league state.",
                ephemeral=True
            )
            return

        # Check if already frozen
        if current.freeze:
            embed = EmbedTemplate.warning(
                title="Already Frozen",
                description=f"League is already in freeze period for week {current.week}."
            )
            embed.add_field(
                name="Current State",
                value=f"**Week:** {current.week}\n**Freeze:** {current.freeze}\n**Season:** {current.season}",
                inline=False
            )
            await interaction.followup.send(embed=embed)
            return

        # Increment week and set freeze
        new_week = current.week + 1
        updated = await league_service.update_current_state(
            week=new_week,
            freeze=True
        )

        if not updated:
            await interaction.followup.send(
                "❌ Failed to update league state.",
                ephemeral=True
            )
            return

        # Create success embed
        embed = EmbedTemplate.success(
            title="Freeze Period Begun",
            description=f"Manually triggered freeze begin for week {new_week}."
        )

        embed.add_field(
            name="Previous State",
            value=f"**Week:** {current.week}\n**Freeze:** {current.freeze}",
            inline=True
        )

        embed.add_field(
            name="New State",
            value=f"**Week:** {new_week}\n**Freeze:** True",
            inline=True
        )

        embed.add_field(
            name="Actions Performed",
            value="✅ Week incremented\n✅ Freeze flag set to True",
            inline=False
        )

        embed.add_field(
            name="⚠️ Manual Steps Required",
            value="• Post freeze announcement to #transaction-log\n"
                  "• Post weekly info to #weekly-info (if weeks 1-18)\n"
                  "• Run regular transactions if needed",
            inline=False
        )

        embed.set_footer(text=f"Triggered by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="admin-freeze-end",
        description="[ADMIN] Manually trigger freeze end (process transactions, unfreeze)"
    )
    @league_admin_only()
    @logged_command("/admin-freeze-end")
    async def admin_freeze_end(self, interaction: discord.Interaction):
        """Manually trigger the freeze end process."""
        await interaction.response.defer()

        # Get current state
        current = await league_service.get_current_state()
        if not current:
            await interaction.followup.send(
                "❌ Could not retrieve current league state.",
                ephemeral=True
            )
            return

        # Check if currently frozen
        if not current.freeze:
            embed = EmbedTemplate.warning(
                title="Not Frozen",
                description=f"League is not currently in freeze period (week {current.week})."
            )
            embed.add_field(
                name="Current State",
                value=f"**Week:** {current.week}\n**Freeze:** {current.freeze}\n**Season:** {current.season}",
                inline=False
            )
            await interaction.followup.send(embed=embed)
            return

        # Process frozen transactions
        processing_msg = await interaction.followup.send(
            "⏳ Processing frozen transactions...",
            wait=True
        )

        # Get frozen transactions
        transactions = await transaction_service.get_frozen_transactions_by_week(
            season=current.season,
            week_start=current.week,
            week_end=current.week + 1
        )

        winning_count = 0
        losing_count = 0

        if transactions:
            # Resolve contested transactions
            winning_move_ids, losing_move_ids = await resolve_contested_transactions(
                transactions,
                current.season
            )

            # Cancel losing transactions (one API call per moveid, updates all transactions in group)
            for losing_move_id in losing_move_ids:
                await transaction_service.cancel_transaction(losing_move_id)
                losing_count += 1

            # Unfreeze winning transactions (one API call per moveid, updates all transactions in group)
            for winning_move_id in winning_move_ids:
                await transaction_service.unfreeze_transaction(winning_move_id)
                winning_count += 1

        # Update processing message
        await processing_msg.edit(content="⏳ Updating league state...")

        # Set freeze to False
        updated = await league_service.update_current_state(freeze=False)

        if not updated:
            await interaction.followup.send(
                "❌ Failed to update league state after processing transactions.",
                ephemeral=True
            )
            return

        # Create success embed
        embed = EmbedTemplate.success(
            title="Freeze Period Ended",
            description=f"Manually triggered freeze end for week {current.week}."
        )

        embed.add_field(
            name="Transaction Processing",
            value=f"**Total Transactions:** {len(transactions) if transactions else 0}\n"
                  f"**Successful:** {winning_count}\n"
                  f"**Cancelled:** {losing_count}",
            inline=True
        )

        embed.add_field(
            name="League State",
            value=f"**Week:** {current.week}\n"
                  f"**Freeze:** False\n"
                  f"**Season:** {current.season}",
            inline=True
        )

        embed.add_field(
            name="Actions Performed",
            value=f"✅ Processed {len(transactions) if transactions else 0} frozen transactions\n"
                  f"✅ Resolved contested players\n"
                  f"✅ Freeze flag set to False",
            inline=False
        )

        if transactions:
            embed.add_field(
                name="⚠️ Manual Steps Required",
                value="• Post thaw announcement to #transaction-log\n"
                      "• Notify GMs of cancelled transactions\n"
                      "• Post successful transactions to #transaction-log",
                inline=False
            )

        embed.set_footer(text=f"Triggered by {interaction.user.display_name}")

        # Edit the processing message to show final results instead of deleting and sending new
        await processing_msg.edit(content=None, embed=embed)

    @app_commands.command(
        name="admin-set-week",
        description="[ADMIN] Manually set the current league week"
    )
    @app_commands.describe(
        week="Week number to set (1-24)"
    )
    @league_admin_only()
    @logged_command("/admin-set-week")
    async def admin_set_week(self, interaction: discord.Interaction, week: int):
        """Manually set the current league week."""
        await interaction.response.defer()

        # Validate week number
        if week < 1 or week > 24:
            await interaction.followup.send(
                "❌ Week number must be between 1 and 24.",
                ephemeral=True
            )
            return

        # Get current state
        current = await league_service.get_current_state()
        if not current:
            await interaction.followup.send(
                "❌ Could not retrieve current league state.",
                ephemeral=True
            )
            return

        # Update week
        updated = await league_service.update_current_state(week=week)

        if not updated:
            await interaction.followup.send(
                "❌ Failed to update league week.",
                ephemeral=True
            )
            return

        # Create success embed
        embed = EmbedTemplate.success(
            title="League Week Updated",
            description=f"Manually set league week to {week}."
        )

        embed.add_field(
            name="Previous Week",
            value=f"**Week:** {current.week}",
            inline=True
        )

        embed.add_field(
            name="New Week",
            value=f"**Week:** {week}",
            inline=True
        )

        embed.add_field(
            name="Current State",
            value=f"**Season:** {current.season}\n"
                  f"**Freeze:** {current.freeze}\n"
                  f"**Trade Deadline:** Week {current.trade_deadline}\n"
                  f"**Playoffs Begin:** Week {current.playoffs_begin}",
            inline=False
        )

        embed.add_field(
            name="⚠️ Warning",
            value="Manual week changes bypass automated freeze/thaw processes.\n"
                  "Ensure you run appropriate admin commands for transaction management.",
            inline=False
        )

        embed.set_footer(text=f"Changed by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="admin-set-freeze",
        description="[ADMIN] Manually toggle freeze status"
    )
    @app_commands.describe(
        freeze="True to freeze transactions, False to unfreeze"
    )
    @app_commands.choices(freeze=[
        app_commands.Choice(name="Freeze (True)", value=1),
        app_commands.Choice(name="Unfreeze (False)", value=0)
    ])
    @league_admin_only()
    @logged_command("/admin-set-freeze")
    async def admin_set_freeze(self, interaction: discord.Interaction, freeze: int):
        """Manually toggle the freeze status."""
        await interaction.response.defer()

        freeze_bool = bool(freeze)

        # Get current state
        current = await league_service.get_current_state()
        if not current:
            await interaction.followup.send(
                "❌ Could not retrieve current league state.",
                ephemeral=True
            )
            return

        # Check if already in desired state
        if current.freeze == freeze_bool:
            status = "frozen" if freeze_bool else "unfrozen"
            embed = EmbedTemplate.warning(
                title="No Change Needed",
                description=f"League is already {status}."
            )
            embed.add_field(
                name="Current State",
                value=f"**Week:** {current.week}\n**Freeze:** {current.freeze}\n**Season:** {current.season}",
                inline=False
            )
            await interaction.followup.send(embed=embed)
            return

        # Update freeze status
        updated = await league_service.update_current_state(freeze=freeze_bool)

        if not updated:
            await interaction.followup.send(
                "❌ Failed to update freeze status.",
                ephemeral=True
            )
            return

        # Create success embed
        action = "Frozen" if freeze_bool else "Unfrozen"
        embed = EmbedTemplate.success(
            title=f"Transactions {action}",
            description=f"Manually set freeze status to {freeze_bool}."
        )

        embed.add_field(
            name="Previous Status",
            value=f"**Freeze:** {current.freeze}",
            inline=True
        )

        embed.add_field(
            name="New Status",
            value=f"**Freeze:** {freeze_bool}",
            inline=True
        )

        embed.add_field(
            name="Current State",
            value=f"**Week:** {current.week}\n**Season:** {current.season}",
            inline=False
        )

        if freeze_bool:
            embed.add_field(
                name="⚠️ Note",
                value="Transactions are now frozen. Use `/admin-freeze-end` to process frozen transactions.",
                inline=False
            )
        else:
            embed.add_field(
                name="⚠️ Warning",
                value="Manual freeze toggle bypasses transaction processing.\n"
                      "Ensure frozen transactions were processed before unfreezing.",
                inline=False
            )

        embed.set_footer(text=f"Changed by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="admin-process-freeze",
        description="[ADMIN] Manually process frozen transactions without changing freeze status"
    )
    @app_commands.describe(
        week="Week to process transactions for (defaults to current week)",
        dry_run="Preview results without making changes (default: False)"
    )
    @league_admin_only()
    @logged_command("/admin-process-freeze")
    async def admin_process_transactions(
        self,
        interaction: discord.Interaction,
        week: Optional[int] = None,
        dry_run: bool = False
    ):
        """Manually process frozen transactions for a specific week."""
        await interaction.response.defer()

        # Get current state
        current = await league_service.get_current_state()
        if not current:
            await interaction.followup.send(
                "❌ Could not retrieve current league state.",
                ephemeral=True
            )
            return

        # Use provided week or current week
        target_week = week if week is not None else current.week

        # Validate week
        if target_week < 1 or target_week > 24:
            await interaction.followup.send(
                "❌ Week number must be between 1 and 24.",
                ephemeral=True
            )
            return

        # Send processing message
        mode_text = " (DRY RUN - No changes will be made)" if dry_run else ""
        processing_msg = await interaction.followup.send(
            f"⏳ Processing frozen transactions for week {target_week}{mode_text}...",
            wait=True
        )

        # Get frozen transactions for the week
        transactions = await transaction_service.get_frozen_transactions_by_week(
            season=current.season,
            week_start=target_week,
            week_end=target_week + 1
        )

        if not transactions:
            await processing_msg.edit(
                content=f"ℹ️ No frozen transactions found for week {target_week}."
            )
            return

        # Resolve contested transactions
        winning_move_ids, losing_move_ids = await resolve_contested_transactions(
            transactions,
            current.season
        )

        # Process transactions (unless dry run)
        if not dry_run:
            # Cancel losing transactions (one API call per moveid, updates all transactions in group)
            for losing_move_id in losing_move_ids:
                await transaction_service.cancel_transaction(losing_move_id)

            # Unfreeze winning transactions (one API call per moveid, updates all transactions in group)
            for winning_move_id in winning_move_ids:
                await transaction_service.unfreeze_transaction(winning_move_id)

        # Create detailed results embed
        if dry_run:
            embed = EmbedTemplate.info(
                title="Transaction Processing Preview",
                description=f"Dry run results for week {target_week} (no changes made)."
            )
        else:
            embed = EmbedTemplate.success(
                title="Transactions Processed",
                description=f"Successfully processed frozen transactions for week {target_week}."
            )

        embed.add_field(
            name="Transaction Summary",
            value=f"**Total Frozen:** {len(transactions)}\n"
                  f"**Successful:** {len(winning_move_ids)}\n"
                  f"**Cancelled:** {len(losing_move_ids)}",
            inline=True
        )

        embed.add_field(
            name="Processing Details",
            value=f"**Week:** {target_week}\n"
                  f"**Season:** {current.season}\n"
                  f"**Mode:** {'Dry Run' if dry_run else 'Live'}",
            inline=True
        )

        # Show contested transactions
        if losing_move_ids:
            contested_info = []
            for losing_move_id in losing_move_ids:
                losing_moves = [t for t in transactions if t.moveid == losing_move_id]
                if losing_moves:
                    player_name = losing_moves[0].player.name
                    team_abbrev = losing_moves[0].newteam.abbrev
                    contested_info.append(f"• {player_name} ({team_abbrev} - cancelled)")

            if contested_info:
                # Limit to first 10 contested transactions
                display_info = contested_info[:10]
                if len(contested_info) > 10:
                    display_info.append(f"... and {len(contested_info) - 10} more")

                embed.add_field(
                    name="Contested Transactions",
                    value="\n".join(display_info),
                    inline=False
                )

        # Add warnings
        if dry_run:
            embed.add_field(
                name="ℹ️ Dry Run Mode",
                value="No transactions were modified. Run without `dry_run` parameter to apply changes.",
                inline=False
            )
        else:
            embed.add_field(
                name="⚠️ Manual Steps Required",
                value="• Notify GMs of cancelled transactions\n"
                      "• Post successful transactions to #transaction-log\n"
                      "• Verify all transactions processed correctly",
                inline=False
            )

        embed.set_footer(text=f"Processed by {interaction.user.display_name}")

        # Edit the processing message to show final results instead of deleting and sending new
        await processing_msg.edit(content=None, embed=embed)


async def setup(bot: commands.Bot):
    """Load the league management commands cog."""
    await bot.add_cog(LeagueManagementCommands(bot))
