"""
Tests for TeamService functionality
"""
import pytest
from unittest.mock import AsyncMock

from services.team_service import TeamService, team_service
from models.team import Team
from constants import SBA_CURRENT_SEASON
from exceptions import APIException


class TestTeamService:
    """Test TeamService functionality."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock API client."""
        client = AsyncMock()
        return client
    
    @pytest.fixture
    def team_service_instance(self, mock_client):
        """Create TeamService instance with mocked client."""
        service = TeamService()
        service._client = mock_client
        return service
    
    def create_team_data(self, team_id: int, abbrev: str, season: int = 12, **kwargs):
        """Create complete team data for testing."""
        base_data = {
            'id': team_id,
            'abbrev': abbrev,
            'sname': f'{abbrev} Team',
            'lname': f'{abbrev} Long Team Name',
            'season': season,
            'gmid': 101,
            'division_id': 1,
        }
        base_data.update(kwargs)
        return base_data
    
    @pytest.mark.asyncio
    async def test_get_team_success(self, team_service_instance, mock_client):
        """Test successful team retrieval."""
        mock_data = self.create_team_data(1, 'TST', stadium='Test Stadium')
        mock_client.get.return_value = mock_data
        
        result = await team_service_instance.get_team(1)
        
        assert isinstance(result, Team)
        assert result.abbrev == 'TST'
        assert result.sname == 'TST Team'
        assert result.season == 12
        mock_client.get.assert_called_once_with('teams', object_id=1)
    
    @pytest.mark.asyncio
    async def test_get_team_by_abbrev_success(self, team_service_instance, mock_client):
        """Test getting team by abbreviation."""
        mock_data = {
            'count': 1,
            'teams': [self.create_team_data(1, 'NYY', season=12)]
        }
        mock_client.get.return_value = mock_data
        
        result = await team_service_instance.get_team_by_abbrev('nyy', season=12)
        
        assert isinstance(result, Team)
        assert result.abbrev == 'NYY'
        mock_client.get.assert_called_once_with('teams', params=[('team_abbrev', 'NYY'), ('season', '12')])
    
    @pytest.mark.asyncio
    async def test_get_team_by_abbrev_not_found(self, team_service_instance, mock_client):
        """Test getting team by abbreviation when not found."""
        mock_data = {'count': 0, 'teams': []}
        mock_client.get.return_value = mock_data
        
        result = await team_service_instance.get_team_by_abbrev('XXX', season=12)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_teams_by_season(self, team_service_instance, mock_client):
        """Test getting all teams for a season."""
        mock_data = {
            'count': 3,
            'teams': [
                self.create_team_data(1, 'TEA', season=12),
                self.create_team_data(2, 'TEB', season=12),
                self.create_team_data(3, 'TEC', season=12)
            ]
        }
        mock_client.get.return_value = mock_data
        
        result = await team_service_instance.get_teams_by_season(12)
        
        assert len(result) == 3
        assert all(isinstance(team, Team) for team in result)
        assert all(team.season == 12 for team in result)
        mock_client.get.assert_called_once_with('teams', params=[('season', '12')])
    
    @pytest.mark.asyncio
    async def test_get_teams_by_manager(self, team_service_instance, mock_client):
        """Test getting teams by manager."""
        mock_data = {
            'count': 2,
            'teams': [
                self.create_team_data(1, 'TEA', manager1_id=101, season=12),
                self.create_team_data(2, 'TEB', manager2_id=101, season=12)
            ]
        }
        mock_client.get.return_value = mock_data
        
        result = await team_service_instance.get_teams_by_manager(101, season=12)
        
        assert len(result) == 2
        assert all(isinstance(team, Team) for team in result)
        mock_client.get.assert_called_once_with('teams', params=[('manager_id', '101'), ('season', '12')])
    
    @pytest.mark.asyncio
    async def test_get_teams_by_division(self, team_service_instance, mock_client):
        """Test getting teams by division."""
        mock_data = {
            'count': 4,
            'teams': [
                self.create_team_data(1, 'TEA', division_id=1, season=12),
                self.create_team_data(2, 'TEB', division_id=1, season=12),
                self.create_team_data(3, 'TEC', division_id=1, season=12),
                self.create_team_data(4, 'TED', division_id=1, season=12)
            ]
        }
        mock_client.get.return_value = mock_data
        
        result = await team_service_instance.get_teams_by_division(1, season=12)
        
        assert len(result) == 4
        assert all(isinstance(team, Team) for team in result)
        mock_client.get.assert_called_once_with('teams', params=[('division_id', '1'), ('season', '12')])
    
    @pytest.mark.asyncio
    async def test_get_team_roster(self, team_service_instance, mock_client):
        """Test getting team roster with position counts."""
        mock_roster_data = {
            'active': {
                'C': 2, '1B': 1, '2B': 1, '3B': 1, 'SS': 1, 'LF': 1, 'CF': 1, 'RF': 1, 'DH': 1,
                'SP': 5, 'RP': 8, 'CP': 2, 'WARa': 45.2,
                'players': [
                    {'id': 1, 'name': 'Player 1', 'wara': 5.2},
                    {'id': 2, 'name': 'Player 2', 'wara': 4.8}
                ]
            },
            'shortil': {
                'C': 0, '1B': 0, '2B': 0, '3B': 0, 'SS': 0, 'LF': 0, 'CF': 0, 'RF': 0, 'DH': 0,
                'SP': 2, 'RP': 3, 'CP': 0, 'WARa': 8.5,
                'players': [
                    {'id': 3, 'name': 'Minor Player 1', 'wara': 2.1}
                ]
            },
            'longil': {
                'C': 0, '1B': 0, '2B': 0, '3B': 0, 'SS': 0, 'LF': 0, 'CF': 0, 'RF': 0, 'DH': 0,
                'SP': 0, 'RP': 1, 'CP': 0, 'WARa': 1.2,
                'players': [
                    {'id': 4, 'name': 'Injured Player', 'wara': 1.2}
                ]
            }
        }
        mock_client.get.return_value = mock_roster_data
        
        result = await team_service_instance.get_team_roster(1, 'current')
        
        assert result is not None
        assert 'active' in result
        assert 'shortil' in result
        assert 'longil' in result
        assert result['active']['C'] == 2
        assert result['active']['SP'] == 5
        assert len(result['active']['players']) == 2
        mock_client.get.assert_called_once_with('teams/1/roster/current')
    
    @pytest.mark.asyncio
    async def test_get_team_roster_next_week(self, team_service_instance, mock_client):
        """Test getting next week's roster."""
        mock_roster_data = {
            'active': {'C': 1, 'SP': 5, 'players': []},
            'shortil': {'C': 0, 'SP': 0, 'players': []},
            'longil': {'C': 0, 'SP': 0, 'players': []}
        }
        mock_client.get.return_value = mock_roster_data
        
        result = await team_service_instance.get_team_roster(1, 'next')
        
        assert result is not None
        mock_client.get.assert_called_once_with('teams/1/roster/next')
    
    @pytest.mark.asyncio
    async def test_get_team_standings_position(self, team_service_instance, mock_client):
        """Test getting team standings information."""
        mock_standings_data = {
            'id': 1,
            'team_id': 1,
            'wins': 45,
            'losses': 27,
            'run_diff': 125,
            'div_gb': None,
            'wc_gb': None,
            'home_wins': 25,
            'home_losses': 11,
            'away_wins': 20,
            'away_losses': 16
        }
        mock_client.get.return_value = mock_standings_data
        
        result = await team_service_instance.get_team_standings_position(1, season=12)
        
        assert result is not None
        assert result['wins'] == 45
        assert result['losses'] == 27
        assert result['run_diff'] == 125
        mock_client.get.assert_called_once_with('standings/team/1', params=[('season', '12')])
    
    @pytest.mark.asyncio
    async def test_update_team(self, team_service_instance, mock_client):
        """Test team update functionality."""
        update_data = {'stadium': 'New Stadium', 'color': '#FF0000'}
        response_data = self.create_team_data(1, 'TST', stadium='New Stadium', color='#FF0000')
        mock_client.put.return_value = response_data
        
        result = await team_service_instance.update_team(1, update_data)
        
        assert isinstance(result, Team)
        assert result.stadium == 'New Stadium'
        assert result.color == '#FF0000'
        mock_client.put.assert_called_once_with('teams', update_data, object_id=1)
    
    @pytest.mark.asyncio
    async def test_is_valid_team_abbrev(self, team_service_instance, mock_client):
        """Test team abbreviation validation."""
        # Mock successful lookup
        mock_data = {
            'count': 1,
            'teams': [self.create_team_data(1, 'TST', season=12)]
        }
        mock_client.get.return_value = mock_data
        
        result = await team_service_instance.is_valid_team_abbrev('TST', season=12)
        
        assert result is True
        
        # Mock failed lookup
        mock_client.get.return_value = {'count': 0, 'teams': []}
        
        result = await team_service_instance.is_valid_team_abbrev('XXX', season=12)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_current_season_teams(self, team_service_instance, mock_client):
        """Test getting current season teams."""
        mock_data = {
            'count': 2,
            'teams': [
                self.create_team_data(1, 'TEA', season=SBA_CURRENT_SEASON),
                self.create_team_data(2, 'TEB', season=SBA_CURRENT_SEASON)
            ]
        }
        mock_client.get.return_value = mock_data
        
        result = await team_service_instance.get_current_season_teams()
        
        assert len(result) == 2
        assert all(team.season == SBA_CURRENT_SEASON for team in result)
        mock_client.get.assert_called_once_with('teams', params=[('season', str(SBA_CURRENT_SEASON))])
    
    @pytest.mark.asyncio
    async def test_error_handling(self, team_service_instance, mock_client):
        """Test error handling in team service methods."""
        mock_client.get.side_effect = APIException("API Error")
        
        # Should return None/empty list on errors, not raise
        result = await team_service_instance.get_team(1)
        assert result is None
        
        result = await team_service_instance.get_teams_by_season(12)
        assert result == []
        
        result = await team_service_instance.get_teams_by_manager(101)
        assert result == []
        
        result = await team_service_instance.get_team_roster(1)
        assert result is None
        
        result = await team_service_instance.get_team_standings_position(1, 12)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_abbrev_case_insensitive(self, team_service_instance, mock_client):
        """Test that abbreviation lookup is case insensitive."""
        mock_data = {
            'count': 1,
            'teams': [self.create_team_data(1, 'NYY', season=12)]
        }
        mock_client.get.return_value = mock_data
        
        # Test with lowercase input
        result = await team_service_instance.get_team_by_abbrev('nyy', season=12)
        
        assert result is not None
        assert result.abbrev == 'NYY'
        # Should call with uppercase
        mock_client.get.assert_called_once_with('teams', params=[('team_abbrev', 'NYY'), ('season', '12')])


class TestGlobalTeamServiceInstance:
    """Test global team service instance."""
    
    def test_team_service_global(self):
        """Test global team service instance."""
        assert isinstance(team_service, TeamService)
        assert team_service.model_class == Team
        assert team_service.endpoint == 'teams'
    
    @pytest.mark.asyncio
    async def test_service_independence(self):
        """Test that service instances are independent."""
        service1 = TeamService()
        service2 = TeamService()
        
        # Should be different instances
        assert service1 is not service2
        # But same configuration
        assert service1.model_class == service2.model_class
        assert service1.endpoint == service2.endpoint