"""
Tests for Custom Commands Service in Discord Bot v2.0

Fixed version with proper mocking following established patterns.
"""
import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from services.custom_commands_service import (
    CustomCommandsService,
    CustomCommandNotFoundError,
    CustomCommandExistsError,
    CustomCommandPermissionError
)
from models.custom_command import (
    CustomCommand,
    CustomCommandCreator,
    CustomCommandSearchFilters,
    CustomCommandSearchResult,
    CustomCommandStats
)


@pytest.fixture
def sample_creator() -> CustomCommandCreator:
    """Fixture providing a sample creator."""
    return CustomCommandCreator(
        id=1,
        discord_id=12345,
        username="testuser",
        display_name="Test User",
        created_at=datetime.now(timezone.utc),
        total_commands=5,
        active_commands=5
    )


@pytest.fixture
def sample_command(sample_creator: CustomCommandCreator) -> CustomCommand:
    """Fixture providing a sample command."""
    now = datetime.now(timezone.utc)
    return CustomCommand(
        id=1,
        name="testcmd",
        content="This is a test command response",
        creator_id=sample_creator.id,
        creator=sample_creator,
        created_at=now,
        updated_at=None,
        last_used=now - timedelta(days=2),
        use_count=10,
        warning_sent=False,
        is_active=True,
        tags=None
    )


@pytest.fixture
def mock_client():
    """Mock API client."""
    client = AsyncMock()
    return client


@pytest.fixture
def custom_commands_service_instance(mock_client):
    """Create CustomCommandsService instance with mocked client."""
    service = CustomCommandsService()
    service._client = mock_client
    return service


class TestCustomCommandsServiceInit:
    """Test service initialization and basic functionality."""
    
    def test_service_singleton_pattern(self):
        """Test that the service follows singleton pattern."""
        from services.custom_commands_service import custom_commands_service
        
        # Multiple imports should return the same instance
        from services.custom_commands_service import custom_commands_service as service2
        assert custom_commands_service is service2
    
    def test_service_has_required_methods(self):
        """Test that service has all required methods."""
        from services.custom_commands_service import custom_commands_service
        
        # Core CRUD operations
        assert hasattr(custom_commands_service, 'create_command')
        assert hasattr(custom_commands_service, 'get_command_by_name')
        assert hasattr(custom_commands_service, 'update_command')
        assert hasattr(custom_commands_service, 'delete_command')
        
        # Search and listing
        assert hasattr(custom_commands_service, 'search_commands')
        assert hasattr(custom_commands_service, 'get_commands_by_creator')
        assert hasattr(custom_commands_service, 'get_command_names_for_autocomplete')
        
        # Execution
        assert hasattr(custom_commands_service, 'execute_command')
        
        # Management
        assert hasattr(custom_commands_service, 'get_statistics')
        assert hasattr(custom_commands_service, 'get_commands_needing_warning')
        assert hasattr(custom_commands_service, 'get_commands_eligible_for_deletion')


class TestCustomCommandsServiceCRUD:
    """Test CRUD operations of the custom commands service."""
    
    @pytest.mark.asyncio
    async def test_create_command_success(self, custom_commands_service_instance, sample_creator):
        """Test successful command creation."""
        # Mock the service methods directly
        created_command = None
        
        async def mock_get_command_by_name(name, *args, **kwargs):
            if created_command and name == "hello":
                return created_command
            # Command doesn't exist initially - raise exception
            raise CustomCommandNotFoundError(f"Custom command '{name}' not found")
        
        async def mock_get_or_create_creator(*args, **kwargs):
            return sample_creator
        
        async def mock_create(data):
            nonlocal created_command
            # Create the command model directly from the data 
            created_command = CustomCommand(
                id=1,
                name=data["name"],
                content=data["content"],
                creator_id=sample_creator.id,
                creator=sample_creator,
                created_at=datetime.now(timezone.utc),
                updated_at=None,
                last_used=datetime.now(timezone.utc),
                use_count=0,
                warning_sent=False,
                is_active=True,
                tags=None
            )
            return created_command
        
        async def mock_update_creator_stats(*args, **kwargs):
            return None
        
        # Patch the service methods
        custom_commands_service_instance.get_command_by_name = mock_get_command_by_name
        custom_commands_service_instance.get_or_create_creator = mock_get_or_create_creator
        custom_commands_service_instance.create = mock_create
        custom_commands_service_instance._update_creator_stats = mock_update_creator_stats
        
        result = await custom_commands_service_instance.create_command(
            name="hello",
            content="Hello, world!",
            creator_discord_id=12345,
            creator_username="testuser",
            creator_display_name="Test User"
        )
        
        assert isinstance(result, CustomCommand)
        assert result.name == "hello"
        assert result.content == "Hello, world!"
        assert result.creator.discord_id == 12345
        assert result.use_count == 0
    
    @pytest.mark.asyncio
    async def test_create_command_already_exists(self, custom_commands_service_instance, sample_command):
        """Test command creation when command already exists."""
        # Mock command already exists
        async def mock_get_command_by_name(*args, **kwargs):
            return sample_command
        
        custom_commands_service_instance.get_command_by_name = mock_get_command_by_name
        
        with pytest.raises(CustomCommandExistsError, match="Command 'hello' already exists"):
            await custom_commands_service_instance.create_command(
                name="hello",
                content="Hello, world!",
                creator_discord_id=12345,
                creator_username="testuser"
            )
    
    @pytest.mark.asyncio
    async def test_get_command_by_name_success(self, custom_commands_service_instance, sample_command, sample_creator):
        """Test successful command retrieval."""
        # Mock the API client to return proper data structure
        command_data = {
            'id': sample_command.id,
            'name': sample_command.name,
            'content': sample_command.content,
            'creator_id': sample_command.creator_id,
            'creator': {
                'id': sample_creator.id,
                'discord_id': sample_creator.discord_id,
                'username': sample_creator.username,
                'display_name': sample_creator.display_name,
                'created_at': sample_creator.created_at.isoformat(),
                'total_commands': sample_creator.total_commands,
                'active_commands': sample_creator.active_commands
            },
            'created_at': sample_command.created_at.isoformat(),
            'updated_at': sample_command.updated_at.isoformat() if sample_command.updated_at else None,
            'last_used': sample_command.last_used.isoformat() if sample_command.last_used else None,
            'use_count': sample_command.use_count,
            'warning_sent': sample_command.warning_sent,
            'is_active': sample_command.is_active,
            'tags': sample_command.tags
        }
        
        custom_commands_service_instance._client.get.return_value = command_data
        
        result = await custom_commands_service_instance.get_command_by_name("testcmd")
        
        assert isinstance(result, CustomCommand)
        assert result.name == "testcmd"
        assert result.use_count == 10
    
    @pytest.mark.asyncio
    async def test_get_command_by_name_not_found(self, custom_commands_service_instance):
        """Test command retrieval when command doesn't exist."""
        # Mock the API client to return None (not found)
        custom_commands_service_instance._client.get.return_value = None
        
        with pytest.raises(CustomCommandNotFoundError, match="Custom command 'nonexistent' not found"):
            await custom_commands_service_instance.get_command_by_name("nonexistent")


class TestCustomCommandsServiceErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_api_connection_error(self, custom_commands_service_instance):
        """Test handling of API connection errors."""
        from exceptions import APIException, BotException
        
        # Mock the API client to raise an APIException
        custom_commands_service_instance._client.get.side_effect = APIException("Connection error")
        
        with pytest.raises(BotException, match="Failed to retrieve command 'test'"):
            await custom_commands_service_instance.get_command_by_name("test")