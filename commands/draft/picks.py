"""
Draft Pick Commands

Implements slash commands for making draft picks with global lock protection.
"""
import asyncio
import re
from typing import List, Optional
from datetime import datetime

import discord
from discord.ext import commands

from config import get_config
from services.draft_service import draft_service
from services.draft_pick_service import draft_pick_service
from services.draft_sheet_service import get_draft_sheet_service
from services.player_service import player_service
from services.team_service import team_service
from services.roster_service import roster_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command, requires_draft_period
from utils.draft_helpers import validate_cap_space, format_pick_display
from utils.helpers import get_team_salary_cap
from utils.permissions import requires_team
from views.draft_views import (
    create_player_draft_card,
    create_pick_illegal_embed,
    create_pick_success_embed,
    create_on_clock_announcement_embed
)


def _parse_player_name(raw_input: str) -> str:
    """
    Parse player name from raw input, handling autocomplete display format.

    Discord sometimes sends the autocomplete display text instead of the value
    when users type quickly. This function strips the position and sWAR info.

    Examples:
        "Mason Miller" -> "Mason Miller"
        "Mason Miller (RP) - 2.50 sWAR" -> "Mason Miller"
        "Geraldo Perdomo (SS) - 1.23 sWAR" -> "Geraldo Perdomo"
        "Player Name (1B) - 0.00 sWAR" -> "Player Name"

    Args:
        raw_input: Raw player name input from command

    Returns:
        Cleaned player name
    """
    # Pattern: "Player Name (POS) - X.XX sWAR"
    # Position can be letters or numbers (e.g., SS, RP, 1B, 2B, 3B, OF)
    # Extract just the player name before the opening parenthesis
    match = re.match(r'^(.+?)\s*\([A-Z0-9]+\)\s*-\s*[\d.]+\s*sWAR$', raw_input)
    if match:
        return match.group(1).strip()

    # No match - return original input (already clean)
    return raw_input.strip()


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
            player_name: Player name to draft (may include autocomplete display format)
        """
        config = get_config()

        # Parse player name in case it includes autocomplete display format
        # e.g., "Mason Miller (RP) - 2.50 sWAR" -> "Mason Miller"
        player_name = _parse_player_name(player_name)

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

        # Check if draft is paused
        if draft_data.paused:
            embed = await create_pick_illegal_embed(
                "Draft Paused",
                "The draft is currently paused. Please wait for an administrator to resume."
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

        # Validate user is on the clock OR has a skipped pick
        pick_to_use = current_pick  # Default: use current pick if on the clock

        if current_pick.owner.id != team.id:
            # Not on the clock - check for skipped picks
            skipped_picks = await draft_pick_service.get_skipped_picks_for_team(
                config.sba_season,
                team.id,
                draft_data.currentpick
            )

            if not skipped_picks:
                # No skipped picks - can't draft
                embed = await create_pick_illegal_embed(
                    "Not Your Turn",
                    f"{current_pick.owner.sname} is on the clock for {format_pick_display(current_pick.overall)}."
                )
                await interaction.followup.send(embed=embed)
                return

            # Use the earliest skipped pick
            pick_to_use = skipped_picks[0]
            self.logger.info(
                f"Team {team.abbrev} using skipped pick #{pick_to_use.overall} "
                f"(current pick is #{current_pick.overall})"
            )

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

        # Execute pick (using pick_to_use which may be current or skipped pick)
        updated_pick = await draft_pick_service.update_pick_selection(
            pick_to_use.id,
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

        # Write pick to Google Sheets (fire-and-forget with notification on failure)
        await self._write_pick_to_sheets(
            draft_data=draft_data,
            pick=pick_to_use,
            player=player_obj,
            team=team,
            guild=interaction.guild
        )

        # Determine if this was a skipped pick
        is_skipped_pick = pick_to_use.overall != current_pick.overall

        # Send success message
        success_embed = await create_pick_success_embed(
            player_obj,
            team,
            pick_to_use.overall,
            projected_total,
            cap_limit
        )

        # Add note if this was a skipped pick
        if is_skipped_pick:
            success_embed.set_footer(
                text=f"📝 Making up skipped pick (current pick is #{current_pick.overall})"
            )

        await interaction.followup.send(embed=success_embed)

        # Post draft card to ping channel (only if different from command channel)
        if draft_data.ping_channel and draft_data.ping_channel != interaction.channel_id:
            guild = interaction.guild
            if guild:
                ping_channel = guild.get_channel(draft_data.ping_channel)
                if ping_channel:
                    draft_card = await create_player_draft_card(player_obj, pick_to_use)

                    # Add skipped pick context to draft card
                    if is_skipped_pick:
                        draft_card.set_footer(
                            text=f"📝 Making up skipped pick (current pick is #{current_pick.overall})"
                        )

                    await ping_channel.send(embed=draft_card)

        # Only advance the draft if this was the current pick (not a skipped pick)
        if not is_skipped_pick:
            await draft_service.advance_pick(draft_data.id, draft_data.currentpick)

            # Post on-clock announcement for next team
            guild = interaction.guild
            if guild and draft_data.ping_channel:
                ping_channel = guild.get_channel(draft_data.ping_channel)
                if ping_channel:
                    await self._post_on_clock_announcement(
                        ping_channel=ping_channel,
                        guild=guild
                    )

        self.logger.info(
            f"Draft pick completed: {team.abbrev} selected {player_obj.name} "
            f"(pick #{pick_to_use.overall})"
            + (f" [skipped pick makeup]" if is_skipped_pick else "")
        )

    async def _write_pick_to_sheets(
        self,
        draft_data,
        pick,
        player,
        team,
        guild: Optional[discord.Guild]
    ):
        """
        Write pick to Google Sheets (fire-and-forget with ping channel notification on failure).

        Args:
            draft_data: Current draft configuration
            pick: The draft pick being used
            player: Player being drafted
            team: Team making the pick
            guild: Discord guild for notification channel
        """
        config = get_config()

        try:
            draft_sheet_service = get_draft_sheet_service()
            success = await draft_sheet_service.write_pick(
                season=config.sba_season,
                overall=pick.overall,
                orig_owner_abbrev=pick.origowner.abbrev if pick.origowner else team.abbrev,
                owner_abbrev=team.abbrev,
                player_name=player.name,
                swar=player.wara
            )

            if not success:
                # Write failed - notify in ping channel
                await self._notify_sheet_failure(
                    guild=guild,
                    channel_id=draft_data.ping_channel,
                    pick_overall=pick.overall,
                    player_name=player.name,
                    reason="Sheet write returned failure"
                )

        except Exception as e:
            self.logger.warning(f"Failed to write pick to sheets: {e}")
            # Notify in ping channel
            await self._notify_sheet_failure(
                guild=guild,
                channel_id=draft_data.ping_channel,
                pick_overall=pick.overall,
                player_name=player.name,
                reason=str(e)
            )

    async def _notify_sheet_failure(
        self,
        guild: Optional[discord.Guild],
        channel_id: Optional[int],
        pick_overall: int,
        player_name: str,
        reason: str
    ):
        """
        Post notification to ping channel when sheet write fails.

        Args:
            guild: Discord guild
            channel_id: Ping channel ID
            pick_overall: Pick number that failed
            player_name: Player name
            reason: Failure reason
        """
        if not guild or not channel_id:
            return

        try:
            channel = guild.get_channel(channel_id)
            if channel and hasattr(channel, 'send'):
                await channel.send(
                    f"⚠️ **Sheet Sync Failed** - Pick #{pick_overall} ({player_name}) "
                    f"was not written to the draft sheet. "
                    f"Use `/draft-admin resync-sheet` to manually sync."
                )
        except Exception as e:
            self.logger.error(f"Failed to send sheet failure notification: {e}")

    async def _post_on_clock_announcement(
        self,
        ping_channel,
        guild: discord.Guild
    ) -> None:
        """
        Post the on-clock announcement embed for the next team with role ping.

        Called after advance_pick() to announce who is now on the clock.

        Args:
            ping_channel: Discord channel to post in
            guild: Discord guild for role lookup
        """
        try:
            config = get_config()

            # Refresh draft data to get updated currentpick and deadline
            updated_draft_data = await draft_service.get_draft_data()
            if not updated_draft_data:
                self.logger.error("Could not refresh draft data for announcement")
                return

            # Get the new current pick
            next_pick = await draft_pick_service.get_pick(
                config.sba_season,
                updated_draft_data.currentpick
            )

            if not next_pick or not next_pick.owner:
                self.logger.error(f"Could not get pick #{updated_draft_data.currentpick} for announcement")
                return

            # Get recent picks (last 5 completed)
            recent_picks = await draft_pick_service.get_recent_picks(
                config.sba_season,
                updated_draft_data.currentpick - 1,  # Start from previous pick
                limit=5
            )

            # Get team roster for sWAR calculation
            team_roster = await roster_service.get_team_roster(next_pick.owner.id, "current")
            roster_swar = team_roster.total_wara if team_roster else 0.0
            cap_limit = get_team_salary_cap(next_pick.owner)

            # Get top 5 most expensive players on team roster
            top_roster_players = []
            if team_roster:
                all_players = team_roster.all_players
                sorted_players = sorted(all_players, key=lambda p: p.wara if p.wara else 0.0, reverse=True)
                top_roster_players = sorted_players[:5]

            # Get sheet URL
            sheet_url = config.get_draft_sheet_url(config.sba_season)

            # Create and send the embed
            embed = await create_on_clock_announcement_embed(
                current_pick=next_pick,
                draft_data=updated_draft_data,
                recent_picks=recent_picks if recent_picks else [],
                roster_swar=roster_swar,
                cap_limit=cap_limit,
                top_roster_players=top_roster_players,
                sheet_url=sheet_url
            )

            # Mention the team's role (using team.lname)
            team_mention = ""
            team_role = discord.utils.get(guild.roles, name=next_pick.owner.lname)
            if team_role:
                team_mention = f"{team_role.mention} "
            else:
                self.logger.warning(f"Could not find role for team {next_pick.owner.lname}")

            await ping_channel.send(content=team_mention, embed=embed)
            self.logger.info(f"Posted on-clock announcement for pick #{updated_draft_data.currentpick}")

        except Exception as e:
            self.logger.error("Error posting on-clock announcement", error=e)


async def setup(bot: commands.Bot):
    """Load the draft picks cog."""
    await bot.add_cog(DraftPicksCog(bot))
