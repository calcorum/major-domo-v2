"""
Tests for service integration and global service instances
"""
import pytest

from services.player_service import PlayerService, player_service
from services.team_service import TeamService, team_service
from models.player import Player
from models.team import Team


class TestGlobalServiceInstances:
    """Test global service instances and their integration."""
    
    def test_player_service_global(self):
        """Test global player service instance."""
        assert isinstance(player_service, PlayerService)
        assert player_service.model_class == Player
        assert player_service.endpoint == 'players'
    
    def test_team_service_global(self):
        """Test global team service instance."""
        assert isinstance(team_service, TeamService)
        assert team_service.model_class == Team
        assert team_service.endpoint == 'teams'
    
    def test_service_wiring(self):
        """Test that services are properly wired together."""
        # PlayerService should have TeamService injected
        assert player_service._team_service is not None
        assert isinstance(player_service._team_service, TeamService)
        assert player_service._team_service is team_service
    
    @pytest.mark.asyncio
    async def test_service_independence(self):
        """Test that service instances are independent."""
        player_service1 = PlayerService()
        player_service2 = PlayerService()
        team_service1 = TeamService()
        team_service2 = TeamService()
        
        # Should be different instances
        assert player_service1 is not player_service2
        assert team_service1 is not team_service2
        
        # But same configuration
        assert player_service1.model_class == player_service2.model_class
        assert player_service1.endpoint == player_service2.endpoint
        assert team_service1.model_class == team_service2.model_class
        assert team_service1.endpoint == team_service2.endpoint
    
    def test_service_imports_work(self):
        """Test that service imports work from the main services module."""
        from services import player_service, team_service, PlayerService, TeamService
        
        # Should be able to import both services and their classes
        assert isinstance(player_service, PlayerService)
        assert isinstance(team_service, TeamService)
        
        # Should be the same instances as imported directly
        from services.player_service import player_service as direct_player_service
        from services.team_service import team_service as direct_team_service
        
        assert player_service is direct_player_service
        assert team_service is direct_team_service