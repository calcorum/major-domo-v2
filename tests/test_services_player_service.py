"""
Tests for PlayerService functionality
"""
import pytest
from unittest.mock import AsyncMock

from services.player_service import PlayerService, player_service
from models.player import Player
from constants import FREE_AGENT_TEAM_ID
from exceptions import APIException


class TestPlayerService:
    """Test PlayerService functionality."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock API client."""
        client = AsyncMock()
        return client
    
    @pytest.fixture
    def player_service_instance(self, mock_client):
        """Create PlayerService instance with mocked client."""
        service = PlayerService()
        service._client = mock_client
        return service
    
    def create_player_data(self, player_id: int, name: str, team_id: int = 5, position: str = 'C', **kwargs):
        """Create complete player data for testing."""
        base_data = {
            'id': player_id,
            'name': name,
            'wara': 2.5,
            'season': 12,
            'team_id': team_id,
            'image': f'https://example.com/player{player_id}.jpg',
            'pos_1': position,
        }
        base_data.update(kwargs)
        return base_data
    
    @pytest.mark.asyncio
    async def test_get_player_success(self, player_service_instance, mock_client):
        """Test successful player retrieval."""
        mock_data = self.create_player_data(1, 'Test Player', pos_2='1B')
        mock_client.get.return_value = mock_data
        
        result = await player_service_instance.get_player(1)
        
        assert isinstance(result, Player)
        assert result.name == 'Test Player'
        assert result.wara == 2.5
        assert result.season == 12
        assert result.primary_position == 'C'
        mock_client.get.assert_called_once_with('players', object_id=1)
    
    @pytest.mark.asyncio
    async def test_get_player_includes_team_data(self, player_service_instance, mock_client):
        """Test that get_player returns data with team information (from API)."""
        # API returns player data with team information already included
        player_data = self.create_player_data(1, 'Test Player', team_id=5)
        player_data['team'] = {
            'id': 5,
            'abbrev': 'TST', 
            'sname': 'Test Team',
            'lname': 'Test Team Long Name',
            'season': 12
        }
        
        mock_client.get.return_value = player_data
        
        result = await player_service_instance.get_player(1)
        
        assert isinstance(result, Player)
        assert result.name == 'Test Player'
        assert result.team is not None
        assert result.team.sname == 'Test Team'
        
        # Should call get once for player (team data included in API response)
        mock_client.get.assert_called_once_with('players', object_id=1)
    
    @pytest.mark.asyncio
    async def test_get_players_by_team(self, player_service_instance, mock_client):
        """Test getting players by team."""
        mock_data = {
            'count': 2,
            'players': [
                self.create_player_data(1, 'Player1', team_id=5),
                self.create_player_data(2, 'Player2', team_id=5)
            ]
        }
        mock_client.get.return_value = mock_data
        
        result = await player_service_instance.get_players_by_team(5, season=12)
        
        assert len(result) == 2
        assert all(isinstance(p, Player) for p in result)
        mock_client.get.assert_called_once_with('players', params=[('season', '12'), ('team_id', '5')])
    
    @pytest.mark.asyncio
    async def test_get_players_by_name(self, player_service_instance, mock_client):
        """Test searching players by name."""
        mock_data = {
            'count': 1,
            'players': [
                self.create_player_data(1, 'John Smith', team_id=5)
            ]
        }
        mock_client.get.return_value = mock_data
        
        result = await player_service_instance.get_players_by_name('John', season=12)
        
        assert len(result) == 1
        assert result[0].name == 'John Smith'
        mock_client.get.assert_called_once_with('players', params=[('season', '12'), ('name', 'John')])
    
    @pytest.mark.asyncio
    async def test_get_player_by_name_exact(self, player_service_instance, mock_client):
        """Test exact name matching."""
        mock_data = {
            'count': 2,
            'players': [
                self.create_player_data(1, 'John Smith', team_id=5),
                self.create_player_data(2, 'John Doe', team_id=6)
            ]
        }
        mock_client.get.return_value = mock_data
        
        result = await player_service_instance.get_player_by_name_exact('John Smith', season=12)
        
        assert result is not None
        assert result.name == 'John Smith'
        assert result.id == 1
    
    @pytest.mark.asyncio
    async def test_get_free_agents(self, player_service_instance, mock_client):
        """Test getting free agents."""
        mock_data = {
            'count': 2,
            'players': [
                self.create_player_data(1, 'Free Agent 1', team_id=FREE_AGENT_TEAM_ID),
                self.create_player_data(2, 'Free Agent 2', team_id=FREE_AGENT_TEAM_ID)
            ]
        }
        mock_client.get.return_value = mock_data
        
        result = await player_service_instance.get_free_agents(season=12)
        
        assert len(result) == 2
        assert all(p.team_id == FREE_AGENT_TEAM_ID for p in result)
        mock_client.get.assert_called_once_with('players', params=[('team_id', FREE_AGENT_TEAM_ID), ('season', '12')])
    
    @pytest.mark.asyncio
    async def test_is_free_agent(self, player_service_instance):
        """Test free agent checking."""
        # Create test players with all required fields
        free_agent_data = self.create_player_data(1, 'Free Agent', team_id=FREE_AGENT_TEAM_ID)
        regular_player_data = self.create_player_data(2, 'Regular Player', team_id=5)
        
        free_agent = Player.from_api_data(free_agent_data)
        regular_player = Player.from_api_data(regular_player_data)
        
        assert await player_service_instance.is_free_agent(free_agent) is True
        assert await player_service_instance.is_free_agent(regular_player) is False
    
    @pytest.mark.asyncio
    async def test_search_players_fuzzy(self, player_service_instance, mock_client):
        """Test fuzzy search with relevance sorting."""
        mock_data = {
            'count': 3,
            'players': [
                self.create_player_data(1, 'John Smith', team_id=5),  # partial match
                self.create_player_data(2, 'John', team_id=6),        # exact match
                self.create_player_data(3, 'Johnny Doe', team_id=7)   # partial match
            ]
        }
        mock_client.get.return_value = mock_data
        
        result = await player_service_instance.search_players_fuzzy('John', limit=2)
        
        # Should return exact match first, then partial matches, limited to 2
        assert len(result) == 2
        assert result[0].name == 'John'  # exact match first
        mock_client.get.assert_called_once_with('players', params=[('season', '12'), ('name', 'John')])
    
    @pytest.mark.asyncio
    async def test_get_players_by_position(self, player_service_instance, mock_client):
        """Test getting players by position."""
        mock_data = {
            'count': 2,
            'players': [
                self.create_player_data(1, 'Catcher 1', position='C', team_id=5),
                self.create_player_data(2, 'Catcher 2', position='C', team_id=6)
            ]
        }
        mock_client.get.return_value = mock_data
        
        result = await player_service_instance.get_players_by_position('C', season=12)
        
        assert len(result) == 2
        assert all(p.primary_position == 'C' for p in result)
        mock_client.get.assert_called_once_with('players', params=[('position', 'C'), ('season', '12')])
    
    @pytest.mark.asyncio
    async def test_error_handling(self, player_service_instance, mock_client):
        """Test error handling in service methods."""
        mock_client.get.side_effect = APIException("API Error")
        
        # Should return None/empty list on errors, not raise
        result = await player_service_instance.get_player(1)
        assert result is None
        
        result = await player_service_instance.get_players_by_team(5, season=12)
        assert result == []


class TestPlayerServiceExtras:
    """Additional coverage tests for PlayerService edge cases."""
    
    def create_player_data(self, player_id: int, name: str, team_id: int = 5, position: str = 'C', **kwargs):
        """Create complete player data for testing."""
        base_data = {
            'id': player_id,
            'name': name,
            'wara': 2.5,
            'season': 12,
            'team_id': team_id,
            'image': f'https://example.com/player{player_id}.jpg',
            'pos_1': position,
        }
        base_data.update(kwargs)
        return base_data
    
    @pytest.mark.asyncio
    async def test_player_service_additional_methods(self):
        """Test additional PlayerService methods for coverage."""
        from services.player_service import PlayerService
        from constants import FREE_AGENT_TEAM_ID
        
        mock_client = AsyncMock()
        player_service = PlayerService()
        player_service._client = mock_client
        
        # Test additional functionality
        mock_client.get.return_value = {
            'count': 1,
            'players': [self.create_player_data(1, 'Test Player')]
        }
        
        result = await player_service.get_players_by_name('Test', season=12)
        assert len(result) == 1


class TestGlobalPlayerServiceInstance:
    """Test global player service instance."""
    
    def test_player_service_global(self):
        """Test global player service instance."""
        assert isinstance(player_service, PlayerService)
        assert player_service.model_class == Player
        assert player_service.endpoint == 'players'
    
    @pytest.mark.asyncio
    async def test_service_independence(self):
        """Test that service instances are independent."""
        service1 = PlayerService()
        service2 = PlayerService()
        
        # Should be different instances
        assert service1 is not service2
        # But same configuration
        assert service1.model_class == service2.model_class
        assert service1.endpoint == service2.endpoint