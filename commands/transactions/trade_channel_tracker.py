"""
Trade Channel Tracker

Provides persistent tracking of bot-created trade discussion channels using JSON file storage.
"""
import json
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Any

import discord

from utils.logging import get_contextual_logger

logger = get_contextual_logger(f'{__name__}.TradeChannelTracker')


class TradeChannelTracker:
    """
    Tracks bot-created trade discussion channels with JSON file persistence.

    Features:
    - Persistent storage across bot restarts
    - Channel creation and tracking by trade ID
    - Lookup by trade ID or channel ID
    - Automatic stale entry removal
    """

    def __init__(self, data_file: str = "storage/trade_channels.json"):
        """
        Initialize the trade channel tracker.

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
                    logger.debug(f"Loaded {len(self._data.get('trade_channels', {}))} tracked trade channels")
            else:
                self._data = {"trade_channels": {}}
                logger.info("No existing trade channel data found, starting fresh")
        except Exception as e:
            logger.error(f"Failed to load trade channel data: {e}")
            self._data = {"trade_channels": {}}

    def save_data(self) -> None:
        """Save channel data to JSON file."""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self._data, f, indent=2, default=str)
            logger.debug("Trade channel data saved successfully")
        except Exception as e:
            logger.error(f"Failed to save trade channel data: {e}")

    def add_channel(
        self,
        channel: discord.TextChannel,
        trade_id: str,
        team1_abbrev: str,
        team2_abbrev: str,
        creator_id: int
    ) -> None:
        """
        Add a new trade channel to tracking.

        Args:
            channel: Discord text channel object
            trade_id: Unique trade identifier
            team1_abbrev: First team abbreviation
            team2_abbrev: Second team abbreviation
            creator_id: Discord user ID who created the trade
        """
        self._data.setdefault("trade_channels", {})[str(channel.id)] = {
            "channel_id": str(channel.id),
            "guild_id": str(channel.guild.id),
            "name": channel.name,
            "trade_id": trade_id,
            "team1_abbrev": team1_abbrev,
            "team2_abbrev": team2_abbrev,
            "created_at": datetime.now(UTC).isoformat(),
            "creator_id": str(creator_id)
        }
        self.save_data()
        logger.info(f"Added trade channel to tracking: {channel.name} (ID: {channel.id}, Trade: {trade_id})")

    def remove_channel(self, channel_id: int) -> None:
        """
        Remove channel from tracking.

        Args:
            channel_id: Discord channel ID
        """
        channels = self._data.get("trade_channels", {})
        channel_key = str(channel_id)

        if channel_key in channels:
            channel_data = channels[channel_key]
            trade_id = channel_data.get("trade_id", "unknown")
            channel_name = channel_data["name"]
            del channels[channel_key]
            self.save_data()
            logger.info(f"Removed trade channel from tracking: {channel_name} (ID: {channel_id}, Trade: {trade_id})")

    def get_channel_by_trade_id(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """
        Get channel data for a specific trade.

        Args:
            trade_id: Trade identifier

        Returns:
            Channel data dictionary or None if not found
        """
        channels = self._data.get("trade_channels", {})
        for channel_data in channels.values():
            if channel_data.get("trade_id") == trade_id:
                return channel_data
        return None

    def get_channel_by_id(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """
        Get data for a specific tracked channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            Channel data dictionary or None if not tracked
        """
        channels = self._data.get("trade_channels", {})
        return channels.get(str(channel_id))

    def get_all_tracked_channels(self) -> List[Dict[str, Any]]:
        """
        Get all currently tracked trade channels.

        Returns:
            List of all tracked channel data dictionaries
        """
        return list(self._data.get("trade_channels", {}).values())

    def cleanup_stale_entries(self, valid_channel_ids: List[int]) -> int:
        """
        Remove tracking entries for channels that no longer exist.

        Args:
            valid_channel_ids: List of channel IDs that still exist in Discord

        Returns:
            Number of stale entries removed
        """
        channels = self._data.get("trade_channels", {})
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
            trade_id = channels[channel_id_str].get("trade_id", "unknown")
            del channels[channel_id_str]
            logger.info(f"Removed stale tracking entry: {channel_name} (ID: {channel_id_str}, Trade: {trade_id})")

        if stale_entries:
            self.save_data()

        return len(stale_entries)
