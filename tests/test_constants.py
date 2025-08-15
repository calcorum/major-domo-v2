"""
Tests for application constants

Validates that constants have sensible values.
"""
import pytest

from constants import (
    DISCORD_EMBED_LIMIT,
    DISCORD_FIELD_VALUE_LIMIT,
    DISCORD_EMBED_DESCRIPTION_LIMIT,
    WEEKS_PER_SEASON,
    GAMES_PER_WEEK,
    MODERN_STATS_START_SEASON,
    API_VERSION,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
    PITCHER_POSITIONS,
    POSITION_FIELDERS,
    ALL_POSITIONS,
    DEFAULT_PICK_MINUTES,
    DRAFT_ROUNDS
)


class TestDiscordLimits:
    """Test Discord API limits are reasonable."""
    
    def test_discord_limits_are_positive(self):
        """Test that all Discord limits are positive integers."""
        assert DISCORD_EMBED_LIMIT > 0
        assert DISCORD_FIELD_VALUE_LIMIT > 0
        assert DISCORD_EMBED_DESCRIPTION_LIMIT > 0
        
        assert isinstance(DISCORD_EMBED_LIMIT, int)
        assert isinstance(DISCORD_FIELD_VALUE_LIMIT, int)
        assert isinstance(DISCORD_EMBED_DESCRIPTION_LIMIT, int)
    
    def test_discord_limits_hierarchy(self):
        """Test that Discord limits have sensible relationships."""
        # Description should be larger than field values
        assert DISCORD_EMBED_DESCRIPTION_LIMIT > DISCORD_FIELD_VALUE_LIMIT
        
        # Total embed limit should be larger than description limit
        assert DISCORD_EMBED_LIMIT > DISCORD_EMBED_DESCRIPTION_LIMIT


class TestLeagueConstants:
    """Test league-specific constants."""
    
    def test_league_constants_are_positive(self):
        """Test that league constants are positive."""
        assert WEEKS_PER_SEASON > 0
        assert GAMES_PER_WEEK > 0
        assert MODERN_STATS_START_SEASON > 0
        
        assert isinstance(WEEKS_PER_SEASON, int)
        assert isinstance(GAMES_PER_WEEK, int)
        assert isinstance(MODERN_STATS_START_SEASON, int)
    
    def test_league_constants_are_reasonable(self):
        """Test that league constants have reasonable values."""
        # Baseball season should be reasonable length
        assert 10 <= WEEKS_PER_SEASON <= 30
        
        # Games per week should be reasonable
        assert 1 <= GAMES_PER_WEEK <= 7
        
        # Modern stats era should be reasonable
        assert 1 <= MODERN_STATS_START_SEASON <= 20


class TestAPIConstants:
    """Test API-related constants."""
    
    def test_api_version_format(self):
        """Test that API version is properly formatted."""
        assert isinstance(API_VERSION, str)
        assert API_VERSION.startswith("v")
        assert API_VERSION[1:].isdigit()  # Should be like "v3"
    
    def test_timeout_and_retry_values(self):
        """Test that timeout and retry values are reasonable."""
        assert DEFAULT_TIMEOUT > 0
        assert MAX_RETRIES > 0
        
        assert isinstance(DEFAULT_TIMEOUT, int)
        assert isinstance(MAX_RETRIES, int)
        
        # Should be reasonable values
        assert 1 <= DEFAULT_TIMEOUT <= 60  # 1-60 seconds
        assert 1 <= MAX_RETRIES <= 10      # 1-10 retries


class TestPositionConstants:
    """Test baseball position constants."""
    
    def test_position_sets_are_sets(self):
        """Test that position constants are sets."""
        assert isinstance(PITCHER_POSITIONS, set)
        assert isinstance(POSITION_FIELDERS, set)
        assert isinstance(ALL_POSITIONS, set)
    
    def test_position_sets_not_empty(self):
        """Test that position sets are not empty."""
        assert len(PITCHER_POSITIONS) > 0
        assert len(POSITION_FIELDERS) > 0
        assert len(ALL_POSITIONS) > 0
    
    def test_position_sets_no_overlap(self):
        """Test that pitcher and fielder positions don't overlap."""
        overlap = PITCHER_POSITIONS & POSITION_FIELDERS
        assert len(overlap) == 0, f"Found overlapping positions: {overlap}"
    
    def test_all_positions_is_union(self):
        """Test that ALL_POSITIONS is the union of pitcher and fielder positions."""
        expected_all = PITCHER_POSITIONS | POSITION_FIELDERS
        assert ALL_POSITIONS == expected_all
    
    def test_position_values_are_strings(self):
        """Test that all position values are strings."""
        for position in ALL_POSITIONS:
            assert isinstance(position, str)
            assert len(position) > 0  # Not empty strings
    
    def test_common_positions_exist(self):
        """Test that common baseball positions exist."""
        # Common pitcher positions
        assert "SP" in PITCHER_POSITIONS or "P" in PITCHER_POSITIONS
        assert "RP" in PITCHER_POSITIONS or "P" in PITCHER_POSITIONS
        
        # Common fielder positions
        common_fielders = {"C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"}
        found_fielders = common_fielders & POSITION_FIELDERS
        assert len(found_fielders) > 0, "No common fielder positions found"


class TestDraftConstants:
    """Test draft-related constants."""
    
    def test_draft_constants_are_positive(self):
        """Test that draft constants are positive."""
        assert DEFAULT_PICK_MINUTES > 0
        assert DRAFT_ROUNDS > 0
        
        assert isinstance(DEFAULT_PICK_MINUTES, int)
        assert isinstance(DRAFT_ROUNDS, int)
    
    def test_draft_constants_are_reasonable(self):
        """Test that draft constants have reasonable values."""
        # Pick minutes should be reasonable
        assert 1 <= DEFAULT_PICK_MINUTES <= 60
        
        # Draft rounds should be reasonable for fantasy baseball
        assert 10 <= DRAFT_ROUNDS <= 50