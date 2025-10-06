"""
Tests for shared autocomplete utility functions.

Validates the shared autocomplete functions used across multiple command modules.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from utils.autocomplete import player_autocomplete, team_autocomplete, major_league_team_autocomplete
from tests.factories import PlayerFactory, TeamFactory
from models.team import RosterType


class TestPlayerAutocomplete:
    """Test player autocomplete functionality."""

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock()
        interaction.user.id = 12345
        return interaction

    @pytest.mark.asyncio
    async def test_player_autocomplete_success(self, mock_interaction):
        """Test successful player autocomplete."""
        mock_players = [
            PlayerFactory.mike_trout(id=1),
            PlayerFactory.ronald_acuna(id=2)
        ]

        with patch('utils.autocomplete.player_service') as mock_service:
            mock_service.search_players = AsyncMock(return_value=mock_players)

            choices = await player_autocomplete(mock_interaction, 'Trout')

            assert len(choices) == 2
            assert choices[0].name == 'Mike Trout (CF)'
            assert choices[0].value == 'Mike Trout'
            assert choices[1].name == 'Ronald Acuna Jr. (OF)'
            assert choices[1].value == 'Ronald Acuna Jr.'

    @pytest.mark.asyncio
    async def test_player_autocomplete_with_team_info(self, mock_interaction):
        """Test player autocomplete with team information."""
        mock_team = TeamFactory.create(id=499, abbrev='LAA', sname='Angels', lname='Los Angeles Angels')
        mock_player = PlayerFactory.mike_trout(id=1)
        mock_player.team = mock_team

        with patch('utils.autocomplete.player_service') as mock_service:
            mock_service.search_players = AsyncMock(return_value=[mock_player])

            choices = await player_autocomplete(mock_interaction, 'Trout')

            assert len(choices) == 1
            assert choices[0].name == 'Mike Trout (CF - LAA)'
            assert choices[0].value == 'Mike Trout'

    @pytest.mark.asyncio
    async def test_player_autocomplete_prioritizes_user_team(self, mock_interaction):
        """Test that user's team players are prioritized in autocomplete."""
        user_team = TeamFactory.create(id=1, abbrev='POR', sname='Loggers')
        other_team = TeamFactory.create(id=2, abbrev='LAA', sname='Angels')

        # Create players - one from user's team, one from other team
        user_player = PlayerFactory.mike_trout(id=1)
        user_player.team = user_team
        user_player.team_id = user_team.id

        other_player = PlayerFactory.ronald_acuna(id=2)
        other_player.team = other_team
        other_player.team_id = other_team.id

        with patch('utils.autocomplete.player_service') as mock_service, \
             patch('utils.autocomplete.get_user_major_league_team') as mock_get_team:

            mock_service.search_players = AsyncMock(return_value=[other_player, user_player])
            mock_get_team.return_value = user_team

            choices = await player_autocomplete(mock_interaction, 'player')

            assert len(choices) == 2
            # User's team player should be first
            assert choices[0].name == 'Mike Trout (CF - POR)'
            assert choices[1].name == 'Ronald Acuna Jr. (OF - LAA)'

    @pytest.mark.asyncio
    async def test_player_autocomplete_short_input(self, mock_interaction):
        """Test player autocomplete with short input returns empty."""
        choices = await player_autocomplete(mock_interaction, 'T')
        assert len(choices) == 0

    @pytest.mark.asyncio
    async def test_player_autocomplete_error_handling(self, mock_interaction):
        """Test player autocomplete error handling."""
        with patch('utils.autocomplete.player_service') as mock_service:
            mock_service.search_players.side_effect = Exception("API Error")

            choices = await player_autocomplete(mock_interaction, 'Trout')
            assert len(choices) == 0


class TestTeamAutocomplete:
    """Test team autocomplete functionality."""

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock()
        interaction.user.id = 12345
        return interaction

    @pytest.mark.asyncio
    async def test_team_autocomplete_success(self, mock_interaction):
        """Test successful team autocomplete."""
        mock_teams = [
            TeamFactory.create(id=1, abbrev='LAA', sname='Angels'),
            TeamFactory.create(id=2, abbrev='LAAMIL', sname='Salt Lake Bees'),
            TeamFactory.create(id=3, abbrev='LAAAIL', sname='Angels IL'),
            TeamFactory.create(id=4, abbrev='POR', sname='Loggers')
        ]

        with patch('utils.autocomplete.team_service') as mock_service:
            mock_service.get_teams_by_season = AsyncMock(return_value=mock_teams)

            choices = await team_autocomplete(mock_interaction, 'la')

            assert len(choices) == 3  # All teams with 'la' in abbrev or sname
            assert any('LAA' in choice.name for choice in choices)
            assert any('LAAMIL' in choice.name for choice in choices)
            assert any('LAAAIL' in choice.name for choice in choices)

    @pytest.mark.asyncio
    async def test_team_autocomplete_short_input(self, mock_interaction):
        """Test team autocomplete with very short input."""
        choices = await team_autocomplete(mock_interaction, '')
        assert len(choices) == 0

    @pytest.mark.asyncio
    async def test_team_autocomplete_error_handling(self, mock_interaction):
        """Test team autocomplete error handling."""
        with patch('utils.autocomplete.team_service') as mock_service:
            mock_service.get_teams_by_season.side_effect = Exception("API Error")

            choices = await team_autocomplete(mock_interaction, 'LAA')
            assert len(choices) == 0


class TestMajorLeagueTeamAutocomplete:
    """Test major league team autocomplete functionality."""

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock()
        interaction.user.id = 12345
        return interaction

    @pytest.mark.asyncio
    async def test_major_league_team_autocomplete_filters_correctly(self, mock_interaction):
        """Test that only major league teams are returned."""
        # Create teams with different roster types
        mock_teams = [
            TeamFactory.create(id=1, abbrev='LAA', sname='Angels'),  # ML
            TeamFactory.create(id=2, abbrev='LAAMIL', sname='Salt Lake Bees'),  # MiL
            TeamFactory.create(id=3, abbrev='LAAAIL', sname='Angels IL'),  # IL
            TeamFactory.create(id=4, abbrev='FA', sname='Free Agents'),  # FA
            TeamFactory.create(id=5, abbrev='POR', sname='Loggers'),  # ML
            TeamFactory.create(id=6, abbrev='PORMIL', sname='Portland MiL'),  # MiL
        ]

        with patch('utils.autocomplete.team_service') as mock_service:
            mock_service.get_teams_by_season = AsyncMock(return_value=mock_teams)

            choices = await major_league_team_autocomplete(mock_interaction, 'l')

            # Should only return major league teams that match 'l' (LAA, POR)
            choice_values = [choice.value for choice in choices]
            assert 'LAA' in choice_values
            assert 'POR' in choice_values
            assert len(choice_values) == 2
            # Should NOT include MiL, IL, or FA teams
            assert 'LAAMIL' not in choice_values
            assert 'LAAAIL' not in choice_values
            assert 'FA' not in choice_values
            assert 'PORMIL' not in choice_values

    @pytest.mark.asyncio
    async def test_major_league_team_autocomplete_matching(self, mock_interaction):
        """Test search matching on abbreviation and short name."""
        mock_teams = [
            TeamFactory.create(id=1, abbrev='LAA', sname='Angels'),
            TeamFactory.create(id=2, abbrev='LAD', sname='Dodgers'),
            TeamFactory.create(id=3, abbrev='POR', sname='Loggers'),
            TeamFactory.create(id=4, abbrev='BOS', sname='Red Sox'),
        ]

        with patch('utils.autocomplete.team_service') as mock_service:
            mock_service.get_teams_by_season = AsyncMock(return_value=mock_teams)

            # Test abbreviation matching
            choices = await major_league_team_autocomplete(mock_interaction, 'la')
            assert len(choices) == 2  # LAA and LAD
            choice_values = [choice.value for choice in choices]
            assert 'LAA' in choice_values
            assert 'LAD' in choice_values

            # Test short name matching
            choices = await major_league_team_autocomplete(mock_interaction, 'red')
            assert len(choices) == 1
            assert choices[0].value == 'BOS'

    @pytest.mark.asyncio
    async def test_major_league_team_autocomplete_short_input(self, mock_interaction):
        """Test major league team autocomplete with very short input."""
        choices = await major_league_team_autocomplete(mock_interaction, '')
        assert len(choices) == 0

    @pytest.mark.asyncio
    async def test_major_league_team_autocomplete_error_handling(self, mock_interaction):
        """Test major league team autocomplete error handling."""
        with patch('utils.autocomplete.team_service') as mock_service:
            mock_service.get_teams_by_season.side_effect = Exception("API Error")

            choices = await major_league_team_autocomplete(mock_interaction, 'LAA')
            assert len(choices) == 0

    @pytest.mark.asyncio
    async def test_major_league_team_autocomplete_roster_type_detection(self, mock_interaction):
        """Test that roster type detection works correctly for edge cases."""
        # Test edge cases like teams whose abbreviation ends in 'M' + 'IL'
        mock_teams = [
            TeamFactory.create(id=1, abbrev='BHM', sname='Iron'),  # ML team ending in 'M'
            TeamFactory.create(id=2, abbrev='BHMIL', sname='Iron IL'),  # IL team (BHM + IL)
            TeamFactory.create(id=3, abbrev='NYYMIL', sname='Staten Island RailRiders'),  # MiL team (NYY + MIL)
            TeamFactory.create(id=4, abbrev='NYY', sname='Yankees'),  # ML team
        ]

        with patch('utils.autocomplete.team_service') as mock_service:
            mock_service.get_teams_by_season = AsyncMock(return_value=mock_teams)

            choices = await major_league_team_autocomplete(mock_interaction, 'b')

            # Should only return major league teams
            choice_values = [choice.value for choice in choices]
            assert 'BHM' in choice_values  # Major league team
            assert 'BHMIL' not in choice_values  # Should be detected as IL, not MiL
            assert 'NYYMIL' not in choice_values  # Minor league team

            # Verify the roster type detection is working
            bhm_team = next(t for t in mock_teams if t.abbrev == 'BHM')
            bhmil_team = next(t for t in mock_teams if t.abbrev == 'BHMIL')
            nyymil_team = next(t for t in mock_teams if t.abbrev == 'NYYMIL')

            assert bhm_team.roster_type() == RosterType.MAJOR_LEAGUE
            assert bhmil_team.roster_type() == RosterType.INJURED_LIST
            assert nyymil_team.roster_type() == RosterType.MINOR_LEAGUE