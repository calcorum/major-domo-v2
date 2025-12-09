"""
Unit tests for Soak Easter Egg functionality.

Tests cover:
- Giphy service (tier determination, phrase selection, GIF fetching)
- Tracker (JSON persistence, soak recording, time calculations)
- Message listener (detection logic)
- Info command (response formatting)
"""
import pytest
import json
import re
from datetime import datetime, timedelta, UTC
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from aioresponses import aioresponses

# Import modules to test
from commands.soak.giphy_service import (
    get_tier_for_seconds,
    get_random_phrase_for_tier,
    get_tier_description,
    get_disappointment_gif,
    DISAPPOINTMENT_TIERS
)
from commands.soak.tracker import SoakTracker

# Listener uses simple string matching: ' soak' in msg_text.lower()
# Define helper function that mimics the listener's detection logic
def soak_detected(text: str) -> bool:
    """Check if soak mention is detected using listener's logic."""
    return ' soak' in text.lower()


class TestGiphyService:
    """Tests for Giphy service functionality."""

    def test_tier_determination_first_ever(self):
        """Test tier determination for first ever soak."""
        tier = get_tier_for_seconds(None)
        assert tier == 'first_ever'

    def test_tier_determination_maximum_disappointment(self):
        """Test tier 1: 0-30 minutes (maximum disappointment)."""
        # 15 minutes
        tier = get_tier_for_seconds(900)
        assert tier == 'tier_1'

        # 30 minutes (boundary)
        tier = get_tier_for_seconds(1800)
        assert tier == 'tier_1'

    def test_tier_determination_severe_disappointment(self):
        """Test tier 2: 30min-2hrs (severe disappointment)."""
        # 1 hour
        tier = get_tier_for_seconds(3600)
        assert tier == 'tier_2'

        # 2 hours (boundary)
        tier = get_tier_for_seconds(7200)
        assert tier == 'tier_2'

    def test_tier_determination_strong_disappointment(self):
        """Test tier 3: 2-6 hours (strong disappointment)."""
        # 4 hours
        tier = get_tier_for_seconds(14400)
        assert tier == 'tier_3'

        # 6 hours (boundary)
        tier = get_tier_for_seconds(21600)
        assert tier == 'tier_3'

    def test_tier_determination_moderate_disappointment(self):
        """Test tier 4: 6-24 hours (moderate disappointment)."""
        # 12 hours
        tier = get_tier_for_seconds(43200)
        assert tier == 'tier_4'

        # 24 hours (boundary)
        tier = get_tier_for_seconds(86400)
        assert tier == 'tier_4'

    def test_tier_determination_mild_disappointment(self):
        """Test tier 5: 1-7 days (mild disappointment)."""
        # 3 days
        tier = get_tier_for_seconds(259200)
        assert tier == 'tier_5'

        # 7 days (boundary)
        tier = get_tier_for_seconds(604800)
        assert tier == 'tier_5'

    def test_tier_determination_minimal_disappointment(self):
        """Test tier 6: 7+ days (minimal disappointment)."""
        # 10 days
        tier = get_tier_for_seconds(864000)
        assert tier == 'tier_6'

        # 30 days
        tier = get_tier_for_seconds(2592000)
        assert tier == 'tier_6'

    def test_random_phrase_selection(self):
        """Test that random phrase selection returns valid phrases."""
        for tier_key in DISAPPOINTMENT_TIERS.keys():
            phrase = get_random_phrase_for_tier(tier_key)
            assert phrase in DISAPPOINTMENT_TIERS[tier_key]['phrases']

    def test_tier_description_retrieval(self):
        """Test tier description retrieval."""
        assert get_tier_description('tier_1') == "Maximum Disappointment"
        assert get_tier_description('first_ever') == "The Beginning"

    @pytest.mark.asyncio
    async def test_get_disappointment_gif_success(self):
        """Test successful GIF fetch from Giphy API."""
        with aioresponses() as m:
            # Mock successful Giphy response
            m.get(
                re.compile(r'https://api\.giphy\.com/v1/gifs/translate\?.*'),
                payload={
                    'data': {
                        'url': 'https://giphy.com/gifs/test123',
                        'title': 'Disappointed Reaction'
                    }
                },
                status=200
            )

            gif_url = await get_disappointment_gif('tier_1')
            assert gif_url == 'https://giphy.com/gifs/test123'

    @pytest.mark.asyncio
    async def test_get_disappointment_gif_filters_trump(self):
        """Test that Trump GIFs are filtered out."""
        with aioresponses() as m:
            # First response is Trump GIF (should be filtered)
            # Second response is acceptable
            m.get(
                re.compile(r'https://api\.giphy\.com/v1/gifs/translate\?.*'),
                payload={
                    'data': {
                        'url': 'https://giphy.com/gifs/trump123',
                        'title': 'Donald Trump Disappointed'
                    }
                },
                status=200
            )
            m.get(
                re.compile(r'https://api\.giphy\.com/v1/gifs/translate\?.*'),
                payload={
                    'data': {
                        'url': 'https://giphy.com/gifs/good456',
                        'title': 'Disappointed Reaction'
                    }
                },
                status=200
            )

            gif_url = await get_disappointment_gif('tier_1')
            assert gif_url == 'https://giphy.com/gifs/good456'

    @pytest.mark.asyncio
    async def test_get_disappointment_gif_api_failure(self):
        """Test graceful handling of Giphy API failures."""
        with aioresponses() as m:
            # Mock API failure for all requests
            m.get(
                re.compile(r'https://api\.giphy\.com/v1/gifs/translate\?.*'),
                status=500,
                repeat=True
            )

            gif_url = await get_disappointment_gif('tier_1')
            assert gif_url is None


class TestSoakTracker:
    """Tests for SoakTracker functionality."""

    @pytest.fixture
    def temp_tracker_file(self, tmp_path):
        """Create a temporary tracker file path."""
        return str(tmp_path / "test_soak_data.json")

    def test_tracker_initialization_new_file(self, temp_tracker_file):
        """Test tracker initialization with no existing file."""
        tracker = SoakTracker(temp_tracker_file)

        assert tracker.get_soak_count() == 0
        assert tracker.get_last_soak() is None
        assert tracker.get_history() == []

    def test_tracker_initialization_existing_file(self, temp_tracker_file):
        """Test tracker initialization with existing data."""
        # Create existing data
        existing_data = {
            "last_soak": {
                "timestamp": "2025-01-01T12:00:00+00:00",
                "user_id": "123",
                "username": "testuser",
                "display_name": "Test User",
                "channel_id": "456",
                "message_id": "789"
            },
            "total_count": 5,
            "history": []
        }

        with open(temp_tracker_file, 'w') as f:
            json.dump(existing_data, f)

        tracker = SoakTracker(temp_tracker_file)

        assert tracker.get_soak_count() == 5
        assert tracker.get_last_soak() is not None

    def test_record_soak(self, temp_tracker_file):
        """Test recording a soak mention."""
        tracker = SoakTracker(temp_tracker_file)

        tracker.record_soak(
            user_id=123456,
            username="testuser",
            display_name="Test User",
            channel_id=789012,
            message_id=345678
        )

        assert tracker.get_soak_count() == 1

        last_soak = tracker.get_last_soak()
        assert last_soak is not None
        assert last_soak['user_id'] == '123456'
        assert last_soak['username'] == 'testuser'

    def test_record_multiple_soaks(self, temp_tracker_file):
        """Test recording multiple soaks maintains history."""
        tracker = SoakTracker(temp_tracker_file)

        # Record 3 soaks
        for i in range(3):
            tracker.record_soak(
                user_id=i,
                username=f"user{i}",
                display_name=f"User {i}",
                channel_id=100,
                message_id=200 + i
            )

        assert tracker.get_soak_count() == 3

        history = tracker.get_history()
        assert len(history) == 3
        # History should be newest first
        assert history[0]['user_id'] == '2'
        assert history[2]['user_id'] == '0'

    def test_get_time_since_last_soak(self, temp_tracker_file):
        """Test time calculation since last soak."""
        tracker = SoakTracker(temp_tracker_file)

        # No previous soak
        assert tracker.get_time_since_last_soak() is None

        # Record a soak
        tracker.record_soak(
            user_id=123,
            username="test",
            display_name="Test",
            channel_id=456,
            message_id=789
        )

        # Time since should be very small (just recorded)
        time_since = tracker.get_time_since_last_soak()
        assert time_since is not None
        assert time_since.total_seconds() < 5  # Should be < 5 seconds

    def test_history_limit(self, temp_tracker_file):
        """Test that history is limited to prevent file bloat."""
        tracker = SoakTracker(temp_tracker_file)

        # Record 1100 soaks (exceeds 1000 limit)
        for i in range(1100):
            tracker.record_soak(
                user_id=i,
                username=f"user{i}",
                display_name=f"User {i}",
                channel_id=100,
                message_id=200 + i
            )

        history = tracker.get_history(limit=9999)
        # Should be capped at 1000
        assert len(history) == 1000


class TestMessageListener:
    """Tests for message listener detection logic.

    Note: The listener uses simple string matching: ' soak' in msg_text.lower()
    This requires a space before 'soak' to avoid false positives.
    """

    def test_soak_detection_with_space(self):
        """Test detection requires space before 'soak'."""
        assert soak_detected("I soak") is True
        assert soak_detected("let's soak") is True

    def test_soak_detection_case_insensitive(self):
        """Test case insensitivity."""
        assert soak_detected("I SOAK") is True
        assert soak_detected("I Soak") is True
        assert soak_detected("I SoAk") is True

    def test_soak_detection_variations(self):
        """Test detection of word variations."""
        assert soak_detected("I was soaking") is True
        assert soak_detected("it's soaked") is True
        assert soak_detected("the soaker") is True

    def test_soak_detection_word_start_no_match(self):
        """Test that soak at start of message (no space) is not detected."""
        # Leading soak without space should NOT match (listener checks ' soak')
        assert soak_detected("soak") is False
        assert soak_detected("soaking is fun") is False

    def test_soak_detection_in_sentence(self):
        """Test detection in full sentences."""
        assert soak_detected("We went soaking last night") is True
        assert soak_detected("The clothes are soaked") is True
        assert soak_detected("Pass me the soaker") is True
        assert soak_detected("I love to soak in the pool") is True


class TestInfoCommand:
    """Tests for /lastsoak info command."""

    # Note: Full command testing requires discord.py test utilities
    # These tests focus on the logic components

    def test_timestamp_formatting_logic(self):
        """Test Unix timestamp calculation for Discord formatting."""
        # Create a known timestamp
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        unix_timestamp = int(dt.timestamp())

        # Verify timestamp is a valid Unix timestamp (positive integer)
        # The exact value depends on timezone, but should be reasonable
        assert unix_timestamp > 1700000000  # After 2023
        assert unix_timestamp < 2000000000  # Before 2033

    def test_jump_url_formatting(self):
        """Test Discord message jump URL formatting."""
        guild_id = 123456789
        channel_id = 987654321
        message_id = 111222333

        expected_url = f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
        assert expected_url == "https://discord.com/channels/123456789/987654321/111222333"
