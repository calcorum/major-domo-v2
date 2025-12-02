"""
Draft List Commands

Manage team auto-draft queue (draft board).
"""
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import get_config
from services.draft_list_service import draft_list_service
from services.player_service import player_service
from services.team_service import team_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command, requires_draft_period
from utils.permissions import requires_team
from views.draft_views import create_draft_list_embed
from views.embeds import EmbedTemplate


async def fa_player_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[discord.app_commands.Choice[str]]:
    """Autocomplete for FA players only."""
    if len(current) < 2:
        return []

    try:
        config = get_config()
        players = await player_service.search_players(
            current,
            limit=25,
            season=config.sba_season
        )

        # Filter to FA team
        fa_players = [p for p in players if p.team_id == config.free_agent_team_id]

        return [
            discord.app_commands.Choice(
                name=f"{p.name} ({p.primary_position}) - {p.wara:.2f} sWAR",
                value=p.name
            )
            for p in fa_players[:25]
        ]

    except Exception:
        return []


class DraftListCommands(commands.Cog):
    """Draft list management command handlers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.DraftListCommands')

    @discord.app_commands.command(
        name="draft-list",
        description="View your team's auto-draft queue"
    )
    @requires_draft_period
    @requires_team()
    @logged_command("/draft-list")
    async def draft_list_view(self, interaction: discord.Interaction):
        """Display team's draft list."""
        await interaction.response.defer(ephemeral=True)

        config = get_config()

        # Get user's team
        team = await team_service.get_team_by_owner(
            interaction.user.id,
            config.sba_season
        )

        if not team:
            embed = EmbedTemplate.error(
                "Not a GM",
                "You are not registered as a team owner."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get draft list
        draft_list = await draft_list_service.get_team_list(
            config.sba_season,
            team.id
        )

        # Create embed
        embed = await create_draft_list_embed(team, draft_list)
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(
        name="draft-list-add",
        description="Add player to your auto-draft queue"
    )
    @discord.app_commands.describe(
        player="Player name to add (autocomplete shows FA players)",
        rank="Position in queue (optional, adds to end if not specified)"
    )
    @discord.app_commands.autocomplete(player=fa_player_autocomplete)
    @requires_draft_period
    @requires_team()
    @logged_command("/draft-list-add")
    async def draft_list_add(
        self,
        interaction: discord.Interaction,
        player: str,
        rank: Optional[int] = None
    ):
        """Add player to draft list."""
        await interaction.response.defer(ephemeral=True)

        config = get_config()

        # Get user's team
        team = await team_service.get_team_by_owner(
            interaction.user.id,
            config.sba_season
        )

        if not team:
            embed = EmbedTemplate.error(
                "Not a GM",
                "You are not registered as a team owner."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get player
        players = await player_service.get_players_by_name(player, config.sba_season)
        if not players:
            embed = EmbedTemplate.error(
                "Player Not Found",
                f"Could not find player '{player}'."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        player_obj = players[0]

        # Validate player is FA
        if player_obj.team_id != config.free_agent_team_id:
            embed = EmbedTemplate.error(
                "Player Not Available",
                f"{player_obj.name} is not a free agent."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Check if player already in list
        current_list = await draft_list_service.get_team_list(
            config.sba_season,
            team.id
        )

        if any(entry.player_id == player_obj.id for entry in current_list):
            embed = EmbedTemplate.error(
                "Already in Queue",
                f"{player_obj.name} is already in your draft queue."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Validate rank
        if rank is not None:
            if rank < 1 or rank > len(current_list) + 1:
                embed = EmbedTemplate.error(
                    "Invalid Rank",
                    f"Rank must be between 1 and {len(current_list) + 1}."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        # Add to list
        updated_list = await draft_list_service.add_to_list(
            config.sba_season,
            team.id,
            player_obj.id,
            rank
        )

        if not updated_list:
            embed = EmbedTemplate.error(
                "Add Failed",
                f"Failed to add {player_obj.name} to draft queue."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Find the added entry to get its rank
        added_entry = next((e for e in updated_list if e.player_id == player_obj.id), None)
        rank_str = f"#{added_entry.rank}" if added_entry else "at end"

        # Success message with full draft list
        success_msg = f"✅ Added **{player_obj.name}** at position **{rank_str}**"
        embed = await create_draft_list_embed(team, updated_list)
        embed.description = f"{success_msg}\n\n{embed.description}"

        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(
        name="draft-list-remove",
        description="Remove player from your auto-draft queue"
    )
    @discord.app_commands.describe(
        player="Player name to remove"
    )
    @discord.app_commands.autocomplete(player=fa_player_autocomplete)
    @requires_draft_period
    @requires_team()
    @logged_command("/draft-list-remove")
    async def draft_list_remove(
        self,
        interaction: discord.Interaction,
        player: str
    ):
        """Remove player from draft list."""
        await interaction.response.defer(ephemeral=True)

        config = get_config()

        # Get user's team
        team = await team_service.get_team_by_owner(
            interaction.user.id,
            config.sba_season
        )

        if not team:
            embed = EmbedTemplate.error(
                "Not a GM",
                "You are not registered as a team owner."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get player
        players = await player_service.get_players_by_name(player, config.sba_season)
        if not players:
            embed = EmbedTemplate.error(
                "Player Not Found",
                f"Could not find player '{player}'."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        player_obj = players[0]

        # Remove from list
        success = await draft_list_service.remove_player_from_list(
            config.sba_season,
            team.id,
            player_obj.id
        )

        if not success:
            embed = EmbedTemplate.error(
                "Not in Queue",
                f"{player_obj.name} is not in your draft queue."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Success message
        description = f"Removed **{player_obj.name}** from your draft queue."
        embed = EmbedTemplate.success("Player Removed", description)
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(
        name="draft-list-clear",
        description="Clear your entire auto-draft queue"
    )
    @requires_draft_period
    @requires_team()
    @logged_command("/draft-list-clear")
    async def draft_list_clear(self, interaction: discord.Interaction):
        """Clear entire draft list."""
        await interaction.response.defer(ephemeral=True)

        config = get_config()

        # Get user's team
        team = await team_service.get_team_by_owner(
            interaction.user.id,
            config.sba_season
        )

        if not team:
            embed = EmbedTemplate.error(
                "Not a GM",
                "You are not registered as a team owner."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get current list size
        current_list = await draft_list_service.get_team_list(
            config.sba_season,
            team.id
        )

        if not current_list:
            embed = EmbedTemplate.info(
                "Queue Empty",
                "Your draft queue is already empty."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Clear list
        success = await draft_list_service.clear_list(
            config.sba_season,
            team.id
        )

        if not success:
            embed = EmbedTemplate.error(
                "Clear Failed",
                "Failed to clear draft queue."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Success message
        description = f"Cleared **{len(current_list)} players** from your draft queue."
        embed = EmbedTemplate.success("Queue Cleared", description)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    """Load the draft list commands cog."""
    await bot.add_cog(DraftListCommands(bot))
