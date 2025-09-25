"""
Voice Channel Cleanup Service

Provides automatic cleanup of empty voice channels with restart resilience.
"""
import asyncio
import logging

import discord
from discord.ext import commands

from .tracker import VoiceChannelTracker

logger = logging.getLogger(f'{__name__}.VoiceChannelCleanupService')


class VoiceChannelCleanupService:
    """
    Manages automatic cleanup of bot-created voice channels.

    Features:
    - Restart-resilient channel tracking
    - Automatic empty channel cleanup
    - Configurable cleanup intervals and thresholds
    - Stale entry removal and recovery
    """

    def __init__(self, data_file: str = "data/voice_channels.json"):
        """
        Initialize the cleanup service.

        Args:
            data_file: Path to the JSON data file for persistence
        """
        self.tracker = VoiceChannelTracker(data_file)
        self.cleanup_interval = 60   # 5 minutes check interval
        self.empty_threshold = 5    # Delete after 15 minutes empty
        self._running = False

    async def start_monitoring(self, bot: commands.Bot) -> None:
        """
        Start the cleanup monitoring loop.

        Args:
            bot: Discord bot instance
        """
        if self._running:
            logger.warning("Cleanup service is already running")
            return

        self._running = True
        logger.info("Starting voice channel cleanup service")

        # On startup, verify tracked channels still exist and clean up stale entries
        await self.verify_tracked_channels(bot)

        # Start the monitoring loop
        while self._running:
            try:
                await self.cleanup_cycle(bot)
                await asyncio.sleep(self.cleanup_interval)
            except Exception as e:
                logger.error(f"Cleanup cycle error: {e}", exc_info=True)
                # Use shorter retry interval on errors
                await asyncio.sleep(60)

        logger.info("Voice channel cleanup service stopped")

    def stop_monitoring(self) -> None:
        """Stop the cleanup monitoring loop."""
        self._running = False
        logger.info("Stopping voice channel cleanup service")

    async def verify_tracked_channels(self, bot: commands.Bot) -> None:
        """
        Verify tracked channels still exist and clean up stale entries.

        Args:
            bot: Discord bot instance
        """
        logger.info("Verifying tracked voice channels on startup")

        valid_channel_ids = []
        channels_to_remove = []

        for channel_data in self.tracker.get_all_tracked_channels():
            try:
                guild_id = int(channel_data["guild_id"])
                channel_id = int(channel_data["channel_id"])

                guild = bot.get_guild(guild_id)
                if not guild:
                    logger.warning(f"Guild {guild_id} not found, removing channel {channel_data['name']}")
                    channels_to_remove.append(channel_id)
                    continue

                channel = guild.get_channel(channel_id)
                if not channel:
                    logger.warning(f"Channel {channel_data['name']} (ID: {channel_id}) no longer exists")
                    channels_to_remove.append(channel_id)
                    continue

                # Channel exists and is valid
                valid_channel_ids.append(channel_id)

            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Invalid channel data: {e}, removing entry")
                if "channel_id" in channel_data:
                    try:
                        channels_to_remove.append(int(channel_data["channel_id"]))
                    except (ValueError, TypeError):
                        pass

        # Remove stale entries
        for channel_id in channels_to_remove:
            self.tracker.remove_channel(channel_id)

        # Also clean up any additional stale entries
        stale_removed = self.tracker.cleanup_stale_entries(valid_channel_ids)
        total_removed = len(channels_to_remove) + stale_removed

        if total_removed > 0:
            logger.info(f"Cleaned up {total_removed} stale channel tracking entries")

        logger.info(f"Verified {len(valid_channel_ids)} valid tracked channels")

    async def cleanup_cycle(self, bot: commands.Bot) -> None:
        """
        Check all tracked channels and cleanup empty ones.

        Args:
            bot: Discord bot instance
        """
        logger.debug("Starting cleanup cycle")

        # Update status of all tracked channels
        await self.update_all_channel_statuses(bot)

        # Get channels ready for cleanup
        channels_for_cleanup = self.tracker.get_channels_for_cleanup(self.empty_threshold)

        if channels_for_cleanup:
            logger.info(f"Found {len(channels_for_cleanup)} channels ready for cleanup")

        # Delete empty channels
        for channel_data in channels_for_cleanup:
            await self.cleanup_channel(bot, channel_data)

    async def update_all_channel_statuses(self, bot: commands.Bot) -> None:
        """
        Update the empty status of all tracked channels.

        Args:
            bot: Discord bot instance
        """
        for channel_data in self.tracker.get_all_tracked_channels():
            await self.check_channel_status(bot, channel_data)

    async def check_channel_status(self, bot: commands.Bot, channel_data: dict) -> None:
        """
        Check if a channel is empty and update tracking.

        Args:
            bot: Discord bot instance
            channel_data: Channel tracking data
        """
        try:
            guild_id = int(channel_data["guild_id"])
            channel_id = int(channel_data["channel_id"])

            guild = bot.get_guild(guild_id)
            if not guild:
                logger.debug(f"Guild {guild_id} not found for channel {channel_data['name']}")
                return

            channel = guild.get_channel(channel_id)
            if not channel:
                logger.debug(f"Channel {channel_data['name']} no longer exists, will be cleaned up")
                self.tracker.remove_channel(channel_id)
                return

            # Ensure it's a voice channel before checking members
            if not isinstance(channel, discord.VoiceChannel):
                logger.warning(f"Channel {channel_data['name']} is not a voice channel, removing from tracking")
                self.tracker.remove_channel(channel_id)
                return

            # Check if channel is empty
            is_empty = len(channel.members) == 0
            self.tracker.update_channel_status(channel_id, is_empty)

            logger.debug(f"Channel {channel_data['name']}: {'empty' if is_empty else 'occupied'} "
                        f"({len(channel.members)} members)")

        except Exception as e:
            logger.error(f"Error checking channel status for {channel_data.get('name', 'unknown')}: {e}")

    async def cleanup_channel(self, bot: commands.Bot, channel_data: dict) -> None:
        """
        Delete an empty channel and remove from tracking.

        Args:
            bot: Discord bot instance
            channel_data: Channel tracking data
        """
        try:
            guild_id = int(channel_data["guild_id"])
            channel_id = int(channel_data["channel_id"])
            channel_name = channel_data["name"]

            guild = bot.get_guild(guild_id)
            if not guild:
                logger.info(f"Guild {guild_id} not found, removing tracking for {channel_name}")
                self.tracker.remove_channel(channel_id)
                return

            channel = guild.get_channel(channel_id)
            if not channel:
                logger.info(f"Channel {channel_name} already deleted, removing from tracking")
                self.tracker.remove_channel(channel_id)
                return

            # Ensure it's a voice channel before checking members
            if not isinstance(channel, discord.VoiceChannel):
                logger.warning(f"Channel {channel_name} is not a voice channel, removing from tracking")
                self.tracker.remove_channel(channel_id)
                return

            # Final check: make sure channel is still empty before deleting
            if len(channel.members) > 0:
                logger.info(f"Channel {channel_name} is no longer empty, skipping cleanup")
                self.tracker.update_channel_status(channel_id, False)
                return

            # Delete the channel
            await channel.delete(reason="Automatic cleanup - empty for 15+ minutes")
            self.tracker.remove_channel(channel_id)

            logger.info(f"✅ Cleaned up empty voice channel: {channel_name} (ID: {channel_id})")

        except discord.NotFound:
            # Channel was already deleted
            logger.info(f"Channel {channel_data.get('name', 'unknown')} was already deleted")
            self.tracker.remove_channel(int(channel_data["channel_id"]))
        except discord.Forbidden:
            logger.error(f"Missing permissions to delete channel {channel_data.get('name', 'unknown')}")
        except Exception as e:
            logger.error(f"Error cleaning up channel {channel_data.get('name', 'unknown')}: {e}")

    def get_tracker(self) -> VoiceChannelTracker:
        """
        Get the voice channel tracker instance.

        Returns:
            VoiceChannelTracker instance
        """
        return self.tracker

    def get_stats(self) -> dict:
        """
        Get cleanup service statistics.

        Returns:
            Dictionary with service statistics
        """
        all_channels = self.tracker.get_all_tracked_channels()
        empty_channels = [ch for ch in all_channels if ch.get("empty_since")]

        return {
            "running": self._running,
            "total_tracked": len(all_channels),
            "empty_channels": len(empty_channels),
            "cleanup_interval": self.cleanup_interval,
            "empty_threshold": self.empty_threshold
        }