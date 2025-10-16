"""
Tests for application configuration

Validates that config values have sensible defaults.
"""
import pytest

from config import get_config, PITCHER_POSITIONS, POSITION_FIELDERS, ALL_POSITIONS


class TestDiscordLimits:
    """Test Discord API limits are reasonable."""

    def test_discord_limits_are_positive(self):
        """Test that all Discord limits are positive integers."""
        config = get_config()
        assert config.discord_embed_limit > 0
        assert config.discord_field_value_limit > 0
        assert config.discord_embed_description_limit > 0

        assert isinstance(config.discord_embed_limit, int)
        assert isinstance(config.discord_field_value_limit, int)
        assert isinstance(config.discord_embed_description_limit, int)

    def test_discord_limits_hierarchy(self):
        """Test that Discord limits have sensible relationships."""
        config = get_config()
        # Description should be larger than field values
        assert config.discord_embed_description_limit > config.discord_field_value_limit

        # Total embed limit should be larger than description limit
        assert config.discord_embed_limit > config.discord_embed_description_limit


class TestLeagueConstants:
    """Test league-specific constants."""

    def test_league_constants_are_positive(self):
        """Test that league constants are positive."""
        config = get_config()
        assert config.weeks_per_season > 0
        assert config.games_per_week > 0
        assert config.modern_stats_start_season > 0

        assert isinstance(config.weeks_per_season, int)
        assert isinstance(config.games_per_week, int)
        assert isinstance(config.modern_stats_start_season, int)

    def test_league_constants_are_reasonable(self):
        """Test that league constants have reasonable values."""
        config = get_config()
        # Baseball season should be reasonable length
        assert 10 <= config.weeks_per_season <= 30

        # Games per week should be reasonable
        assert 1 <= config.games_per_week <= 7

        # Modern stats era should be reasonable
        assert 1 <= config.modern_stats_start_season <= 20


class TestAPIConstants:
    """Test API-related constants."""

    def test_api_version_format(self):
        """Test that API version is properly formatted."""
        config = get_config()
        assert isinstance(config.api_version, str)
        assert config.api_version.startswith("v")
        assert config.api_version[1:].isdigit()  # Should be like "v3"

    def test_timeout_and_retry_values(self):
        """Test that timeout and retry values are reasonable."""
        config = get_config()
        assert config.default_timeout > 0
        assert config.max_retries > 0

        assert isinstance(config.default_timeout, int)
        assert isinstance(config.max_retries, int)

        # Should be reasonable values
        assert 1 <= config.default_timeout <= 60  # 1-60 seconds
        assert 1 <= config.max_retries <= 10      # 1-10 retries


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
        config = get_config()
        assert config.default_pick_minutes > 0
        assert config.draft_rounds > 0

        assert isinstance(config.default_pick_minutes, int)
        assert isinstance(config.draft_rounds, int)

    def test_draft_constants_are_reasonable(self):
        """Test that draft constants have reasonable values."""
        config = get_config()
        # Pick minutes should be reasonable
        assert 1 <= config.default_pick_minutes <= 60

        # Draft rounds should be reasonable for fantasy baseball
        assert 10 <= config.draft_rounds <= 50