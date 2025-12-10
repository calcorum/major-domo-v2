"""
Draft Pick Commands

Implements slash commands for making draft picks with global lock protection.
"""
import asyncio
from typing import List, Optional
from datetime import datetime

import discord
from discord.ext import commands

from config import get_config
from services.draft_service import draft_service
from services.draft_pick_service import draft_pick_service
from services.player_service import player_service
from services.team_service import team_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command, requires_draft_period
from utils.draft_helpers import validate_cap_space, format_pick_display
from utils.permissions import requires_team
from views.draft_views import (
    create_player_draft_card,
    create_pick_illegal_embed,
    create_pick_success_embed
)


async def fa_player_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[discord.app_commands.Choice[str]]:
    """Autocomplete for FA players only."""
    if len(current) < 2:
        return []

    try:
        config = get_config()
        # Search for FA players only
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


class DraftPicksCog(commands.Cog):
    """Draft pick command handlers with global lock protection."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.DraftPicksCog')

        # GLOBAL PICK LOCK (local only - not in database)
        self.pick_lock = asyncio.Lock()
        self.lock_acquired_at: Optional[datetime] = None
        self.lock_acquired_by: Optional[int] = None

    @discord.app_commands.command(
        name="draft",
        description="Make a draft pick (autocomplete shows FA players only)"
    )
    @discord.app_commands.describe(
        player="Player name to draft (autocomplete shows available FA players)"
    )
    @discord.app_commands.autocomplete(player=fa_player_autocomplete)
    @requires_draft_period
    @requires_team()
    @logged_command("/draft")
    async def draft_pick(
        self,
        interaction: discord.Interaction,
        player: str
    ):
        """Make a draft pick with global lock protection."""
        await interaction.response.defer()

        # Check if lock is held
        if self.pick_lock.locked():
            if self.lock_acquired_at:
                time_held = (datetime.now() - self.lock_acquired_at).total_seconds()

                if time_held > 30:
                    # STALE LOCK: Auto-override after 30 seconds
                    self.logger.warning(
                        f"Stale lock detected ({time_held:.1f}s). "
                        f"Overriding lock from user {self.lock_acquired_by}"
                    )
                else:
                    # ACTIVE LOCK: Reject with friendly message
                    embed = await create_pick_illegal_embed(
                        "Pick In Progress",
                        f"Another manager is currently making a pick. "
                        f"Please wait approximately {30 - int(time_held)} seconds."
                    )
                    await interaction.followup.send(embed=embed)
                    return

        # Acquire global lock
        async with self.pick_lock:
            self.lock_acquired_at = datetime.now()
            self.lock_acquired_by = interaction.user.id

            try:
                await self._process_draft_pick(interaction, player)
            finally:
                self.lock_acquired_at = None
                self.lock_acquired_by = None

    async def _process_draft_pick(
        self,
        interaction: discord.Interaction,
        player_name: str
    ):
        """
        Process draft pick with validation.

        Args:
            interaction: Discord interaction
            player_name: Player name to draft
        """
        config = get_config()

        # Get user's team (CACHED via @cached_single_item)
        team = await team_service.get_team_by_owner(
            interaction.user.id,
            config.sba_season
        )

        if not team:
            embed = await create_pick_illegal_embed(
                "Not a GM",
                "You are not registered as a team owner."
            )
            await interaction.followup.send(embed=embed)
            return

        # Get draft state
        draft_data = await draft_service.get_draft_data()
        if not draft_data:
            embed = await create_pick_illegal_embed(
                "Draft Not Found",
                "Could not retrieve draft configuration."
            )
            await interaction.followup.send(embed=embed)
            return

        # Get current pick
        current_pick = await draft_pick_service.get_pick(
            config.sba_season,
            draft_data.currentpick
        )

        if not current_pick or not current_pick.owner:
            embed = await create_pick_illegal_embed(
                "Invalid Pick",
                f"Could not retrieve pick #{draft_data.currentpick}."
            )
            await interaction.followup.send(embed=embed)
            return

        # Validate user is on the clock
        if current_pick.owner.id != team.id:
            # TODO: Check for skipped picks
            embed = await create_pick_illegal_embed(
                "Not Your Turn",
                f"{current_pick.owner.sname} is on the clock for {format_pick_display(current_pick.overall)}."
            )
            await interaction.followup.send(embed=embed)
            return

        # Get player
        players = await player_service.get_players_by_name(player_name, config.sba_season)

        if not players:
            embed = await create_pick_illegal_embed(
                "Player Not Found",
                f"Could not find player '{player_name}'."
            )
            await interaction.followup.send(embed=embed)
            return

        player_obj = players[0]

        # Validate player is FA
        if player_obj.team_id != config.free_agent_team_id:
            embed = await create_pick_illegal_embed(
                "Player Not Available",
                f"{player_obj.name} is not a free agent."
            )
            await interaction.followup.send(embed=embed)
            return

        # Validate cap space
        roster = await team_service.get_team_roster(team.id, 'current')
        if not roster:
            embed = await create_pick_illegal_embed(
                "Roster Error",
                f"Could not retrieve roster for {team.abbrev}."
            )
            await interaction.followup.send(embed=embed)
            return

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, player_obj.wara, team)

        if not is_valid:
            embed = await create_pick_illegal_embed(
                "Cap Space Exceeded",
                f"Drafting {player_obj.name} would put you at {projected_total:.2f} sWAR (limit: {cap_limit:.2f})."
            )
            await interaction.followup.send(embed=embed)
            return

        # Execute pick
        updated_pick = await draft_pick_service.update_pick_selection(
            current_pick.id,
            player_obj.id
        )

        if not updated_pick:
            embed = await create_pick_illegal_embed(
                "Pick Failed",
                "Failed to update draft pick. Please try again."
            )
            await interaction.followup.send(embed=embed)
            return

        # Update player team
        updated_player = await player_service.update_player_team(
            player_obj.id,
            team.id
        )

        if not updated_player:
            self.logger.error(f"Failed to update player {player_obj.id} team")

        # Send success message
        success_embed = await create_pick_success_embed(
            player_obj,
            team,
            current_pick.overall,
            projected_total,
            cap_limit
        )
        await interaction.followup.send(embed=success_embed)

        # Post draft card to ping channel
        if draft_data.ping_channel:
            guild = interaction.guild
            if guild:
                ping_channel = guild.get_channel(draft_data.ping_channel)
                if ping_channel:
                    draft_card = await create_player_draft_card(player_obj, current_pick)
                    await ping_channel.send(embed=draft_card)

        # Advance to next pick
        await draft_service.advance_pick(draft_data.id, draft_data.currentpick)

        self.logger.info(
            f"Draft pick completed: {team.abbrev} selected {player_obj.name} "
            f"(pick #{current_pick.overall})"
        )


async def setup(bot: commands.Bot):
    """Load the draft picks cog."""
    await bot.add_cog(DraftPicksCog(bot))
