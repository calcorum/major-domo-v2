"""
Draft Board Commands

View draft picks by round with pagination.
"""
from typing import Optional

import discord
from discord.ext import commands

from config import get_config
from services.draft_pick_service import draft_pick_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.permissions import requires_team
from views.draft_views import create_draft_board_embed
from views.embeds import EmbedTemplate


class DraftBoardCommands(commands.Cog):
    """Draft board viewing command handlers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.DraftBoardCommands')

    @discord.app_commands.command(
        name="draft-board",
        description="View draft picks by round"
    )
    @discord.app_commands.describe(
        round_number="Round number to view (1-32)"
    )
    @requires_team()
    @logged_command("/draft-board")
    async def draft_board(
        self,
        interaction: discord.Interaction,
        round_number: Optional[int] = None
    ):
        """Display draft board for a specific round."""
        await interaction.response.defer()

        config = get_config()

        # Default to round 1 if not specified
        if round_number is None:
            round_number = 1

        # Validate round number
        if round_number < 1 or round_number > config.draft_rounds:
            embed = EmbedTemplate.error(
                "Invalid Round",
                f"Round number must be between 1 and {config.draft_rounds}."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get picks for this round
        picks = await draft_pick_service.get_picks_by_round(
            config.sba_current_season,
            round_number,
            include_taken=True
        )

        if not picks:
            embed = EmbedTemplate.error(
                "No Picks Found",
                f"Could not retrieve picks for round {round_number}."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Create draft board embed
        embed = await create_draft_board_embed(round_number, picks)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    """Load the draft board commands cog."""
    await bot.add_cog(DraftBoardCommands(bot))
