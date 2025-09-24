"""
Transaction Management Commands

Core transaction commands for roster management and transaction tracking.
"""
from typing import Optional
import asyncio

import discord
from discord.ext import commands
from discord import app_commands

from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from views.embeds import EmbedColors, EmbedTemplate
from constants import SBA_CURRENT_SEASON

from services.transaction_service import transaction_service
from services.roster_service import roster_service
from services.team_service import team_service
# No longer need TransactionStatus enum


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
        user_teams = await team_service.get_teams_by_owner(interaction.user.id, SBA_CURRENT_SEASON)
        
        if not user_teams:
            await interaction.followup.send(
                "❌ You don't appear to own a team in the current season.",
                ephemeral=True
            )
            return
        
        team = user_teams[0]  # Use first team if multiple
        
        # Get transactions in parallel
        pending_task = transaction_service.get_pending_transactions(team.abbrev, SBA_CURRENT_SEASON)
        frozen_task = transaction_service.get_frozen_transactions(team.abbrev, SBA_CURRENT_SEASON) 
        processed_task = transaction_service.get_processed_transactions(team.abbrev, SBA_CURRENT_SEASON)
        
        pending_transactions = await pending_task
        frozen_transactions = await frozen_task
        processed_transactions = await processed_task
        
        # Get cancelled if requested
        cancelled_transactions = []
        if show_cancelled:
            cancelled_transactions = await transaction_service.get_team_transactions(
                team.abbrev, 
                SBA_CURRENT_SEASON,
                cancelled=True
            )
        
        embed = await self._create_my_moves_embed(
            team, 
            pending_transactions, 
            frozen_transactions, 
            processed_transactions,
            cancelled_transactions
        )
        
        await interaction.followup.send(embed=embed)
    
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
            target_team = await team_service.get_team_by_abbrev(team.upper(), SBA_CURRENT_SEASON)
            if not target_team:
                await interaction.followup.send(
                    f"❌ Could not find team '{team}' in season {SBA_CURRENT_SEASON}.",
                    ephemeral=True
                )
                return
        else:
            # Get user's team
            user_teams = await team_service.get_teams_by_owner(interaction.user.id, SBA_CURRENT_SEASON)
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
    
    async def _create_my_moves_embed(
        self,
        team,
        pending_transactions,
        frozen_transactions,
        processed_transactions,
        cancelled_transactions
    ) -> discord.Embed:
        """Create embed showing user's transaction status."""
        
        embed = EmbedTemplate.create_base_embed(
            title=f"📋 Transaction Status - {team.abbrev}",
            description=f"{team.lname} • Season {SBA_CURRENT_SEASON}",
            color=EmbedColors.INFO
        )
        
        # Add team thumbnail if available
        if hasattr(team, 'thumbnail') and team.thumbnail:
            embed.set_thumbnail(url=team.thumbnail)
        
        # Pending transactions
        if pending_transactions:
            pending_lines = []
            for transaction in pending_transactions[-5:]:  # Show last 5
                pending_lines.append(
                    f"{transaction.status_emoji} Week {transaction.week}: {transaction.move_description}"
                )
            
            embed.add_field(
                name="⏳ Pending Transactions",
                value="\n".join(pending_lines),
                inline=False
            )
        else:
            embed.add_field(
                name="⏳ Pending Transactions", 
                value="No pending transactions",
                inline=False
            )
        
        # Frozen transactions (scheduled for processing)
        if frozen_transactions:
            frozen_lines = []
            for transaction in frozen_transactions[-3:]:  # Show last 3
                frozen_lines.append(
                    f"{transaction.status_emoji} Week {transaction.week}: {transaction.move_description}"
                )
            
            embed.add_field(
                name="❄️ Scheduled for Processing",
                value="\n".join(frozen_lines),
                inline=False
            )
        
        # Recent processed transactions
        if processed_transactions:
            processed_lines = []
            for transaction in processed_transactions[-3:]:  # Show last 3
                processed_lines.append(
                    f"{transaction.status_emoji} Week {transaction.week}: {transaction.move_description}"
                )
            
            embed.add_field(
                name="✅ Recently Processed",
                value="\n".join(processed_lines),
                inline=False
            )
        
        # Cancelled transactions (if requested)
        if cancelled_transactions:
            cancelled_lines = []
            for transaction in cancelled_transactions[-2:]:  # Show last 2
                cancelled_lines.append(
                    f"{transaction.status_emoji} Week {transaction.week}: {transaction.move_description}"
                )
            
            embed.add_field(
                name="❌ Cancelled Transactions",
                value="\n".join(cancelled_lines),
                inline=False
            )
        
        # Transaction summary
        total_pending = len(pending_transactions)
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
        
        embed.set_footer(text="Use /legal to check roster legality")
        return embed
    
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
            description=f"{team.lname} • Season {SBA_CURRENT_SEASON}",
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