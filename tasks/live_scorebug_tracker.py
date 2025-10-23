"""
Live Scorebug Tracker

Background task that monitors published scorecards and updates live score displays.
"""
import asyncio
from typing import List, Optional
import discord
from discord.ext import tasks, commands

from models.team import Team
from utils.logging import get_contextual_logger
from utils.scorebug_helpers import create_scorebug_embed
from utils.discord_helpers import set_channel_visibility
from services.scorebug_service import ScorebugData, ScorebugService
from services.team_service import team_service
from commands.gameplay.scorecard_tracker import ScorecardTracker
from commands.voice.tracker import VoiceChannelTracker
from views.embeds import EmbedTemplate, EmbedColors
from config import get_config
from exceptions import SheetsException


class LiveScorebugTracker:
    """
    Manages live scorebug updates for active games.

    Features:
    - Updates live scores channel every 3 minutes
    - Updates voice channel descriptions with live scores
    - Clears displays when no active games
    - Error resilient with graceful degradation
    """

    def __init__(self, bot: commands.Bot):
        """
        Initialize the live scorebug tracker.

        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.LiveScorebugTracker')
        self.scorebug_service = ScorebugService()
        self.scorecard_tracker = ScorecardTracker()
        self.voice_tracker = VoiceChannelTracker()

        # Start the monitoring loop
        self.update_loop.start()
        self.logger.info("Live scorebug tracker initialized")

    def cog_unload(self):
        """Stop the task when service is unloaded."""
        self.update_loop.cancel()
        self.logger.info("Live scorebug tracker stopped")

    @tasks.loop(minutes=3)
    async def update_loop(self):
        """
        Main update loop - runs every 3 minutes.

        Updates:
        - Live scores channel with all active scorebugs
        - Voice channel descriptions with live scores
        """
        try:
            await self._update_scorebugs()
        except Exception as e:
            self.logger.error(f"Error in scorebug update loop: {e}", exc_info=True)

    @update_loop.before_loop
    async def before_update_loop(self):
        """Wait for bot to be ready before starting."""
        await self.bot.wait_until_ready()
        self.logger.info("Live scorebug tracker ready to start monitoring")

    async def _update_scorebugs(self):
        """Update all scorebug displays."""
        config = get_config()
        guild = self.bot.get_guild(config.guild_id)

        if not guild:
            self.logger.warning(f"Guild {config.guild_id} not found, skipping update")
            return

        # Get live scores channel
        live_scores_channel = discord.utils.get(guild.text_channels, name='live-sba-scores')

        if not live_scores_channel:
            self.logger.warning("live-sba-scores channel not found, skipping channel update")
            # Don't return - still update voice channels
        else:
            # Get all published scorecards
            all_scorecards = self.scorecard_tracker.get_all_scorecards()

            if not all_scorecards:
                # No active scorebugs - clear the channel and hide it
                await self._clear_live_scores_channel(live_scores_channel)
                await set_channel_visibility(
                    live_scores_channel,
                    visible=False,
                    reason="No active games"
                )
                return

            # Read all scorebugs and create embeds
            active_scorebugs = []
            for text_channel_id, sheet_url in all_scorecards:
                try:
                    scorebug_data = await self.scorebug_service.read_scorebug_data(
                        sheet_url,
                        full_length=False  # Compact view for live channel
                    )

                    # Only include active (non-final) games
                    if scorebug_data.is_active:
                        # Get team data
                        away_team = await team_service.get_team(scorebug_data.away_team_id)
                        home_team = await team_service.get_team(scorebug_data.home_team_id)

                        if away_team is None or home_team is None:
                            raise ValueError(f'Error looking up teams in scorecard; IDs provided: {scorebug_data.away_team_id} & {scorebug_data.home_team_id}')

                        # Create compact embed using shared utility
                        embed = create_scorebug_embed(
                            scorebug_data,
                            away_team,
                            home_team,
                            full_length=False  # Compact view for live channel
                        )

                        active_scorebugs.append(embed)

                        # Update associated voice channel if it exists
                        await self._update_voice_channel_description(
                            text_channel_id,
                            scorebug_data,
                            away_team,
                            home_team
                        )

                    await asyncio.sleep(1)  # Rate limit between reads

                except SheetsException as e:
                    self.logger.warning(f"Could not read scorecard {sheet_url}: {e}")
                except Exception as e:
                    self.logger.error(f"Error processing scorecard {sheet_url}: {e}")

            # Update live scores channel
            if active_scorebugs:
                await set_channel_visibility(
                    live_scores_channel,
                    visible=True,
                    reason="Active games in progress"
                )
                await self._post_scorebugs_to_channel(live_scores_channel, active_scorebugs)
            else:
                # All games finished - clear the channel and hide it
                await self._clear_live_scores_channel(live_scores_channel)
                await set_channel_visibility(
                    live_scores_channel,
                    visible=False,
                    reason="No active games"
                )

    async def _post_scorebugs_to_channel(
        self,
        channel: discord.TextChannel,
        embeds: List[discord.Embed]
    ):
        """
        Post scorebugs to the live scores channel.

        Args:
            channel: Discord text channel
            embeds: List of scorebug embeds
        """
        try:
            # Clear old messages
            async for message in channel.history(limit=25):
                await message.delete()

            # Post new scorebugs (Discord allows up to 10 embeds per message)
            if len(embeds) <= 10:
                await channel.send(embeds=embeds)
            else:
                # Split into multiple messages if more than 10 embeds
                for i in range(0, len(embeds), 10):
                    batch = embeds[i:i+10]
                    await channel.send(embeds=batch)

            self.logger.info(f"Posted {len(embeds)} scorebugs to live-sba-scores")

        except discord.Forbidden:
            self.logger.error("Missing permissions to update live-sba-scores channel")
        except Exception as e:
            self.logger.error(f"Error posting scorebugs: {e}")

    async def _clear_live_scores_channel(self, channel: discord.TextChannel):
        """
        Clear the live scores channel when no active games.

        Args:
            channel: Discord text channel
        """
        try:
            # Clear all messages
            async for message in channel.history(limit=25):
                await message.delete()

            self.logger.info("Cleared live-sba-scores channel (no active games)")

        except discord.Forbidden:
            self.logger.error("Missing permissions to clear live-sba-scores channel")
        except Exception as e:
            self.logger.error(f"Error clearing channel: {e}")

    async def _update_voice_channel_description(
        self,
        text_channel_id: int,
        scorebug_data: ScorebugData,
        away_team: Team,
        home_team: Team
    ):
        """
        Update voice channel description with live score.

        Args:
            text_channel_id: Text channel ID where scorecard was published
            scorebug_data: ScorebugData object
            away_team: Away team object (optional)
            home_team: Home team object (optional)
        """
        try:
            # Check if there's an associated voice channel
            voice_channel_id = self.voice_tracker.get_voice_channel_for_text_channel(text_channel_id)

            if not voice_channel_id:
                self.logger.debug(f'No voice channel associated with text channel ID {text_channel_id} (may have been cleaned up)')
                return  # No associated voice channel

            # Get the voice channel
            config = get_config()
            guild = self.bot.get_guild(config.guild_id)

            if not guild:
                return

            voice_channel = guild.get_channel(voice_channel_id)

            if not voice_channel or not isinstance(voice_channel, discord.VoiceChannel):
                self.logger.debug(f"Voice channel {voice_channel_id} not found or wrong type")
                return

            # Format description: "BOS 4 @ 3 NYY" or "BOS 5 @ 3 NYY - FINAL"
            away_abbrev = away_team.abbrev if away_team else "AWAY"
            home_abbrev = home_team.abbrev if home_team else "HOME"

            if scorebug_data.is_final:
                description = f"{away_abbrev} {scorebug_data.away_score} @ {scorebug_data.home_score} {home_abbrev} - FINAL"
            else:
                description = f"{away_abbrev} {scorebug_data.away_score} @ {scorebug_data.home_score} {home_abbrev}"

            # Update voice channel description (topic)
            await voice_channel.edit(status=description)

            self.logger.debug(f"Updated voice channel {voice_channel.name} description to: {description}")

        except discord.Forbidden:
            self.logger.warning(f"Missing permissions to update voice channel {voice_channel_id}")
        except Exception as e:
            self.logger.error(f"Error updating voice channel description: {e}")


def setup_scorebug_tracker(bot: commands.Bot) -> LiveScorebugTracker:
    """
    Setup function to initialize the live scorebug tracker.

    Args:
        bot: Discord bot instance

    Returns:
        LiveScorebugTracker instance
    """
    return LiveScorebugTracker(bot)
