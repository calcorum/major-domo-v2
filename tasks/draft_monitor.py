"""
Draft Monitor Task for Discord Bot v2.0

Automated background task for draft timer monitoring, warnings, and auto-draft.
Self-terminates when draft timer is disabled to conserve resources.
"""
import asyncio
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands, tasks

from services.draft_service import draft_service
from services.draft_pick_service import draft_pick_service
from services.draft_list_service import draft_list_service
from services.player_service import player_service
from services.team_service import team_service
from utils.logging import get_contextual_logger
from views.embeds import EmbedTemplate, EmbedColors
from config import get_config


class DraftMonitorTask:
    """
    Automated monitoring task for draft operations.

    Features:
    - Monitors draft timer every 15 seconds
    - Sends warnings at 60s and 30s remaining
    - Triggers auto-draft when deadline passes
    - Respects global pick lock
    - Self-terminates when timer disabled
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.DraftMonitorTask')

        # Warning flags (reset each pick)
        self.warning_60s_sent = False
        self.warning_30s_sent = False

        self.logger.info("Draft monitor task initialized")

        # Start the monitor task
        self.monitor_loop.start()

    def cog_unload(self):
        """Stop the task when cog is unloaded."""
        self.monitor_loop.cancel()

    @tasks.loop(seconds=15)
    async def monitor_loop(self):
        """
        Main monitoring loop - checks draft state every 15 seconds.

        Self-terminates when draft timer is disabled.
        """
        try:
            # Get current draft state
            draft_data = await draft_service.get_draft_data()

            if not draft_data:
                self.logger.warning("No draft data found")
                return

            # CRITICAL: Stop loop if timer disabled
            if not draft_data.timer:
                self.logger.info("Draft timer disabled - stopping monitor")
                self.monitor_loop.cancel()
                return

            # Check if we need to take action
            now = datetime.now()
            deadline = draft_data.pick_deadline

            if not deadline:
                self.logger.warning("Draft timer active but no deadline set")
                return

            # Calculate time remaining
            time_remaining = (deadline - now).total_seconds()

            if time_remaining <= 0:
                # Timer expired - auto-draft
                await self._handle_expired_timer(draft_data)
            else:
                # Send warnings at intervals
                await self._send_warnings_if_needed(draft_data, time_remaining)

        except Exception as e:
            self.logger.error("Error in draft monitor loop", error=e)

    @monitor_loop.before_loop
    async def before_monitor(self):
        """Wait for bot to be ready before starting - REQUIRED FOR SAFE STARTUP."""
        await self.bot.wait_until_ready()
        self.logger.info("Bot is ready, draft monitor starting")

    async def _handle_expired_timer(self, draft_data):
        """
        Handle expired pick timer - trigger auto-draft.

        Args:
            draft_data: Current draft configuration
        """
        try:
            config = get_config()
            guild = self.bot.get_guild(config.guild_id)

            if not guild:
                self.logger.error("Could not find guild")
                return

            # Get current pick
            current_pick = await draft_pick_service.get_pick(
                config.sba_current_season,
                draft_data.currentpick
            )

            if not current_pick or not current_pick.owner:
                self.logger.error(f"Could not get pick #{draft_data.currentpick}")
                return

            # Get draft picks cog to check/acquire lock
            draft_picks_cog = self.bot.get_cog('DraftPicksCog')

            if not draft_picks_cog:
                self.logger.error("Could not find DraftPicksCog")
                return

            # Check if lock is available
            if draft_picks_cog.pick_lock.locked():
                self.logger.debug("Pick lock is held, skipping auto-draft this cycle")
                return

            # Acquire lock
            async with draft_picks_cog.pick_lock:
                draft_picks_cog.lock_acquired_at = datetime.now()
                draft_picks_cog.lock_acquired_by = None  # System auto-draft

                try:
                    await self._auto_draft_current_pick(draft_data, current_pick, guild)
                finally:
                    draft_picks_cog.lock_acquired_at = None
                    draft_picks_cog.lock_acquired_by = None

        except Exception as e:
            self.logger.error("Error handling expired timer", error=e)

    async def _auto_draft_current_pick(self, draft_data, current_pick, guild):
        """
        Attempt to auto-draft from team's draft list.

        Args:
            draft_data: Current draft configuration
            current_pick: DraftPick to auto-draft
            guild: Discord guild
        """
        try:
            config = get_config()

            # Get ping channel
            ping_channel = guild.get_channel(draft_data.ping_channel_id)
            if not ping_channel:
                self.logger.error(f"Could not find ping channel {draft_data.ping_channel_id}")
                return

            # Get team's draft list
            draft_list = await draft_list_service.get_team_list(
                config.sba_current_season,
                current_pick.owner.id
            )

            if not draft_list:
                self.logger.warning(f"Team {current_pick.owner.abbrev} has no draft list")
                await ping_channel.send(
                    content=f"⏰ {current_pick.owner.abbrev} time expired with no draft list - pick skipped"
                )
                # Advance to next pick
                await draft_service.advance_pick(draft_data.id, draft_data.currentpick)
                return

            # Try each player in order
            for entry in draft_list:
                if not entry.player:
                    continue

                player = entry.player

                # Check if player is still available
                if player.team_id != 498:  # 498 = FA team ID
                    self.logger.debug(f"Player {player.name} no longer available, skipping")
                    continue

                # Attempt to draft this player
                success = await self._attempt_draft_player(
                    current_pick,
                    player,
                    ping_channel
                )

                if success:
                    self.logger.info(
                        f"Auto-drafted {player.name} for {current_pick.owner.abbrev}"
                    )
                    # Advance to next pick
                    await draft_service.advance_pick(draft_data.id, draft_data.currentpick)
                    # Reset warning flags
                    self.warning_60s_sent = False
                    self.warning_30s_sent = False
                    return

            # No players successfully drafted
            self.logger.warning(f"Could not auto-draft for {current_pick.owner.abbrev}")
            await ping_channel.send(
                content=f"⏰ {current_pick.owner.abbrev} time expired - no valid players in draft list"
            )
            # Advance to next pick anyway
            await draft_service.advance_pick(draft_data.id, draft_data.currentpick)

        except Exception as e:
            self.logger.error("Error auto-drafting player", error=e)

    async def _attempt_draft_player(
        self,
        draft_pick,
        player,
        ping_channel
    ) -> bool:
        """
        Attempt to draft a specific player.

        Args:
            draft_pick: DraftPick to update
            player: Player to draft
            ping_channel: Discord channel for announcements

        Returns:
            True if draft succeeded
        """
        try:
            from utils.draft_helpers import validate_cap_space
            from services.team_service import team_service

            # Get team roster for cap validation
            roster = await team_service.get_team_roster(draft_pick.owner.id, 'current')

            if not roster:
                self.logger.error(f"Could not get roster for team {draft_pick.owner.id}")
                return False

            # Validate cap space
            is_valid, projected_total = await validate_cap_space(roster, player.wara)

            if not is_valid:
                self.logger.debug(
                    f"Cannot auto-draft {player.name} - would exceed cap "
                    f"(projected: {projected_total:.2f})"
                )
                return False

            # Update draft pick
            updated_pick = await draft_pick_service.update_pick_selection(
                draft_pick.id,
                player.id
            )

            if not updated_pick:
                self.logger.error(f"Failed to update pick {draft_pick.id}")
                return False

            # Update player team
            from services.player_service import player_service
            updated_player = await player_service.update_player_team(
                player.id,
                draft_pick.owner.id
            )

            if not updated_player:
                self.logger.error(f"Failed to update player {player.id} team")
                return False

            # Post to channel
            await ping_channel.send(
                content=f"🤖 AUTO-DRAFT: {draft_pick.owner.abbrev} selects **{player.name}** "
                        f"(Pick #{draft_pick.overall})"
            )

            return True

        except Exception as e:
            self.logger.error(f"Error attempting to draft {player.name}", error=e)
            return False

    async def _send_warnings_if_needed(self, draft_data, time_remaining: float):
        """
        Send warnings at 60s and 30s remaining.

        Args:
            draft_data: Current draft configuration
            time_remaining: Seconds remaining until deadline
        """
        try:
            config = get_config()
            guild = self.bot.get_guild(config.guild_id)

            if not guild:
                return

            ping_channel = guild.get_channel(draft_data.ping_channel_id)
            if not ping_channel:
                return

            # Get current pick for mention
            current_pick = await draft_pick_service.get_pick(
                config.sba_current_season,
                draft_data.currentpick
            )

            if not current_pick or not current_pick.owner:
                return

            # 60-second warning
            if 55 <= time_remaining <= 60 and not self.warning_60s_sent:
                await ping_channel.send(
                    content=f"⏰ {current_pick.owner.abbrev} - **60 seconds remaining** "
                            f"for pick #{current_pick.overall}!"
                )
                self.warning_60s_sent = True
                self.logger.debug(f"Sent 60s warning for pick #{current_pick.overall}")

            # 30-second warning
            elif 25 <= time_remaining <= 30 and not self.warning_30s_sent:
                await ping_channel.send(
                    content=f"⏰ {current_pick.owner.abbrev} - **30 seconds remaining** "
                            f"for pick #{current_pick.overall}!"
                )
                self.warning_30s_sent = True
                self.logger.debug(f"Sent 30s warning for pick #{current_pick.overall}")

            # Reset warnings if time goes back above 60s
            elif time_remaining > 60:
                if self.warning_60s_sent or self.warning_30s_sent:
                    self.warning_60s_sent = False
                    self.warning_30s_sent = False
                    self.logger.debug("Reset warning flags - pick deadline extended")

        except Exception as e:
            self.logger.error("Error sending warnings", error=e)


# Task factory function
def setup_draft_monitor(bot: commands.Bot) -> DraftMonitorTask:
    """
    Setup function for draft monitor task.

    Args:
        bot: Discord bot instance

    Returns:
        Initialized DraftMonitorTask
    """
    return DraftMonitorTask(bot)
