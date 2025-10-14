"""
Soak Tracker

Provides persistent tracking of "soak" mentions using JSON file storage.
"""
import json
import logging
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(f'{__name__}.SoakTracker')


class SoakTracker:
    """
    Tracks "soak" mentions with JSON file persistence.

    Features:
    - Persistent storage across bot restarts
    - Mention recording with full history
    - Time-based calculations for disappointment tiers
    """

    def __init__(self, data_file: str = "storage/soak_data.json"):
        """
        Initialize the soak tracker.

        Args:
            data_file: Path to the JSON data file
        """
        self.data_file = Path(data_file)
        self.data_file.parent.mkdir(exist_ok=True)
        self._data: Dict[str, Any] = {}
        self.load_data()

    def load_data(self) -> None:
        """Load soak data from JSON file."""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r') as f:
                    self._data = json.load(f)
                    logger.debug(f"Loaded soak data: {self._data.get('total_count', 0)} total soaks")
            else:
                self._data = {
                    "last_soak": None,
                    "total_count": 0,
                    "history": []
                }
                logger.info("No existing soak data found, starting fresh")
        except Exception as e:
            logger.error(f"Failed to load soak data: {e}")
            self._data = {
                "last_soak": None,
                "total_count": 0,
                "history": []
            }

    def save_data(self) -> None:
        """Save soak data to JSON file."""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self._data, f, indent=2, default=str)
            logger.debug("Soak data saved successfully")
        except Exception as e:
            logger.error(f"Failed to save soak data: {e}")

    def record_soak(
        self,
        user_id: int,
        username: str,
        display_name: str,
        channel_id: int,
        message_id: int
    ) -> None:
        """
        Record a new soak mention.

        Args:
            user_id: Discord user ID who mentioned soak
            username: Discord username
            display_name: Discord display name
            channel_id: Channel where soak was mentioned
            message_id: Message ID containing the mention
        """
        soak_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "user_id": str(user_id),
            "username": username,
            "display_name": display_name,
            "channel_id": str(channel_id),
            "message_id": str(message_id)
        }

        # Update last_soak
        self._data["last_soak"] = soak_data

        # Increment counter
        self._data["total_count"] = self._data.get("total_count", 0) + 1

        # Add to history (newest first)
        history = self._data.get("history", [])
        history.insert(0, soak_data)

        # Optional: Limit history to last 1000 entries to prevent file bloat
        if len(history) > 1000:
            history = history[:1000]

        self._data["history"] = history

        self.save_data()

        logger.info(f"Recorded soak by {username} (ID: {user_id}) in channel {channel_id}")

    def get_last_soak(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent soak data.

        Returns:
            Dictionary with soak data, or None if no soaks recorded
        """
        return self._data.get("last_soak")

    def get_time_since_last_soak(self) -> Optional[timedelta]:
        """
        Calculate time elapsed since the last soak mention.

        Returns:
            timedelta object, or None if no previous soaks
        """
        last_soak = self.get_last_soak()
        if not last_soak:
            return None

        try:
            # Parse ISO format timestamp
            last_timestamp_str = last_soak["timestamp"]
            if last_timestamp_str.endswith('Z'):
                last_timestamp_str = last_timestamp_str[:-1] + '+00:00'

            last_timestamp = datetime.fromisoformat(last_timestamp_str.replace('Z', '+00:00'))

            # Ensure both times are timezone-aware
            if last_timestamp.tzinfo is None:
                last_timestamp = last_timestamp.replace(tzinfo=UTC)

            current_time = datetime.now(UTC)
            time_elapsed = current_time - last_timestamp

            return time_elapsed

        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Invalid timestamp in last soak data: {e}")
            return None

    def get_soak_count(self) -> int:
        """
        Get the total number of soak mentions.

        Returns:
            Total count across all time
        """
        return self._data.get("total_count", 0)

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent soak mention history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of soak data dictionaries (newest first)
        """
        history = self._data.get("history", [])
        return history[:limit]
