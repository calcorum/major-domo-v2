"""
Tests for scorebug_helpers utility functions.

Tests the create_team_progress_bar function to ensure correct
win probability visualization for home and away teams.
"""
import pytest
from utils.scorebug_helpers import create_team_progress_bar


class TestCreateTeamProgressBar:
    """Tests for the create_team_progress_bar function."""

    def test_home_team_winning_75_percent(self):
        """Test progress bar when home team has 75% win probability."""
        result = create_team_progress_bar(
            win_percentage=75.0,
            away_abbrev="POR",
            home_abbrev="WV"
        )

        # Home team winning: should show dark blocks (▓) on right side
        # Arrow should extend from right side (►)
        assert "►" in result
        assert "◄" not in result
        assert "75.0%" in result
        assert "POR" in result
        assert "WV" in result

        # Should have more dark blocks (▓) than light blocks (░)
        dark_blocks = result.count("▓")
        light_blocks = result.count("░")
        assert dark_blocks > light_blocks, "Home team winning should have more dark blocks"

    def test_away_team_winning_25_percent_home(self):
        """Test progress bar when home team has only 25% win probability (away team winning)."""
        result = create_team_progress_bar(
            win_percentage=25.0,
            away_abbrev="POR",
            home_abbrev="WV"
        )

        # Away team winning: should show dark blocks (▓) on left side
        # Arrow should extend from left side (◄)
        assert "◄" in result
        assert "►" not in result
        # Percentage should show away team's win % (75.0%) on left
        assert result.startswith("75.0%"), "Percentage should be on left when away team winning"
        assert "POR" in result
        assert "WV" in result

        # Should have more dark blocks (▓) than light blocks (░)
        dark_blocks = result.count("▓")
        light_blocks = result.count("░")
        assert dark_blocks > light_blocks, "Away team winning should have more dark blocks"

    def test_even_game_50_percent(self):
        """Test progress bar when game is even at 50%."""
        result = create_team_progress_bar(
            win_percentage=50.0,
            away_abbrev="POR",
            home_abbrev="WV"
        )

        # Even game: should have equals signs on both sides
        assert "=" in result
        assert "►" not in result
        assert "◄" not in result
        # Percentage should appear on both sides for even game
        assert result.startswith("50.0%"), "Percentage should be on left for even game"
        assert result.endswith("50.0%"), "Percentage should be on right for even game"
        assert "POR" in result
        assert "WV" in result

        # All blocks should be dark (▓) for even game
        assert "░" not in result, "Even game should have no light blocks"

    def test_home_team_slight_advantage_55_percent(self):
        """Test progress bar when home team has slight advantage (55%)."""
        result = create_team_progress_bar(
            win_percentage=55.0,
            away_abbrev="NYK",
            home_abbrev="BOS"
        )

        # Home team winning: arrow extends from right
        assert "►" in result
        assert "◄" not in result
        assert "55.0%" in result

    def test_away_team_strong_advantage_30_percent_home(self):
        """Test progress bar when away team has strong advantage (home only 30%)."""
        result = create_team_progress_bar(
            win_percentage=30.0,
            away_abbrev="LAD",
            home_abbrev="SF"
        )

        # Away team winning: arrow extends from left
        assert "◄" in result
        assert "►" not in result
        # Percentage should show away team's win % (70.0%) on left
        assert result.startswith("70.0%"), "Percentage should be on left when away team winning"

    def test_home_team_dominant_95_percent(self):
        """Test progress bar when home team is dominant (95%)."""
        result = create_team_progress_bar(
            win_percentage=95.0,
            away_abbrev="POR",
            home_abbrev="WV"
        )

        # Home team dominant: almost all dark blocks
        assert "►" in result
        assert "95.0%" in result

        dark_blocks = result.count("▓")
        light_blocks = result.count("░")

        # With 95% home win probability, should be 9.5/10 blocks dark (rounds to 9 or 10)
        assert dark_blocks >= 9, "95% should result in 9+ dark blocks"
        assert light_blocks <= 1, "95% should result in 0-1 light blocks"

    def test_away_team_dominant_5_percent_home(self):
        """Test progress bar when away team is dominant (home only 5%)."""
        result = create_team_progress_bar(
            win_percentage=5.0,
            away_abbrev="POR",
            home_abbrev="WV"
        )

        # Away team dominant: almost all dark blocks
        assert "◄" in result
        # Percentage should show away team's win % (95.0%) on left
        assert result.startswith("95.0%"), "Percentage should be on left when away team winning"

        dark_blocks = result.count("▓")
        light_blocks = result.count("░")

        # With 5% home win probability, should be 9.5/10 blocks dark (rounds to 9 or 10)
        assert dark_blocks >= 9, "5% should result in 9+ dark blocks"
        assert light_blocks <= 1, "5% should result in 0-1 light blocks"

    def test_custom_bar_length(self):
        """Test progress bar with custom length."""
        result = create_team_progress_bar(
            win_percentage=75.0,
            away_abbrev="POR",
            home_abbrev="WV",
            length=20
        )

        # Should have more blocks total
        total_blocks = result.count("▓") + result.count("░")
        assert total_blocks == 20, "Should have exactly 20 blocks with custom length"

    def test_edge_case_0_percent(self):
        """Test progress bar at edge case of 0% home win probability."""
        result = create_team_progress_bar(
            win_percentage=0.0,
            away_abbrev="POR",
            home_abbrev="WV"
        )

        # Away team certain to win: arrow from left
        assert "◄" in result
        # Percentage should show away team's win % (100.0%) on left
        assert result.startswith("100.0%"), "Percentage should be on left when away team winning"

        # Should be all dark blocks (away team dominant)
        assert result.count("▓") == 10, "0% home should be all dark blocks"
        assert "░" not in result, "0% home should have no light blocks"

    def test_edge_case_100_percent(self):
        """Test progress bar at edge case of 100% home win probability."""
        result = create_team_progress_bar(
            win_percentage=100.0,
            away_abbrev="POR",
            home_abbrev="WV"
        )

        # Home team certain to win: arrow from right
        assert "►" in result
        # Percentage should be on right when home team winning
        assert result.endswith("100.0%"), "Percentage should be on right when home team winning"

        # Should be all dark blocks (home team dominant)
        assert result.count("▓") == 10, "100% home should be all dark blocks"
        assert "░" not in result, "100% home should have no light blocks"
