"""
Voice Channel Tracker

Provides persistent tracking of bot-created voice channels using JSON file storage.
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import discord

logger = logging.getLogger(f'{__name__}.VoiceChannelTracker')


class VoiceChannelTracker:
    """
    Tracks bot-created voice channels with JSON file persistence.

    Features:
    - Persistent storage across bot restarts
    - Channel creation and status tracking
    - Cleanup candidate identification
    - Automatic stale entry removal
    """

    def __init__(self, data_file: str = "data/voice_channels.json"):
        """
        Initialize the voice channel tracker.

        Args:
            data_file: Path to the JSON data file
        """
        self.data_file = Path(data_file)
        self.data_file.parent.mkdir(exist_ok=True)
        self._data: Dict[str, Any] = {}
        self.load_data()

    def load_data(self) -> None:
        """Load channel data from JSON file."""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r') as f:
                    self._data = json.load(f)
                    logger.debug(f"Loaded {len(self._data.get('voice_channels', {}))} tracked channels")
            else:
                self._data = {"voice_channels": {}}
                logger.info("No existing voice channel data found, starting fresh")
        except Exception as e:
            logger.error(f"Failed to load voice channel data: {e}")
            self._data = {"voice_channels": {}}

    def save_data(self) -> None:
        """Save channel data to JSON file."""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self._data, f, indent=2, default=str)
            logger.debug("Voice channel data saved successfully")
        except Exception as e:
            logger.error(f"Failed to save voice channel data: {e}")

    def add_channel(
        self,
        channel: discord.VoiceChannel,
        channel_type: str,
        creator_id: int
    ) -> None:
        """
        Add a new channel to tracking.

        Args:
            channel: Discord voice channel object
            channel_type: Type of channel ('public' or 'private')
            creator_id: Discord user ID who created the channel
        """
        self._data.setdefault("voice_channels", {})[str(channel.id)] = {
            "channel_id": str(channel.id),
            "guild_id": str(channel.guild.id),
            "name": channel.name,
            "type": channel_type,
            "created_at": datetime.utcnow().isoformat(),
            "last_checked": datetime.utcnow().isoformat(),
            "empty_since": None,
            "creator_id": str(creator_id)
        }
        self.save_data()
        logger.info(f"Added channel to tracking: {channel.name} (ID: {channel.id})")

    def update_channel_status(self, channel_id: int, is_empty: bool) -> None:
        """
        Update channel empty status.

        Args:
            channel_id: Discord channel ID
            is_empty: Whether the channel is currently empty
        """
        channels = self._data.get("voice_channels", {})
        channel_key = str(channel_id)

        if channel_key in channels:
            channel_data = channels[channel_key]
            channel_data["last_checked"] = datetime.utcnow().isoformat()

            if is_empty and channel_data["empty_since"] is None:
                # Channel just became empty
                channel_data["empty_since"] = datetime.utcnow().isoformat()
                logger.debug(f"Channel {channel_data['name']} became empty")
            elif not is_empty and channel_data["empty_since"] is not None:
                # Channel is no longer empty
                channel_data["empty_since"] = None
                logger.debug(f"Channel {channel_data['name']} is no longer empty")

            self.save_data()

    def remove_channel(self, channel_id: int) -> None:
        """
        Remove channel from tracking.

        Args:
            channel_id: Discord channel ID
        """
        channels = self._data.get("voice_channels", {})
        channel_key = str(channel_id)

        if channel_key in channels:
            channel_name = channels[channel_key]["name"]
            del channels[channel_key]
            self.save_data()
            logger.info(f"Removed channel from tracking: {channel_name} (ID: {channel_id})")

    def get_channels_for_cleanup(self, empty_threshold_minutes: int = 15) -> List[Dict[str, Any]]:
        """
        Get channels that should be deleted based on empty duration.

        Args:
            empty_threshold_minutes: Minutes a channel must be empty before cleanup

        Returns:
            List of channel data dictionaries ready for cleanup
        """
        cleanup_candidates = []
        cutoff_time = datetime.utcnow() - timedelta(minutes=empty_threshold_minutes)

        for channel_data in self._data.get("voice_channels", {}).values():
            if channel_data["empty_since"]:
                try:
                    # Parse empty_since timestamp
                    empty_since_str = channel_data["empty_since"]
                    # Handle both with and without timezone info
                    if empty_since_str.endswith('Z'):
                        empty_since_str = empty_since_str[:-1] + '+00:00'

                    empty_since = datetime.fromisoformat(empty_since_str.replace('Z', '+00:00'))

                    # Remove timezone info for comparison (both times are UTC)
                    if empty_since.tzinfo:
                        empty_since = empty_since.replace(tzinfo=None)

                    if empty_since <= cutoff_time:
                        cleanup_candidates.append(channel_data)
                        logger.debug(f"Channel {channel_data['name']} ready for cleanup (empty since {empty_since})")

                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid timestamp for channel {channel_data.get('name', 'unknown')}: {e}")

        return cleanup_candidates

    def get_all_tracked_channels(self) -> List[Dict[str, Any]]:
        """
        Get all currently tracked channels.

        Returns:
            List of all tracked channel data dictionaries
        """
        return list(self._data.get("voice_channels", {}).values())

    def get_tracked_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """
        Get data for a specific tracked channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            Channel data dictionary or None if not tracked
        """
        channels = self._data.get("voice_channels", {})
        return channels.get(str(channel_id))

    def cleanup_stale_entries(self, valid_channel_ids: List[int]) -> int:
        """
        Remove tracking entries for channels that no longer exist.

        Args:
            valid_channel_ids: List of channel IDs that still exist in Discord

        Returns:
            Number of stale entries removed
        """
        channels = self._data.get("voice_channels", {})
        stale_entries = []

        for channel_id_str, channel_data in channels.items():
            try:
                channel_id = int(channel_id_str)
                if channel_id not in valid_channel_ids:
                    stale_entries.append(channel_id_str)
            except (ValueError, TypeError):
                logger.warning(f"Invalid channel ID in tracking data: {channel_id_str}")
                stale_entries.append(channel_id_str)

        # Remove stale entries
        for channel_id_str in stale_entries:
            channel_name = channels[channel_id_str].get("name", "unknown")
            del channels[channel_id_str]
            logger.info(f"Removed stale tracking entry: {channel_name} (ID: {channel_id_str})")

        if stale_entries:
            self.save_data()

        return len(stale_entries)