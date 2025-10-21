"""
Scorecard Tracker

Provides persistent tracking of published scorecards per Discord text channel using JSON file storage.
"""
import json
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(f'{__name__}.ScorecardTracker')


class ScorecardTracker:
    """
    Tracks published Google Sheets scorecards linked to Discord text channels.

    Features:
    - Persistent storage across bot restarts
    - Channel-to-scorecard URL mapping
    - Automatic stale entry cleanup
    - Timestamp tracking for monitoring
    """

    def __init__(self, data_file: str = "data/scorecards.json"):
        """
        Initialize the scorecard tracker.

        Args:
            data_file: Path to the JSON data file
        """
        self.data_file = Path(data_file)
        self.data_file.parent.mkdir(exist_ok=True)
        self._data: Dict[str, any] = {}
        self.load_data()

    def load_data(self) -> None:
        """Load scorecard data from JSON file."""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r') as f:
                    self._data = json.load(f)
                    logger.debug(f"Loaded {len(self._data.get('scorecards', {}))} tracked scorecards")
            else:
                self._data = {"scorecards": {}}
                logger.info("No existing scorecard data found, starting fresh")
        except Exception as e:
            logger.error(f"Failed to load scorecard data: {e}")
            self._data = {"scorecards": {}}

    def save_data(self) -> None:
        """Save scorecard data to JSON file."""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self._data, f, indent=2, default=str)
            logger.debug("Scorecard data saved successfully")
        except Exception as e:
            logger.error(f"Failed to save scorecard data: {e}")

    def publish_scorecard(
        self,
        text_channel_id: int,
        sheet_url: str,
        publisher_id: int
    ) -> None:
        """
        Link a scorecard to a text channel.

        Args:
            text_channel_id: Discord text channel ID
            sheet_url: Google Sheets URL or key
            publisher_id: Discord user ID who published the scorecard
        """
        self._data.setdefault("scorecards", {})[str(text_channel_id)] = {
            "text_channel_id": str(text_channel_id),
            "sheet_url": sheet_url,
            "published_at": datetime.now(UTC).isoformat(),
            "last_updated": datetime.now(UTC).isoformat(),
            "publisher_id": str(publisher_id)
        }
        self.save_data()
        logger.info(f"Published scorecard to channel {text_channel_id}: {sheet_url}")

    def unpublish_scorecard(self, text_channel_id: int) -> bool:
        """
        Remove scorecard from a text channel.

        Args:
            text_channel_id: Discord text channel ID

        Returns:
            True if scorecard was removed, False if not found
        """
        scorecards = self._data.get("scorecards", {})
        channel_key = str(text_channel_id)

        if channel_key in scorecards:
            del scorecards[channel_key]
            self.save_data()
            logger.info(f"Unpublished scorecard from channel {text_channel_id}")
            return True

        return False

    def get_scorecard(self, text_channel_id: int) -> Optional[str]:
        """
        Get scorecard URL for a text channel.

        Args:
            text_channel_id: Discord text channel ID

        Returns:
            Sheet URL if published, None otherwise
        """
        scorecards = self._data.get("scorecards", {})
        scorecard_data = scorecards.get(str(text_channel_id))
        return scorecard_data["sheet_url"] if scorecard_data else None

    def get_all_scorecards(self) -> List[Tuple[int, str]]:
        """
        Get all published scorecards.

        Returns:
            List of (text_channel_id, sheet_url) tuples
        """
        scorecards = self._data.get("scorecards", {})
        return [
            (int(channel_id), data["sheet_url"])
            for channel_id, data in scorecards.items()
        ]

    def update_timestamp(self, text_channel_id: int) -> None:
        """
        Update the last_updated timestamp for a scorecard.

        Args:
            text_channel_id: Discord text channel ID
        """
        scorecards = self._data.get("scorecards", {})
        channel_key = str(text_channel_id)

        if channel_key in scorecards:
            scorecards[channel_key]["last_updated"] = datetime.now(UTC).isoformat()
            self.save_data()

    def cleanup_stale_entries(self, valid_channel_ids: List[int]) -> int:
        """
        Remove tracking entries for text channels that no longer exist.

        Args:
            valid_channel_ids: List of channel IDs that still exist in Discord

        Returns:
            Number of stale entries removed
        """
        scorecards = self._data.get("scorecards", {})
        stale_entries = []

        for channel_id_str in scorecards.keys():
            try:
                channel_id = int(channel_id_str)
                if channel_id not in valid_channel_ids:
                    stale_entries.append(channel_id_str)
            except (ValueError, TypeError):
                logger.warning(f"Invalid channel ID in scorecard data: {channel_id_str}")
                stale_entries.append(channel_id_str)

        # Remove stale entries
        for channel_id_str in stale_entries:
            del scorecards[channel_id_str]
            logger.info(f"Removed stale scorecard entry for channel ID: {channel_id_str}")

        if stale_entries:
            self.save_data()

        return len(stale_entries)
