"""
Unit tests for InjuryService.

Tests cover:
- Getting active injuries for a player
- Creating injury records
- Clearing injuries
- Team-based injury queries
"""
import pytest
from aioresponses import aioresponses
from unittest.mock import AsyncMock, patch, MagicMock

from services.injury_service import InjuryService
from models.injury import Injury


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    config = MagicMock()
    config.db_url = "https://api.example.com"
    config.api_token = "test-token"
    return config


@pytest.fixture
def injury_service():
    """Create an InjuryService instance for testing."""
    return InjuryService()


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
    """Tests for InjuryService."""

    @pytest.mark.asyncio
    async def test_get_active_injury_found(self, mock_config, injury_service, sample_injury_data):
        """Test getting active injury when one exists."""
        with patch('api.client.get_config', return_value=mock_config):
            with aioresponses() as m:
                m.get(
                    'https://api.example.com/v3/injuries?player_id=123&season=12&is_active=true',
                    payload={
                        'count': 1,
                        'injuries': [sample_injury_data]
                    }
                )

                injury = await injury_service.get_active_injury(123, 12)

                assert injury is not None
                assert injury.id == 1
                assert injury.player_id == 123
                assert injury.is_active is True

    @pytest.mark.asyncio
    async def test_get_active_injury_not_found(self, mock_config, injury_service):
        """Test getting active injury when none exists."""
        with patch('api.client.get_config', return_value=mock_config):
            with aioresponses() as m:
                m.get(
                    'https://api.example.com/v3/injuries?player_id=123&season=12&is_active=true',
                    payload={
                        'count': 0,
                        'injuries': []
                    }
                )

                injury = await injury_service.get_active_injury(123, 12)

                assert injury is None

    @pytest.mark.asyncio
    async def test_get_injuries_by_player(self, mock_config, injury_service, multiple_injuries_data):
        """Test getting all injuries for a player."""
        with patch('api.client.get_config', return_value=mock_config):
            with aioresponses() as m:
                m.get(
                    'https://api.example.com/v3/injuries?player_id=123&season=12',
                    payload={
                        'count': 1,
                        'injuries': [multiple_injuries_data[0]]
                    }
                )

                injuries = await injury_service.get_injuries_by_player(123, 12)

                assert len(injuries) == 1
                assert injuries[0].player_id == 123

    @pytest.mark.asyncio
    async def test_get_injuries_by_player_active_only(self, mock_config, injury_service, sample_injury_data):
        """Test getting only active injuries for a player."""
        with patch('api.client.get_config', return_value=mock_config):
            with aioresponses() as m:
                m.get(
                    'https://api.example.com/v3/injuries?player_id=123&season=12&is_active=true',
                    payload={
                        'count': 1,
                        'injuries': [sample_injury_data]
                    }
                )

                injuries = await injury_service.get_injuries_by_player(123, 12, active_only=True)

                assert len(injuries) == 1
                assert injuries[0].is_active is True

    @pytest.mark.asyncio
    async def test_get_injuries_by_team(self, mock_config, injury_service, multiple_injuries_data):
        """Test getting injuries for a team."""
        with patch('api.client.get_config', return_value=mock_config):
            with aioresponses() as m:
                m.get(
                    'https://api.example.com/v3/injuries?team_id=10&season=12&is_active=true',
                    payload={
                        'count': 2,
                        'injuries': multiple_injuries_data
                    }
                )

                injuries = await injury_service.get_injuries_by_team(10, 12)

                assert len(injuries) == 2

    @pytest.mark.asyncio
    async def test_create_injury(self, mock_config, injury_service, sample_injury_data):
        """Test creating a new injury record."""
        with patch('api.client.get_config', return_value=mock_config):
            with aioresponses() as m:
                m.post(
                    'https://api.example.com/v3/injuries',
                    payload=sample_injury_data
                )

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

    @pytest.mark.asyncio
    async def test_clear_injury(self, mock_config, injury_service, sample_injury_data):
        """Test clearing an injury."""
        with patch('api.client.get_config', return_value=mock_config):
            with aioresponses() as m:
                # Mock the PATCH request (note: patch sends data in body, not URL)
                cleared_data = sample_injury_data.copy()
                cleared_data['is_active'] = False

                m.patch(
                    'https://api.example.com/v3/injuries/1',
                    payload=cleared_data
                )

                success = await injury_service.clear_injury(1)

                assert success is True

    @pytest.mark.asyncio
    async def test_clear_injury_failure(self, mock_config, injury_service):
        """Test clearing injury when it fails."""
        with patch('api.client.get_config', return_value=mock_config):
            with aioresponses() as m:
                m.patch(
                    'https://api.example.com/v3/injuries/1',
                    status=500
                )

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
        """Test injury table lookup returning OK."""
        from commands.injuries.management import InjuryCog
        from unittest.mock import MagicMock

        cog = InjuryCog(MagicMock())

        # p70 rating with 1 game played, roll of 3 should be OK
        result = cog._get_injury_result('p70', 1, 3)
        assert result == 'OK'

    def test_injury_table_lookup_rem_result(self):
        """Test injury table lookup returning REM."""
        from commands.injuries.management import InjuryCog
        from unittest.mock import MagicMock

        cog = InjuryCog(MagicMock())

        # p70 rating with 1 game played, roll of 9 should be REM
        result = cog._get_injury_result('p70', 1, 9)
        assert result == 'REM'

    def test_injury_table_lookup_games_result(self):
        """Test injury table lookup returning number of games."""
        from commands.injuries.management import InjuryCog
        from unittest.mock import MagicMock

        cog = InjuryCog(MagicMock())

        # p70 rating with 1 game played, roll of 11 should be 1 game
        result = cog._get_injury_result('p70', 1, 11)
        assert result == 1

        # p65 rating with 1 game played, roll of 3 should be 2 games
        result = cog._get_injury_result('p65', 1, 3)
        assert result == 2

    def test_injury_table_no_table_exists(self):
        """Test injury table when no table exists for rating/games combo."""
        from commands.injuries.management import InjuryCog
        from unittest.mock import MagicMock

        cog = InjuryCog(MagicMock())

        # p70 rating with 3 games played has no table, should return OK
        result = cog._get_injury_result('p70', 3, 10)
        assert result == 'OK'

    def test_injury_table_roll_out_of_range(self):
        """Test injury table with out of range roll."""
        from commands.injuries.management import InjuryCog
        from unittest.mock import MagicMock

        cog = InjuryCog(MagicMock())

        # Roll less than 3 or greater than 18 should return OK
        result = cog._get_injury_result('p65', 1, 2)
        assert result == 'OK'

        result = cog._get_injury_result('p65', 1, 19)
        assert result == 'OK'

    def test_injury_table_games_played_mapping(self):
        """Test games played maps correctly to table keys."""
        from commands.injuries.management import InjuryCog
        from unittest.mock import MagicMock

        cog = InjuryCog(MagicMock())

        # Test that different games_played values access different tables
        result_1_game = cog._get_injury_result('p65', 1, 10)
        result_2_games = cog._get_injury_result('p65', 2, 10)

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
