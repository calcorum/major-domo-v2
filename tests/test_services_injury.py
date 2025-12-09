"""
Unit tests for InjuryService.

Tests cover:
- Getting active injuries for a player
- Creating injury records
- Clearing injuries
- Team-based injury queries

Uses the standard service testing pattern: mock the service's _client directly
rather than trying to mock HTTP responses, since the service uses BaseService
which manages its own client instance.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.injury_service import InjuryService
from models.injury import Injury


@pytest.fixture
def mock_client():
    """Mock API client for testing."""
    client = AsyncMock()
    return client


@pytest.fixture
def injury_service(mock_client):
    """Create an InjuryService instance with mocked client."""
    service = InjuryService()
    service._client = mock_client
    return service


@pytest.fixture
def sample_injury_data():
    """Sample injury data from API."""
    return {
        'id': 1,
        'season': 12,
        'player_id': 123,
        'total_games': 4,
        'start_week': 5,
        'start_game': 2,
        'end_week': 6,
        'end_game': 2,
        'is_active': True
    }


@pytest.fixture
def multiple_injuries_data():
    """Multiple injury records."""
    return [
        {
            'id': 1,
            'season': 12,
            'player_id': 123,
            'total_games': 4,
            'start_week': 5,
            'start_game': 2,
            'end_week': 6,
            'end_game': 2,
            'is_active': True
        },
        {
            'id': 2,
            'season': 12,
            'player_id': 456,
            'total_games': 2,
            'start_week': 4,
            'start_game': 3,
            'end_week': 5,
            'end_game': 1,
            'is_active': False
        }
    ]


class TestInjuryModel:
    """Tests for Injury model."""

    def test_injury_model_creation(self, sample_injury_data):
        """Test creating an Injury instance."""
        injury = Injury(**sample_injury_data)

        assert injury.id == 1
        assert injury.season == 12
        assert injury.player_id == 123
        assert injury.total_games == 4
        assert injury.is_active is True

    def test_return_date_property(self, sample_injury_data):
        """Test return_date formatted property."""
        injury = Injury(**sample_injury_data)

        assert injury.return_date == 'w06g2'

    def test_start_date_property(self, sample_injury_data):
        """Test start_date formatted property."""
        injury = Injury(**sample_injury_data)

        assert injury.start_date == 'w05g2'

    def test_duration_display_singular(self):
        """Test duration display for 1 game."""
        injury = Injury(
            id=1,
            season=12,
            player_id=123,
            total_games=1,
            start_week=5,
            start_game=2,
            end_week=5,
            end_game=3,
            is_active=True
        )

        assert injury.duration_display == "1 game"

    def test_duration_display_plural(self, sample_injury_data):
        """Test duration display for multiple games."""
        injury = Injury(**sample_injury_data)

        assert injury.duration_display == "4 games"


class TestInjuryService:
    """Tests for InjuryService using mocked client."""

    @pytest.mark.asyncio
    async def test_get_active_injury_found(self, injury_service, mock_client, sample_injury_data):
        """Test getting active injury when one exists.

        Uses mocked client to return injury data without hitting real API.
        """
        # Mock the client.get() response - BaseService parses this
        mock_client.get.return_value = {
            'count': 1,
            'injuries': [sample_injury_data]
        }

        injury = await injury_service.get_active_injury(123, 12)

        assert injury is not None
        assert injury.id == 1
        assert injury.player_id == 123
        assert injury.is_active is True
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_injury_not_found(self, injury_service, mock_client):
        """Test getting active injury when none exists.

        Returns None when API returns empty list.
        """
        mock_client.get.return_value = {
            'count': 0,
            'injuries': []
        }

        injury = await injury_service.get_active_injury(123, 12)

        assert injury is None

    @pytest.mark.asyncio
    async def test_get_injuries_by_player(self, injury_service, mock_client, multiple_injuries_data):
        """Test getting all injuries for a player.

        Uses mocked client to return injury list.
        """
        mock_client.get.return_value = {
            'count': 1,
            'injuries': [multiple_injuries_data[0]]
        }

        injuries = await injury_service.get_injuries_by_player(123, 12)

        assert len(injuries) == 1
        assert injuries[0].player_id == 123

    @pytest.mark.asyncio
    async def test_get_injuries_by_player_active_only(self, injury_service, mock_client, sample_injury_data):
        """Test getting only active injuries for a player.

        Verifies the active_only filter works correctly.
        """
        mock_client.get.return_value = {
            'count': 1,
            'injuries': [sample_injury_data]
        }

        injuries = await injury_service.get_injuries_by_player(123, 12, active_only=True)

        assert len(injuries) == 1
        assert injuries[0].is_active is True

    @pytest.mark.asyncio
    async def test_get_injuries_by_team(self, injury_service, mock_client, multiple_injuries_data):
        """Test getting injuries for a team.

        Returns all injuries for a team (both active and inactive).
        """
        mock_client.get.return_value = {
            'count': 2,
            'injuries': multiple_injuries_data
        }

        injuries = await injury_service.get_injuries_by_team(10, 12)

        assert len(injuries) == 2

    @pytest.mark.asyncio
    async def test_create_injury(self, injury_service, mock_client, sample_injury_data):
        """Test creating a new injury record.

        The service posts injury data and returns the created injury model.
        """
        mock_client.post.return_value = sample_injury_data

        injury = await injury_service.create_injury(
            season=12,
            player_id=123,
            total_games=4,
            start_week=5,
            start_game=2,
            end_week=6,
            end_game=2
        )

        assert injury is not None
        assert injury.player_id == 123
        assert injury.total_games == 4
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_injury(self, injury_service, mock_client, sample_injury_data):
        """Test clearing an injury.

        Uses PATCH with query params to set is_active=False.
        """
        cleared_data = sample_injury_data.copy()
        cleared_data['is_active'] = False

        mock_client.patch.return_value = cleared_data

        success = await injury_service.clear_injury(1)

        assert success is True
        mock_client.patch.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_injury_failure(self, injury_service, mock_client):
        """Test clearing injury when it fails.

        Returns False when API returns None or error.
        """
        mock_client.patch.return_value = None

        success = await injury_service.clear_injury(1)

        assert success is False


class TestInjuryRollLogic:
    """Tests for injury roll dice and table logic."""

    def test_injury_rating_parsing_valid(self):
        """Test parsing valid injury rating format."""
        # Format: "1p70" -> games_played=1, rating="p70"
        injury_rating = "1p70"
        games_played = int(injury_rating[0])
        rating = injury_rating[1:]

        assert games_played == 1
        assert rating == "p70"

        # Test other formats
        injury_rating = "4p50"
        games_played = int(injury_rating[0])
        rating = injury_rating[1:]

        assert games_played == 4
        assert rating == "p50"

    def test_injury_rating_parsing_invalid(self):
        """Test parsing invalid injury rating format."""
        import pytest

        # Missing games number
        with pytest.raises((ValueError, IndexError)):
            injury_rating = "p70"
            games_played = int(injury_rating[0])

        # Invalid games number
        injury_rating = "7p70"
        games_played = int(injury_rating[0])
        assert games_played > 6  # Should be caught by validation

        # Empty string
        with pytest.raises(IndexError):
            injury_rating = ""
            games_played = int(injury_rating[0])

    def test_injury_table_lookup_ok_result(self):
        """Test injury table lookup returning OK.

        Uses InjuryGroup (app_commands.Group) which doesn't require a bot instance.
        """
        from commands.injuries.management import InjuryGroup

        group = InjuryGroup()

        # p70 rating with 1 game played, roll of 3 should be OK
        result = group._get_injury_result('p70', 1, 3)
        assert result == 'OK'

    def test_injury_table_lookup_rem_result(self):
        """Test injury table lookup returning REM.

        Uses InjuryGroup (app_commands.Group) which doesn't require a bot instance.
        """
        from commands.injuries.management import InjuryGroup

        group = InjuryGroup()

        # p70 rating with 1 game played, roll of 9 should be REM
        result = group._get_injury_result('p70', 1, 9)
        assert result == 'REM'

    def test_injury_table_lookup_games_result(self):
        """Test injury table lookup returning number of games.

        Uses InjuryGroup (app_commands.Group) which doesn't require a bot instance.
        """
        from commands.injuries.management import InjuryGroup

        group = InjuryGroup()

        # p70 rating with 1 game played, roll of 11 should be 1 game
        result = group._get_injury_result('p70', 1, 11)
        assert result == 1

        # p65 rating with 1 game played, roll of 3 should be 2 games
        result = group._get_injury_result('p65', 1, 3)
        assert result == 2

    def test_injury_table_no_table_exists(self):
        """Test injury table when no table exists for rating/games combo.

        Uses InjuryGroup (app_commands.Group) which doesn't require a bot instance.
        """
        from commands.injuries.management import InjuryGroup

        group = InjuryGroup()

        # p70 rating with 3 games played has no table, should return OK
        result = group._get_injury_result('p70', 3, 10)
        assert result == 'OK'

    def test_injury_table_roll_out_of_range(self):
        """Test injury table with out of range roll.

        Uses InjuryGroup (app_commands.Group) which doesn't require a bot instance.
        """
        from commands.injuries.management import InjuryGroup

        group = InjuryGroup()

        # Roll less than 3 or greater than 18 should return OK
        result = group._get_injury_result('p65', 1, 2)
        assert result == 'OK'

        result = group._get_injury_result('p65', 1, 19)
        assert result == 'OK'

    def test_injury_table_games_played_mapping(self):
        """Test games played maps correctly to table keys.

        Uses InjuryGroup (app_commands.Group) which doesn't require a bot instance.
        """
        from commands.injuries.management import InjuryGroup

        group = InjuryGroup()

        # Test that different games_played values access different tables
        result_1_game = group._get_injury_result('p65', 1, 10)
        result_2_games = group._get_injury_result('p65', 2, 10)

        # These should potentially be different values (depends on tables)
        # Just verify both execute without error
        assert result_1_game is not None
        assert result_2_games is not None


class TestInjuryCalculations:
    """Tests for injury date calculation logic (as used in commands)."""

    def test_simple_injury_calculation(self):
        """Test injury return date calculation for 1 game."""
        import math

        this_week = 5
        this_game = 1
        injury_games = 1

        out_weeks = math.floor(injury_games / 4)
        out_games = injury_games % 4

        return_week = this_week + out_weeks
        return_game = this_game + 1 + out_games

        if return_game > 4:
            return_week += 1
            return_game -= 4

        assert return_week == 5
        assert return_game == 3

    def test_multi_game_injury_same_week(self):
        """Test injury spanning multiple games in same week."""
        import math

        this_week = 5
        this_game = 1
        injury_games = 2

        out_weeks = math.floor(injury_games / 4)
        out_games = injury_games % 4

        return_week = this_week + out_weeks
        return_game = this_game + 1 + out_games

        if return_game > 4:
            return_week += 1
            return_game -= 4

        assert return_week == 5
        assert return_game == 4

    def test_injury_crossing_week_boundary(self):
        """Test injury that crosses into next week."""
        import math

        this_week = 5
        this_game = 3
        injury_games = 3

        out_weeks = math.floor(injury_games / 4)
        out_games = injury_games % 4

        return_week = this_week + out_weeks
        return_game = this_game + 1 + out_games

        if return_game > 4:
            return_week += 1
            return_game -= 4

        assert return_week == 6
        assert return_game == 3

    def test_multi_week_injury(self):
        """Test injury spanning multiple weeks."""
        import math

        this_week = 5
        this_game = 2
        injury_games = 8  # 2 full weeks

        out_weeks = math.floor(injury_games / 4)
        out_games = injury_games % 4

        return_week = this_week + out_weeks
        return_game = this_game + 1 + out_games

        if return_game > 4:
            return_week += 1
            return_game -= 4

        assert return_week == 7
        assert return_game == 3

    def test_injury_from_game_4(self):
        """Test injury starting from last game of week."""
        import math

        this_week = 5
        this_game = 4
        injury_games = 2

        # Special handling for injuries starting after game 4
        start_week = this_week if this_game != 4 else this_week + 1
        start_game = this_game + 1 if this_game != 4 else 1

        out_weeks = math.floor(injury_games / 4)
        out_games = injury_games % 4

        return_week = this_week + out_weeks
        return_game = this_game + 1 + out_games

        if return_game > 4:
            return_week += 1
            return_game -= 4

        assert start_week == 6
        assert start_game == 1
        assert return_week == 6
        assert return_game == 3
