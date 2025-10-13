"""
Tests for Help Commands Service in Discord Bot v2.0

Comprehensive tests for help commands CRUD operations and business logic.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

from services.help_commands_service import (
    HelpCommandsService,
    HelpCommandNotFoundError,
    HelpCommandExistsError
)
from models.help_command import (
    HelpCommand,
    HelpCommandSearchFilters,
    HelpCommandSearchResult,
    HelpCommandStats
)


@pytest.fixture
def sample_help_command() -> HelpCommand:
    """Fixture providing a sample help command."""
    now = datetime.now(timezone.utc)
    return HelpCommand(
        id=1,
        name='trading-rules',
        title='Trading Rules & Guidelines',
        content='Complete trading rules for the league...',
        category='rules',
        created_by_discord_id='123456789',
        created_at=now,
        updated_at=None,
        last_modified_by=None,
        is_active=True,
        view_count=100,
        display_order=10
    )


@pytest.fixture
def mock_client():
    """Mock API client."""
    client = AsyncMock()
    return client


@pytest.fixture
def help_commands_service_instance(mock_client):
    """Create HelpCommandsService instance with mocked client."""
    service = HelpCommandsService()
    service._client = mock_client
    return service


class TestHelpCommandsServiceInit:
    """Test service initialization and basic functionality."""

    def test_service_singleton_pattern(self):
        """Test that the service follows singleton pattern."""
        from services.help_commands_service import help_commands_service

        # Multiple imports should return the same instance
        from services.help_commands_service import help_commands_service as service2
        assert help_commands_service is service2

    def test_service_has_required_methods(self):
        """Test that service has all required methods."""
        from services.help_commands_service import help_commands_service

        # Core CRUD operations
        assert hasattr(help_commands_service, 'create_help')
        assert hasattr(help_commands_service, 'get_help_by_name')
        assert hasattr(help_commands_service, 'update_help')
        assert hasattr(help_commands_service, 'delete_help')
        assert hasattr(help_commands_service, 'restore_help')

        # Search and listing
        assert hasattr(help_commands_service, 'search_help_commands')
        assert hasattr(help_commands_service, 'get_all_help_topics')
        assert hasattr(help_commands_service, 'get_help_names_for_autocomplete')

        # View tracking
        assert hasattr(help_commands_service, 'increment_view_count')

        # Statistics
        assert hasattr(help_commands_service, 'get_statistics')


class TestHelpCommandsServiceCRUD:
    """Test CRUD operations of the help commands service."""

    @pytest.mark.asyncio
    async def test_create_help_success(self, help_commands_service_instance):
        """Test successful help command creation."""
        created_help = None

        async def mock_get_help_by_name(name, *args, **kwargs):
            if created_help and name == "test-topic":
                return created_help
            # Command doesn't exist initially - raise exception
            raise HelpCommandNotFoundError(f"Help topic '{name}' not found")

        async def mock_create(data):
            nonlocal created_help
            # Create the help command model directly from the data
            created_help = HelpCommand(
                id=1,
                name=data["name"],
                title=data["title"],
                content=data["content"],
                category=data.get("category"),
                created_by_discord_id=data["created_by_discord_id"],
                created_at=datetime.now(timezone.utc),
                updated_at=None,
                last_modified_by=None,
                is_active=True,
                view_count=0,
                display_order=data.get("display_order", 0)
            )
            return created_help

        # Patch the service methods
        help_commands_service_instance.get_help_by_name = mock_get_help_by_name
        help_commands_service_instance.create = mock_create

        result = await help_commands_service_instance.create_help(
            name="test-topic",
            title="Test Topic",
            content="This is test content for the help topic.",
            creator_discord_id='123456789',
            category="info"
        )

        assert isinstance(result, HelpCommand)
        assert result.name == "test-topic"
        assert result.title == "Test Topic"
        assert result.category == "info"
        assert result.view_count == 0

    @pytest.mark.asyncio
    async def test_create_help_already_exists(self, help_commands_service_instance, sample_help_command):
        """Test help command creation when topic already exists."""
        # Mock topic already exists
        async def mock_get_help_by_name(*args, **kwargs):
            return sample_help_command

        help_commands_service_instance.get_help_by_name = mock_get_help_by_name

        with pytest.raises(HelpCommandExistsError, match="Help topic 'trading-rules' already exists"):
            await help_commands_service_instance.create_help(
                name="trading-rules",
                title="Trading Rules",
                content="Rules content",
                creator_discord_id='123456789'
            )

    @pytest.mark.asyncio
    async def test_get_help_by_name_success(self, help_commands_service_instance, sample_help_command):
        """Test successful help command retrieval."""
        # Mock the API client to return proper data structure
        help_data = {
            'id': sample_help_command.id,
            'name': sample_help_command.name,
            'title': sample_help_command.title,
            'content': sample_help_command.content,
            'category': sample_help_command.category,
            'created_by_discord_id': sample_help_command.created_by_discord_id,
            'created_at': sample_help_command.created_at.isoformat(),
            'updated_at': sample_help_command.updated_at.isoformat() if sample_help_command.updated_at else None,
            'last_modified_by': sample_help_command.last_modified_by,
            'is_active': sample_help_command.is_active,
            'view_count': sample_help_command.view_count,
            'display_order': sample_help_command.display_order
        }

        help_commands_service_instance._client.get.return_value = help_data

        result = await help_commands_service_instance.get_help_by_name("trading-rules")

        assert isinstance(result, HelpCommand)
        assert result.name == "trading-rules"
        assert result.title == "Trading Rules & Guidelines"
        assert result.view_count == 100

    @pytest.mark.asyncio
    async def test_get_help_by_name_not_found(self, help_commands_service_instance):
        """Test help command retrieval when topic doesn't exist."""
        # Mock the API client to return None (not found)
        help_commands_service_instance._client.get.return_value = None

        with pytest.raises(HelpCommandNotFoundError, match="Help topic 'nonexistent' not found"):
            await help_commands_service_instance.get_help_by_name("nonexistent")

    @pytest.mark.asyncio
    async def test_update_help_success(self, help_commands_service_instance, sample_help_command):
        """Test successful help command update."""
        # Mock getting the existing help command
        async def mock_get_help_by_name(name, include_inactive=False):
            if name == "trading-rules":
                return sample_help_command
            raise HelpCommandNotFoundError(f"Help topic '{name}' not found")

        # Mock the API update call
        async def mock_put(*args, **kwargs):
            return True

        help_commands_service_instance.get_help_by_name = mock_get_help_by_name
        help_commands_service_instance._client.put = mock_put

        # Update should call get_help_by_name again at the end, so mock it to return updated version
        updated_help = HelpCommand(
            id=sample_help_command.id,
            name=sample_help_command.name,
            title="Updated Trading Rules",
            content="Updated content",
            category=sample_help_command.category,
            created_by_discord_id=sample_help_command.created_by_discord_id,
            created_at=sample_help_command.created_at,
            updated_at=datetime.now(timezone.utc),
            last_modified_by='987654321',
            is_active=sample_help_command.is_active,
            view_count=sample_help_command.view_count,
            display_order=sample_help_command.display_order
        )

        call_count = 0

        async def mock_get_with_counter(name, include_inactive=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return sample_help_command
            else:
                return updated_help

        help_commands_service_instance.get_help_by_name = mock_get_with_counter

        result = await help_commands_service_instance.update_help(
            name="trading-rules",
            new_title="Updated Trading Rules",
            new_content="Updated content",
            updater_discord_id='987654321'
        )

        assert isinstance(result, HelpCommand)
        assert result.title == "Updated Trading Rules"

    @pytest.mark.asyncio
    async def test_delete_help_success(self, help_commands_service_instance, sample_help_command):
        """Test successful help command deletion (soft delete)."""
        # Mock getting the help command
        async def mock_get_help_by_name(name, include_inactive=False):
            return sample_help_command

        # Mock the API delete call
        async def mock_delete(*args, **kwargs):
            return None

        help_commands_service_instance.get_help_by_name = mock_get_help_by_name
        help_commands_service_instance._client.delete = mock_delete

        result = await help_commands_service_instance.delete_help("trading-rules")

        assert result is True

    @pytest.mark.asyncio
    async def test_restore_help_success(self, help_commands_service_instance):
        """Test successful help command restoration."""
        # Mock getting a deleted help command
        deleted_help = HelpCommand(
            id=1,
            name='deleted-topic',
            title='Deleted Topic',
            content='Content',
            created_by_discord_id='123456789',
            created_at=datetime.now(timezone.utc),
            is_active=False
        )

        async def mock_get_help_by_name(name, include_inactive=False):
            return deleted_help

        # Mock the API restore call
        restored_data = {
            'id': deleted_help.id,
            'name': deleted_help.name,
            'title': deleted_help.title,
            'content': deleted_help.content,
            'created_by_discord_id': deleted_help.created_by_discord_id,
            'created_at': deleted_help.created_at.isoformat(),
            'is_active': True,
            'view_count': 0,
            'display_order': 0
        }

        help_commands_service_instance.get_help_by_name = mock_get_help_by_name
        help_commands_service_instance._client.patch.return_value = restored_data

        result = await help_commands_service_instance.restore_help("deleted-topic")

        assert isinstance(result, HelpCommand)
        assert result.is_active is True


class TestHelpCommandsServiceSearch:
    """Test search and listing operations."""

    @pytest.mark.asyncio
    async def test_search_help_commands(self, help_commands_service_instance):
        """Test searching for help commands with filters."""
        filters = HelpCommandSearchFilters(
            name_contains='trading',
            category='rules',
            page=1,
            page_size=10
        )

        # Mock API response
        api_response = {
            'help_commands': [
                {
                    'id': 1,
                    'name': 'trading-rules',
                    'title': 'Trading Rules',
                    'content': 'Content',
                    'category': 'rules',
                    'created_by_discord_id': '123',
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'is_active': True,
                    'view_count': 100,
                    'display_order': 0
                }
            ],
            'total_count': 1,
            'page': 1,
            'page_size': 10,
            'total_pages': 1,
            'has_more': False
        }

        help_commands_service_instance._client.get.return_value = api_response

        result = await help_commands_service_instance.search_help_commands(filters)

        assert isinstance(result, HelpCommandSearchResult)
        assert len(result.help_commands) == 1
        assert result.total_count == 1
        assert result.help_commands[0].name == 'trading-rules'

    @pytest.mark.asyncio
    async def test_get_all_help_topics(self, help_commands_service_instance):
        """Test getting all help topics."""
        # Mock API response
        api_response = {
            'help_commands': [
                {
                    'id': i,
                    'name': f'topic-{i}',
                    'title': f'Topic {i}',
                    'content': f'Content {i}',
                    'category': 'rules' if i % 2 == 0 else 'guides',
                    'created_by_discord_id': '123',
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'is_active': True,
                    'view_count': i * 10,
                    'display_order': i
                }
                for i in range(1, 6)
            ],
            'total_count': 5,
            'page': 1,
            'page_size': 100,
            'total_pages': 1,
            'has_more': False
        }

        help_commands_service_instance._client.get.return_value = api_response

        result = await help_commands_service_instance.get_all_help_topics()

        assert isinstance(result, list)
        assert len(result) == 5
        assert all(isinstance(cmd, HelpCommand) for cmd in result)

    @pytest.mark.asyncio
    async def test_get_help_names_for_autocomplete(self, help_commands_service_instance):
        """Test getting help names for autocomplete."""
        # Mock API response
        api_response = {
            'results': [
                {
                    'name': 'trading-rules',
                    'title': 'Trading Rules',
                    'category': 'rules'
                },
                {
                    'name': 'trading-deadline',
                    'title': 'Trading Deadline',
                    'category': 'info'
                }
            ]
        }

        help_commands_service_instance._client.get.return_value = api_response

        result = await help_commands_service_instance.get_help_names_for_autocomplete(
            partial_name='trading',
            limit=25
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert 'trading-rules' in result
        assert 'trading-deadline' in result


class TestHelpCommandsServiceViewTracking:
    """Test view count tracking."""

    @pytest.mark.asyncio
    async def test_increment_view_count(self, help_commands_service_instance, sample_help_command):
        """Test incrementing view count."""
        # Mock the API patch call
        help_commands_service_instance._client.patch = AsyncMock()

        # Mock getting the updated help command
        updated_help = HelpCommand(
            id=sample_help_command.id,
            name=sample_help_command.name,
            title=sample_help_command.title,
            content=sample_help_command.content,
            category=sample_help_command.category,
            created_by_discord_id=sample_help_command.created_by_discord_id,
            created_at=sample_help_command.created_at,
            is_active=sample_help_command.is_active,
            view_count=sample_help_command.view_count + 1,
            display_order=sample_help_command.display_order
        )

        async def mock_get_help_by_name(name, include_inactive=False):
            return updated_help

        help_commands_service_instance.get_help_by_name = mock_get_help_by_name

        result = await help_commands_service_instance.increment_view_count("trading-rules")

        assert isinstance(result, HelpCommand)
        assert result.view_count == 101


class TestHelpCommandsServiceStatistics:
    """Test statistics gathering."""

    @pytest.mark.asyncio
    async def test_get_statistics(self, help_commands_service_instance):
        """Test getting help command statistics."""
        # Mock API response
        api_response = {
            'total_commands': 50,
            'active_commands': 45,
            'total_views': 5000,
            'most_viewed_command': {
                'id': 1,
                'name': 'popular-topic',
                'title': 'Popular Topic',
                'content': 'Content',
                'created_by_discord_id': '123',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'is_active': True,
                'view_count': 500,
                'display_order': 0
            },
            'recent_commands_count': 5
        }

        help_commands_service_instance._client.get.return_value = api_response

        result = await help_commands_service_instance.get_statistics()

        assert isinstance(result, HelpCommandStats)
        assert result.total_commands == 50
        assert result.active_commands == 45
        assert result.total_views == 5000
        assert result.most_viewed_command is not None
        assert result.most_viewed_command.name == 'popular-topic'
        assert result.recent_commands_count == 5


class TestHelpCommandsServiceErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_api_connection_error(self, help_commands_service_instance):
        """Test handling of API connection errors."""
        from exceptions import APIException, BotException

        # Mock the API client to raise an APIException
        help_commands_service_instance._client.get.side_effect = APIException("Connection error")

        with pytest.raises(BotException, match="Failed to retrieve help topic 'test'"):
            await help_commands_service_instance.get_help_by_name("test")

    @pytest.mark.asyncio
    async def test_empty_statistics_on_error(self, help_commands_service_instance):
        """Test that get_statistics returns empty stats on error."""
        # Mock the API client to raise an exception
        help_commands_service_instance._client.get.side_effect = Exception("API Error")

        result = await help_commands_service_instance.get_statistics()

        # Should return empty stats instead of raising
        assert isinstance(result, HelpCommandStats)
        assert result.total_commands == 0
        assert result.active_commands == 0
        assert result.total_views == 0
