"""
API client tests using aioresponses for clean HTTP mocking
"""
import pytest
import asyncio
import aiohttp
from unittest.mock import MagicMock, patch
from aioresponses import aioresponses

from api.client import APIClient, get_api_client, get_global_client, cleanup_global_client
from exceptions import APIException


class TestAPIClientWithAioresponses:
    """Test API client with aioresponses for HTTP mocking."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = MagicMock()
        config.db_url = "https://api.example.com"
        config.api_token = "test-token"
        return config
    
    @pytest.fixture
    def api_client(self, mock_config):
        """Create API client with mocked config."""
        with patch('api.client.get_config', return_value=mock_config):
            return APIClient()
    
    @pytest.mark.asyncio
    async def test_get_request_success(self, api_client):
        """Test successful GET request."""
        expected_data = {"id": 1, "name": "Test Player"}
        
        with aioresponses() as m:
            m.get(
                "https://api.example.com/v3/players/1",
                payload=expected_data,
                status=200
            )
            
            result = await api_client.get("players", object_id=1)
            
            assert result == expected_data
    
    @pytest.mark.asyncio
    async def test_get_request_404(self, api_client):
        """Test GET request returning 404."""
        with aioresponses() as m:
            m.get(
                "https://api.example.com/v3/players/999",
                status=404
            )
            
            result = await api_client.get("players", object_id=999)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_request_401_auth_error(self, api_client):
        """Test GET request with authentication error."""
        with aioresponses() as m:
            m.get(
                "https://api.example.com/v3/players",
                status=401
            )
            
            with pytest.raises(APIException, match="Authentication failed"):
                await api_client.get("players")
    
    @pytest.mark.asyncio
    async def test_get_request_403_forbidden(self, api_client):
        """Test GET request with forbidden error."""
        with aioresponses() as m:
            m.get(
                "https://api.example.com/v3/players",
                status=403
            )
            
            with pytest.raises(APIException, match="Access forbidden"):
                await api_client.get("players")
    
    @pytest.mark.asyncio
    async def test_get_request_500_server_error(self, api_client):
        """Test GET request with server error."""
        with aioresponses() as m:
            m.get(
                "https://api.example.com/v3/players",
                status=500,
                body="Internal Server Error"
            )
            
            with pytest.raises(APIException, match="API request failed with status 500"):
                await api_client.get("players")
    
    @pytest.mark.asyncio
    async def test_get_request_with_params(self, api_client):
        """Test GET request with query parameters."""
        expected_data = {"count": 2, "players": [{"id": 1}, {"id": 2}]}
        
        with aioresponses() as m:
            m.get(
                "https://api.example.com/v3/players?team_id=5&season=12",
                payload=expected_data,
                status=200
            )
            
            result = await api_client.get("players", params=[("team_id", "5"), ("season", "12")])
            
            assert result == expected_data
    
    @pytest.mark.asyncio
    async def test_post_request_success(self, api_client):
        """Test successful POST request."""
        input_data = {"name": "New Player", "position": "C"}
        expected_response = {"id": 1, "name": "New Player", "position": "C"}
        
        with aioresponses() as m:
            m.post(
                "https://api.example.com/v3/players",
                payload=expected_response,
                status=201
            )
            
            result = await api_client.post("players", input_data)
            
            assert result == expected_response
    
    @pytest.mark.asyncio
    async def test_post_request_400_error(self, api_client):
        """Test POST request with validation error."""
        input_data = {"invalid": "data"}
        
        with aioresponses() as m:
            m.post(
                "https://api.example.com/v3/players",
                status=400,
                body="Invalid data"
            )
            
            with pytest.raises(APIException, match="POST request failed with status 400"):
                await api_client.post("players", input_data)
    
    @pytest.mark.asyncio
    async def test_put_request_success(self, api_client):
        """Test successful PUT request."""
        update_data = {"name": "Updated Player"}
        expected_response = {"id": 1, "name": "Updated Player"}
        
        with aioresponses() as m:
            m.put(
                "https://api.example.com/v3/players/1",
                payload=expected_response,
                status=200
            )
            
            result = await api_client.put("players", update_data, object_id=1)
            
            assert result == expected_response
    
    @pytest.mark.asyncio
    async def test_put_request_404(self, api_client):
        """Test PUT request with 404."""
        update_data = {"name": "Updated Player"}
        
        with aioresponses() as m:
            m.put(
                "https://api.example.com/v3/players/999",
                status=404
            )
            
            result = await api_client.put("players", update_data, object_id=999)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_request_success(self, api_client):
        """Test successful DELETE request."""
        with aioresponses() as m:
            m.delete(
                "https://api.example.com/v3/players/1",
                status=204
            )
            
            result = await api_client.delete("players", object_id=1)
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_request_404(self, api_client):
        """Test DELETE request with 404."""
        with aioresponses() as m:
            m.delete(
                "https://api.example.com/v3/players/999",
                status=404
            )
            
            result = await api_client.delete("players", object_id=999)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_request_200_success(self, api_client):
        """Test DELETE request with 200 success."""
        with aioresponses() as m:
            m.delete(
                "https://api.example.com/v3/players/1",
                status=200
            )
            
            result = await api_client.delete("players", object_id=1)
            
            assert result is True


class TestAPIClientHelpers:
    """Test API client helper functions."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = MagicMock()
        config.db_url = "https://api.example.com"
        config.api_token = "test-token"
        return config
    
    @pytest.mark.asyncio
    async def test_get_api_client_context_manager(self, mock_config):
        """Test get_api_client context manager."""
        with patch('api.client.get_config', return_value=mock_config):
            with aioresponses() as m:
                m.get(
                    "https://api.example.com/v3/test",
                    payload={"success": True},
                    status=200
                )
                
                async with get_api_client() as client:
                    assert isinstance(client, APIClient)
                    result = await client.get("test")
                    assert result == {"success": True}
    
    @pytest.mark.asyncio
    async def test_global_client_management(self, mock_config):
        """Test global client getter and cleanup."""
        with patch('api.client.get_config', return_value=mock_config):
            # Get global client
            client1 = await get_global_client()
            client2 = await get_global_client()
            
            # Should return same instance
            assert client1 is client2
            assert isinstance(client1, APIClient)
            
            # Test cleanup
            await cleanup_global_client()
            
            # New client should be different instance
            client3 = await get_global_client()
            assert client3 is not client1
            
            # Clean up for other tests
            await cleanup_global_client()


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = MagicMock()
        config.db_url = "https://api.example.com"
        config.api_token = "test-token"
        return config
    
    @pytest.mark.asyncio
    async def test_player_retrieval_with_team_lookup(self, mock_config):
        """Test realistic scenario: get player with team data."""
        with patch('api.client.get_config', return_value=mock_config):
            with aioresponses() as m:
                # Mock player data response
                player_data = {
                    "id": 1,
                    "name": "Test Player",
                    "wara": 2.5,
                    "season": 12,
                    "team_id": 5,
                    "image": "https://example.com/player1.jpg",
                    "pos_1": "C"
                }
                m.get(
                    "https://api.example.com/v3/players/1",
                    payload=player_data,
                    status=200
                )
                
                # Mock team data response
                team_data = {
                    "id": 5,
                    "abbrev": "TST",
                    "sname": "Test Team",
                    "lname": "Test Team Full Name",
                    "season": 12
                }
                m.get(
                    "https://api.example.com/v3/teams/5",
                    payload=team_data,
                    status=200
                )
                
                client = APIClient()
                
                # Get player
                player = await client.get("players", object_id=1)
                assert player["name"] == "Test Player"
                assert player["team_id"] == 5
                
                # Get team for player
                team = await client.get("teams", object_id=player["team_id"])
                assert team["sname"] == "Test Team"
    
    @pytest.mark.asyncio
    async def test_api_response_format_handling(self, mock_config):
        """Test handling of the API's count + list format."""
        with patch('api.client.get_config', return_value=mock_config):
            with aioresponses() as m:
                # Mock API response with count format
                api_response = {
                    "count": 25,
                    "players": [
                        {
                            "id": 1,
                            "name": "Player 1",
                            "wara": 2.5,
                            "season": 12,
                            "team_id": 5,
                            "image": "https://example.com/player1.jpg",
                            "pos_1": "C"
                        },
                        {
                            "id": 2,
                            "name": "Player 2",
                            "wara": 1.8,
                            "season": 12,
                            "team_id": 6,
                            "image": "https://example.com/player2.jpg",
                            "pos_1": "1B"
                        }
                    ]
                }
                
                m.get(
                    "https://api.example.com/v3/players?team_id=5",
                    payload=api_response,
                    status=200
                )
                
                client = APIClient()
                result = await client.get("players", params=[("team_id", "5")])
                
                assert result["count"] == 25
                assert len(result["players"]) == 2
                assert result["players"][0]["name"] == "Player 1"
    
    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self, mock_config):
        """Test error handling and recovery."""
        with patch('api.client.get_config', return_value=mock_config):
            with aioresponses() as m:
                # First request fails with 500
                m.get(
                    "https://api.example.com/v3/players/1",
                    status=500,
                    body="Internal Server Error"
                )
                
                # Second request succeeds
                m.get(
                    "https://api.example.com/v3/players/2",
                    payload={"id": 2, "name": "Working Player"},
                    status=200
                )
                
                client = APIClient()
                
                # First request should raise exception
                with pytest.raises(APIException, match="API request failed"):
                    await client.get("players", object_id=1)
                
                # Second request should work fine
                result = await client.get("players", object_id=2)
                assert result["name"] == "Working Player"
                
                # Client should still be functional
                await client.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, mock_config):
        """Test multiple concurrent requests."""
        import asyncio
        
        with patch('api.client.get_config', return_value=mock_config):
            with aioresponses() as m:
                # Mock multiple endpoints
                for i in range(1, 4):
                    m.get(
                        f"https://api.example.com/v3/players/{i}",
                        payload={"id": i, "name": f"Player {i}"},
                        status=200
                    )
                
                client = APIClient()
                
                # Make concurrent requests
                tasks = [
                    client.get("players", object_id=1),
                    client.get("players", object_id=2),
                    client.get("players", object_id=3)
                ]
                
                results = await asyncio.gather(*tasks)
                
                assert len(results) == 3
                assert results[0]["name"] == "Player 1"
                assert results[1]["name"] == "Player 2"
                assert results[2]["name"] == "Player 3"
                
                await client.close()


class TestAPIClientCoverageExtras:
    """Additional coverage tests for API client edge cases."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = MagicMock()
        config.db_url = "https://api.example.com"
        config.api_token = "test-token"
        return config
    
    @pytest.mark.asyncio
    async def test_global_client_cleanup_when_none(self):
        """Test cleanup when no global client exists."""
        # Ensure no global client exists
        await cleanup_global_client()
        
        # Should not raise error
        await cleanup_global_client()
    
    @pytest.mark.asyncio
    async def test_url_building_edge_cases(self, mock_config):
        """Test URL building with various edge cases."""
        with patch('api.client.get_config', return_value=mock_config):
            client = APIClient()
            
            # Test trailing slash handling
            client.base_url = "https://api.example.com/"
            url = client._build_url("players")
            assert url == "https://api.example.com/v3/players"
            assert "//" not in url.replace("https://", "")
    
    @pytest.mark.asyncio
    async def test_parameter_handling_edge_cases(self, mock_config):
        """Test parameter handling with various scenarios."""
        with patch('api.client.get_config', return_value=mock_config):
            client = APIClient()
            
            # Test with existing query string
            url = client._add_params("https://example.com/api?existing=true", [("new", "param")])
            assert url == "https://example.com/api?existing=true&new=param"
            
            # Test with no parameters
            url = client._add_params("https://example.com/api")
            assert url == "https://example.com/api"
    
    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, mock_config):
        """Test timeout error handling using aioresponses."""
        with patch('api.client.get_config', return_value=mock_config):
            client = APIClient()
            
            # Test timeout using aioresponses exception parameter
            with aioresponses() as m:
                m.get(
                    "https://api.example.com/v3/players",
                    exception=asyncio.TimeoutError("Request timed out")
                )
                
                with pytest.raises(APIException, match="API call failed.*Request timed out"):
                    await client.get("players")
                    
            await client.close()
    
    @pytest.mark.asyncio
    async def test_generic_exception_handling(self, mock_config):
        """Test generic exception handling."""
        with patch('api.client.get_config', return_value=mock_config):
            client = APIClient()
            
            # Test generic exception
            with aioresponses() as m:
                m.get(
                    "https://api.example.com/v3/players",
                    exception=Exception("Generic error")
                )
                
                with pytest.raises(APIException, match="API call failed.*Generic error"):
                    await client.get("players")
                    
            await client.close()
    
    @pytest.mark.asyncio
    async def test_session_closed_handling(self, mock_config):
        """Test handling of closed session."""
        with patch('api.client.get_config', return_value=mock_config):
            # Test that the client recreates session when needed
            with aioresponses() as m:
                m.get(
                    "https://api.example.com/v3/players",
                    payload={"success": True},
                    status=200
                )
                
                client = APIClient()
                
                # Close the session manually
                await client._ensure_session()
                await client._session.close()
                
                # Client should recreate session and work fine
                result = await client.get("players")
                assert result == {"success": True}
                
                await client.close()