"""
Transaction Management Commands

Core transaction commands for roster management and transaction tracking.
"""
from typing import Optional
import asyncio

import discord
from discord.ext import commands
from discord import app_commands

from config import get_config
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.team_utils import get_user_major_league_team
from views.embeds import EmbedColors, EmbedTemplate
from views.base import PaginationView

from services.transaction_service import transaction_service
from services.roster_service import roster_service
from services.team_service import team_service
# No longer need TransactionStatus enum


class TransactionPaginationView(PaginationView):
    """Custom pagination view with Show Move IDs button."""

    def __init__(
        self,
        *,
        pages: list[discord.Embed],
        all_transactions: list,
        user_id: int,
        timeout: float = 300.0,
        show_page_numbers: bool = True
    ):
        super().__init__(
            pages=pages,
            user_id=user_id,
            timeout=timeout,
            show_page_numbers=show_page_numbers
        )
        self.all_transactions = all_transactions

    @discord.ui.button(label="Show Move IDs", style=discord.ButtonStyle.secondary, emoji="🔍", row=1)
    async def show_move_ids(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show all move IDs in an ephemeral message."""
        self.increment_interaction_count()

        if not self.all_transactions:
            await interaction.response.send_message(
                "No transactions to show.",
                ephemeral=True
            )
            return

        # Build the move ID list
        header = "📋 **Move IDs for Your Transactions**\n"
        lines = []

        for transaction in self.all_transactions:
            lines.append(
                f"• Week {transaction.week}: {transaction.player.name} → `{transaction.moveid}`"
            )

        # Discord has a 2000 character limit for messages
        # Chunk messages to stay under the limit
        messages = []
        current_message = header

        for line in lines:
            # Check if adding this line would exceed limit (leave 50 char buffer)
            if len(current_message) + len(line) + 1 > 1950:
                messages.append(current_message)
                current_message = line + "\n"
            else:
                current_message += line + "\n"

        # Add the last message if it has content beyond the header
        if current_message.strip() != header.strip():
            messages.append(current_message)

        # Send the messages
        if not messages:
            await interaction.response.send_message(
                "No transactions to display.",
                ephemeral=True
            )
            return

        # Send first message as response
        await interaction.response.send_message(messages[0], ephemeral=True)

        # Send remaining messages as followups
        if len(messages) > 1:
            for msg in messages[1:]:
                await interaction.followup.send(msg, ephemeral=True)


class TransactionCommands(commands.Cog):
    """Transaction command handlers for roster management."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.TransactionCommands')
    
    @app_commands.command(
        name="mymoves",
        description="View your pending and scheduled transactions"
    )
    @app_commands.describe(
        show_cancelled="Include cancelled transactions in the display (default: False)"
    )
    @logged_command("/mymoves")
    async def my_moves(
        self, 
        interaction: discord.Interaction,
        show_cancelled: bool = False
    ):
        """Display user's transaction status and history."""
        await interaction.response.defer()
        
        # Get user's team
        team = await get_user_major_league_team(interaction.user.id, get_config().sba_current_season)
        
        if not team:
            await interaction.followup.send(
                "❌ You don't appear to own a team in the current season.",
                ephemeral=True
            )
            return
        
        # Get transactions in parallel
        pending_task = transaction_service.get_pending_transactions(team.abbrev, get_config().sba_current_season)
        frozen_task = transaction_service.get_frozen_transactions(team.abbrev, get_config().sba_current_season) 
        processed_task = transaction_service.get_processed_transactions(team.abbrev, get_config().sba_current_season)
        
        pending_transactions = await pending_task
        frozen_transactions = await frozen_task
        processed_transactions = await processed_task
        
        # Get cancelled if requested
        cancelled_transactions = []
        if show_cancelled:
            cancelled_transactions = await transaction_service.get_team_transactions(
                team.abbrev,
                get_config().sba_current_season,
                cancelled=True
            )

        pages = self._create_my_moves_pages(
            team,
            pending_transactions,
            frozen_transactions,
            processed_transactions,
            cancelled_transactions
        )

        # Collect all transactions for the "Show Move IDs" button
        all_transactions = (
            pending_transactions +
            frozen_transactions +
            processed_transactions +
            cancelled_transactions
        )

        # If only one page and no transactions, send without any buttons
        if len(pages) == 1 and not all_transactions:
            await interaction.followup.send(embed=pages[0])
        else:
            # Use custom pagination view with "Show Move IDs" button
            view = TransactionPaginationView(
                pages=pages,
                all_transactions=all_transactions,
                user_id=interaction.user.id,
                timeout=300.0,
                show_page_numbers=True
            )
            await interaction.followup.send(embed=view.get_current_embed(), view=view)
    
    @app_commands.command(
        name="legal",
        description="Check roster legality for current and next week"
    )
    @app_commands.describe(
        team="Team abbreviation to check (defaults to your team)"
    )
    @logged_command("/legal")
    async def legal(
        self,
        interaction: discord.Interaction,
        team: Optional[str] = None
    ):
        """Check roster legality and display detailed validation results."""
        await interaction.response.defer()
        
        # Get target team
        if team:
            target_team = await team_service.get_team_by_abbrev(team.upper(), get_config().sba_current_season)
            if not target_team:
                await interaction.followup.send(
                    f"❌ Could not find team '{team}' in season {get_config().sba_current_season}.",
                    ephemeral=True
                )
                return
        else:
            # Get user's team
            user_teams = await team_service.get_teams_by_owner(interaction.user.id, get_config().sba_current_season)
            if not user_teams:
                await interaction.followup.send(
                    "❌ You don't appear to own a team. Please specify a team abbreviation.",
                    ephemeral=True
                )
                return
            target_team = user_teams[0]
        
        # Get rosters in parallel
        current_roster, next_roster = await asyncio.gather(
            roster_service.get_current_roster(target_team.id),
            roster_service.get_next_roster(target_team.id)
        )
        
        if not current_roster and not next_roster:
            await interaction.followup.send(
                f"❌ Could not retrieve roster data for {target_team.abbrev}.",
                ephemeral=True
            )
            return
        
        # Validate rosters in parallel
        validation_tasks = []
        if current_roster:
            validation_tasks.append(roster_service.validate_roster(current_roster))
        else:
            validation_tasks.append(asyncio.create_task(asyncio.sleep(0)))  # Dummy task
        
        if next_roster:
            validation_tasks.append(roster_service.validate_roster(next_roster))
        else:
            validation_tasks.append(asyncio.create_task(asyncio.sleep(0)))  # Dummy task
        
        validation_results = await asyncio.gather(*validation_tasks)
        current_validation = validation_results[0] if current_roster else None
        next_validation = validation_results[1] if next_roster else None
        
        embed = await self._create_legal_embed(
            target_team,
            current_roster,
            next_roster, 
            current_validation,
            next_validation
        )
        
        await interaction.followup.send(embed=embed)
    
    def _create_my_moves_pages(
        self,
        team,
        pending_transactions,
        frozen_transactions,
        processed_transactions,
        cancelled_transactions
    ) -> list[discord.Embed]:
        """Create paginated embeds showing user's transaction status."""

        pages = []
        transactions_per_page = 10

        # Helper function to create transaction lines without emojis
        def format_transaction(transaction):
            return f"Week {transaction.week}: {transaction.move_description}"

        # Page 1: Summary + Pending Transactions
        if pending_transactions:
            total_pending = len(pending_transactions)
            total_pages = (total_pending + transactions_per_page - 1) // transactions_per_page

            for page_num in range(total_pages):
                start_idx = page_num * transactions_per_page
                end_idx = min(start_idx + transactions_per_page, total_pending)
                page_transactions = pending_transactions[start_idx:end_idx]

                embed = EmbedTemplate.create_base_embed(
                    title=f"📋 Transaction Status - {team.abbrev}",
                    description=f"{team.lname} • Season {get_config().sba_current_season}",
                    color=EmbedColors.INFO
                )

                # Add team thumbnail if available
                if hasattr(team, 'thumbnail') and team.thumbnail:
                    embed.set_thumbnail(url=team.thumbnail)

                # Pending transactions for this page
                pending_lines = [format_transaction(tx) for tx in page_transactions]

                embed.add_field(
                    name=f"⏳ Pending Transactions ({total_pending} total)",
                    value="\n".join(pending_lines),
                    inline=False
                )

                # Add summary only on first page
                if page_num == 0:
                    total_frozen = len(frozen_transactions)
                    status_text = []
                    if total_pending > 0:
                        status_text.append(f"{total_pending} pending")
                    if total_frozen > 0:
                        status_text.append(f"{total_frozen} scheduled")

                    embed.add_field(
                        name="Summary",
                        value=", ".join(status_text) if status_text else "No active transactions",
                        inline=True
                    )

                pages.append(embed)
        else:
            # No pending transactions - create single page
            embed = EmbedTemplate.create_base_embed(
                title=f"📋 Transaction Status - {team.abbrev}",
                description=f"{team.lname} • Season {get_config().sba_current_season}",
                color=EmbedColors.INFO
            )

            if hasattr(team, 'thumbnail') and team.thumbnail:
                embed.set_thumbnail(url=team.thumbnail)

            embed.add_field(
                name="⏳ Pending Transactions",
                value="No pending transactions",
                inline=False
            )

            total_frozen = len(frozen_transactions)
            status_text = []
            if total_frozen > 0:
                status_text.append(f"{total_frozen} scheduled")

            embed.add_field(
                name="Summary",
                value=", ".join(status_text) if status_text else "No active transactions",
                inline=True
            )

            pages.append(embed)

        # Additional page: Frozen transactions
        if frozen_transactions:
            embed = EmbedTemplate.create_base_embed(
                title=f"📋 Transaction Status - {team.abbrev}",
                description=f"{team.lname} • Season {get_config().sba_current_season}",
                color=EmbedColors.INFO
            )

            if hasattr(team, 'thumbnail') and team.thumbnail:
                embed.set_thumbnail(url=team.thumbnail)

            frozen_lines = [format_transaction(tx) for tx in frozen_transactions]

            embed.add_field(
                name=f"❄️ Scheduled for Processing ({len(frozen_transactions)} total)",
                value="\n".join(frozen_lines),
                inline=False
            )

            pages.append(embed)

        # Additional page: Recently processed transactions
        if processed_transactions:
            embed = EmbedTemplate.create_base_embed(
                title=f"📋 Transaction Status - {team.abbrev}",
                description=f"{team.lname} • Season {get_config().sba_current_season}",
                color=EmbedColors.INFO
            )

            if hasattr(team, 'thumbnail') and team.thumbnail:
                embed.set_thumbnail(url=team.thumbnail)

            processed_lines = [format_transaction(tx) for tx in processed_transactions[-20:]]  # Last 20

            embed.add_field(
                name=f"✅ Recently Processed ({len(processed_transactions[-20:])} shown)",
                value="\n".join(processed_lines),
                inline=False
            )

            pages.append(embed)

        # Additional page: Cancelled transactions (if requested)
        if cancelled_transactions:
            embed = EmbedTemplate.create_base_embed(
                title=f"📋 Transaction Status - {team.abbrev}",
                description=f"{team.lname} • Season {get_config().sba_current_season}",
                color=EmbedColors.INFO
            )

            if hasattr(team, 'thumbnail') and team.thumbnail:
                embed.set_thumbnail(url=team.thumbnail)

            cancelled_lines = [format_transaction(tx) for tx in cancelled_transactions[-20:]]  # Last 20

            embed.add_field(
                name=f"❌ Cancelled Transactions ({len(cancelled_transactions[-20:])} shown)",
                value="\n".join(cancelled_lines),
                inline=False
            )

            pages.append(embed)

        # Add footer to all pages
        for page in pages:
            page.set_footer(text="Use /legal to check roster legality")

        return pages
    
    async def _create_legal_embed(
        self,
        team,
        current_roster,
        next_roster,
        current_validation,
        next_validation
    ) -> discord.Embed:
        """Create embed showing roster legality check results."""
        
        # Determine overall status
        overall_legal = True
        if current_validation and not current_validation.is_legal:
            overall_legal = False
        if next_validation and not next_validation.is_legal:
            overall_legal = False
        
        status_emoji = "✅" if overall_legal else "❌"
        embed_color = EmbedColors.SUCCESS if overall_legal else EmbedColors.ERROR
        
        embed = EmbedTemplate.create_base_embed(
            title=f"{status_emoji} Roster Check - {team.abbrev}",
            description=f"{team.lname} • Season {get_config().sba_current_season}",
            color=embed_color
        )
        
        # Add team thumbnail if available
        if hasattr(team, 'thumbnail') and team.thumbnail:
            embed.set_thumbnail(url=team.thumbnail)
        
        # Current week roster
        if current_roster and current_validation:
            current_lines = []
            current_lines.append(f"**Players:** {current_validation.active_players} active, {current_validation.il_players} IL")
            current_lines.append(f"**sWAR:** {current_validation.total_sWAR:.1f}")
            
            if current_validation.errors:
                current_lines.append(f"**❌ Errors:** {len(current_validation.errors)}")
                for error in current_validation.errors[:3]:  # Show first 3 errors
                    current_lines.append(f"• {error}")
            
            if current_validation.warnings:
                current_lines.append(f"**⚠️ Warnings:** {len(current_validation.warnings)}")
                for warning in current_validation.warnings[:2]:  # Show first 2 warnings
                    current_lines.append(f"• {warning}")
            
            embed.add_field(
                name=f"{current_validation.status_emoji} Current Week",
                value="\n".join(current_lines),
                inline=True
            )
        else:
            embed.add_field(
                name="❓ Current Week",
                value="Roster data not available",
                inline=True
            )
        
        # Next week roster  
        if next_roster and next_validation:
            next_lines = []
            next_lines.append(f"**Players:** {next_validation.active_players} active, {next_validation.il_players} IL")
            next_lines.append(f"**sWAR:** {next_validation.total_sWAR:.1f}")
            
            if next_validation.errors:
                next_lines.append(f"**❌ Errors:** {len(next_validation.errors)}")
                for error in next_validation.errors[:3]:  # Show first 3 errors
                    next_lines.append(f"• {error}")
            
            if next_validation.warnings:
                next_lines.append(f"**⚠️ Warnings:** {len(next_validation.warnings)}")
                for warning in next_validation.warnings[:2]:  # Show first 2 warnings
                    next_lines.append(f"• {warning}")
            
            embed.add_field(
                name=f"{next_validation.status_emoji} Next Week",
                value="\n".join(next_lines),
                inline=True
            )
        else:
            embed.add_field(
                name="❓ Next Week", 
                value="Roster data not available",
                inline=True
            )
        
        # Overall status
        if overall_legal:
            embed.add_field(
                name="Overall Status",
                value="✅ All rosters are legal",
                inline=False
            )
        else:
            embed.add_field(
                name="Overall Status", 
                value="❌ Roster violations found - please review and correct",
                inline=False
            )
        
        embed.set_footer(text="Roster validation based on current league rules")
        return embed


async def setup(bot: commands.Bot):
    """Load the transaction commands cog."""
    await bot.add_cog(TransactionCommands(bot))