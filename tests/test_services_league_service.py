"""
Tests for league service functionality

Comprehensive testing of league-related operations including current state,
standings, division standings, and league leaders.
"""
import pytest
from unittest.mock import AsyncMock, patch
from typing import Dict, Any, List

from services.league_service import LeagueService, league_service
from models.current import Current
from exceptions import APIException


class TestLeagueService:
    """Test league service functionality."""
    
    @pytest.fixture
    def mock_current_data(self) -> Dict[str, Any]:
        """Mock current league state data."""
        return {
            'week': 10,
            'season': 13,
            'freeze': False,
            'bet_week': 'sheets',
            'trade_deadline': 14,
            'pick_trade_start': 15,
            'pick_trade_end': 18,
            'playoffs_begin': 19
        }
    
    @pytest.fixture
    def mock_standings_data(self) -> List[Dict[str, Any]]:
        """Mock standings data."""
        return [
            {
                'abbrev': 'NYY',
                'wins': 85,
                'losses': 45,
                'pct': 0.654,
                'gb': 0,
                'division_id': 1
            },
            {
                'abbrev': 'BOS',
                'wins': 80,
                'losses': 50,
                'pct': 0.615,
                'gb': 5,
                'division_id': 1
            },
            {
                'abbrev': 'LAD',
                'wins': 88,
                'losses': 42,
                'pct': 0.677,
                'gb': 0,
                'division_id': 2
            }
        ]
    
    @pytest.fixture
    def mock_leaders_data(self) -> List[Dict[str, Any]]:
        """Mock league leaders data."""
        return [
            {
                'name': 'Mike Trout',
                'avg': 0.325,
                'war': 8.5,
                'ops': 1.050
            },
            {
                'name': 'Mookie Betts',
                'avg': 0.318,
                'war': 7.8,
                'ops': 1.025
            },
            {
                'name': 'Aaron Judge',
                'avg': 0.305,
                'war': 7.2,
                'ops': 1.015
            }
        ]
    
    @pytest.mark.asyncio
    async def test_get_current_state_success(self, mock_current_data):
        """Test successful retrieval of current league state."""
        service = LeagueService()
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.return_value = mock_current_data
            mock_client.return_value = mock_api
            
            result = await service.get_current_state()
            
            assert result is not None
            assert isinstance(result, Current)
            assert result.week == 10
            assert result.season == 13
            assert result.freeze is False
            assert result.trade_deadline == 14
            
            mock_api.get.assert_called_once_with('current')
    
    @pytest.mark.asyncio
    async def test_get_current_state_no_data(self):
        """Test get_current_state when no data is returned."""
        service = LeagueService()
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.return_value = None
            mock_client.return_value = mock_api
            
            result = await service.get_current_state()
            
            assert result is None
            mock_api.get.assert_called_once_with('current')
    
    @pytest.mark.asyncio
    async def test_get_current_state_exception(self):
        """Test get_current_state exception handling."""
        service = LeagueService()
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.side_effect = Exception("API Error")
            mock_client.return_value = mock_api
            
            result = await service.get_current_state()
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_standings_success_list(self, mock_standings_data):
        """Test successful retrieval of standings as list."""
        service = LeagueService()
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.return_value = mock_standings_data
            mock_client.return_value = mock_api
            
            result = await service.get_standings(13)

            assert result is not None
            assert len(result) == 3
            assert result[0]['abbrev'] == 'NYY'
            assert result[0]['wins'] == 85

            mock_api.get.assert_called_once_with('standings', params=[('season', '13')])
    
    @pytest.mark.asyncio
    async def test_get_standings_success_dict(self, mock_standings_data):
        """Test successful retrieval of standings wrapped in dict."""
        service = LeagueService()
        wrapped_data = {'standings': mock_standings_data}
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.return_value = wrapped_data
            mock_client.return_value = mock_api
            
            result = await service.get_standings()
            
            assert result is not None
            assert len(result) == 3
            assert result[0]['abbrev'] == 'NYY'
            
            mock_api.get.assert_called_once_with('standings', params=[('season', '13')])
    
    @pytest.mark.asyncio
    async def test_get_standings_no_data(self):
        """Test get_standings when no data is returned."""
        service = LeagueService()
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.return_value = None
            mock_client.return_value = mock_api
            
            result = await service.get_standings()
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_standings_exception(self):
        """Test get_standings exception handling."""
        service = LeagueService()
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.side_effect = Exception("API Error")
            mock_client.return_value = mock_api
            
            result = await service.get_standings()
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_division_standings_success(self):
        """Test successful retrieval of division standings."""
        service = LeagueService()
        division_data = [
            {'abbrev': 'NYY', 'wins': 85, 'losses': 45, 'division_id': 1},
            {'abbrev': 'BOS', 'wins': 80, 'losses': 50, 'division_id': 1}
        ]
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.return_value = division_data
            mock_client.return_value = mock_api
            
            result = await service.get_division_standings(1, 13)

            assert result is not None
            assert len(result) == 2
            assert all(team['division_id'] == 1 for team in result)

            mock_api.get.assert_called_once_with('standings/division/1', params=[('season', '13')])
    
    @pytest.mark.asyncio
    async def test_get_division_standings_no_data(self):
        """Test get_division_standings when no data is returned."""
        service = LeagueService()
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.return_value = None
            mock_client.return_value = mock_api
            
            result = await service.get_division_standings(1)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_division_standings_exception(self):
        """Test get_division_standings exception handling."""
        service = LeagueService()
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.side_effect = Exception("API Error")
            mock_client.return_value = mock_api
            
            result = await service.get_division_standings(1, 13)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_league_leaders_success_list(self, mock_leaders_data):
        """Test successful retrieval of league leaders as list."""
        service = LeagueService()
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.return_value = mock_leaders_data
            mock_client.return_value = mock_api
            
            result = await service.get_league_leaders('batting', 13, 10)

            assert result is not None
            assert len(result) == 3
            assert result[0]['name'] == 'Mike Trout'
            assert result[0]['avg'] == 0.325

            expected_params = [('season', '13'), ('limit', '10')]
            mock_api.get.assert_called_once_with('leaders/batting', params=expected_params)
    
    @pytest.mark.asyncio
    async def test_get_league_leaders_success_dict(self, mock_leaders_data):
        """Test successful retrieval of league leaders wrapped in dict."""
        service = LeagueService()
        wrapped_data = {'leaders': mock_leaders_data}
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.return_value = wrapped_data
            mock_client.return_value = mock_api
            
            result = await service.get_league_leaders('pitching', 13, 5)

            assert result is not None
            assert len(result) == 3
            assert result[0]['name'] == 'Mike Trout'

            expected_params = [('season', '13'), ('limit', '5')]
            mock_api.get.assert_called_once_with('leaders/pitching', params=expected_params)
    
    @pytest.mark.asyncio
    async def test_get_league_leaders_limit_enforcement(self, mock_leaders_data):
        """Test that league leaders respects the limit parameter."""
        service = LeagueService()
        long_list = mock_leaders_data * 5  # 15 items
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.return_value = long_list
            mock_client.return_value = mock_api
            
            result = await service.get_league_leaders('batting', 12, 5)
            
            assert result is not None
            assert len(result) == 5  # Should be limited to 5
    
    @pytest.mark.asyncio
    async def test_get_league_leaders_default_params(self, mock_leaders_data):
        """Test league leaders with default parameters."""
        service = LeagueService()
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.return_value = mock_leaders_data
            mock_client.return_value = mock_api
            
            result = await service.get_league_leaders()
            
            assert result is not None
            expected_params = [('season', '13'), ('limit', '10')]
            mock_api.get.assert_called_once_with('leaders/batting', params=expected_params)
    
    @pytest.mark.asyncio
    async def test_get_league_leaders_no_data(self):
        """Test get_league_leaders when no data is returned."""
        service = LeagueService()
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.return_value = None
            mock_client.return_value = mock_api
            
            result = await service.get_league_leaders()
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_league_leaders_exception(self):
        """Test get_league_leaders exception handling."""
        service = LeagueService()
        
        with patch.object(service, 'get_client') as mock_client:
            mock_api = AsyncMock()
            mock_api.get.side_effect = Exception("API Error")
            mock_client.return_value = mock_api
            
            result = await service.get_league_leaders('batting', 13)
            
            assert result is None
    
    def test_league_service_global_instance(self):
        """Test that global league_service instance exists."""
        assert league_service is not None
        assert isinstance(league_service, LeagueService)