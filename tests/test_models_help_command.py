"""
Tests for Help Command models

Validates model creation, validation, and business logic.
"""
import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from models.help_command import (
    HelpCommand,
    HelpCommandSearchFilters,
    HelpCommandSearchResult,
    HelpCommandStats
)


class TestHelpCommandModel:
    """Test HelpCommand model functionality."""

    def test_help_command_creation_minimal(self):
        """Test help command creation with minimal required fields."""
        help_cmd = HelpCommand(
            id=1,
            name='test-topic',
            title='Test Topic',
            content='This is test content',
            created_by_discord_id=123456789,
            created_at=datetime.now()
        )

        assert help_cmd.id == 1
        assert help_cmd.name == 'test-topic'
        assert help_cmd.title == 'Test Topic'
        assert help_cmd.content == 'This is test content'
        assert help_cmd.created_by_discord_id == 123456789
        assert help_cmd.is_active is True
        assert help_cmd.view_count == 0

    def test_help_command_creation_with_optional_fields(self):
        """Test help command creation with all optional fields."""
        now = datetime.now()
        help_cmd = HelpCommand(
            id=2,
            name='trading-rules',
            title='Trading Rules & Guidelines',
            content='Complete trading rules...',
            category='rules',
            created_by_discord_id=123456789,
            created_at=now,
            updated_at=now,
            last_modified_by=987654321,
            is_active=True,
            view_count=100,
            display_order=10
        )

        assert help_cmd.category == 'rules'
        assert help_cmd.updated_at == now
        assert help_cmd.last_modified_by == 987654321
        assert help_cmd.view_count == 100
        assert help_cmd.display_order == 10

    def test_help_command_name_validation(self):
        """Test help command name validation."""
        base_data = {
            'id': 3,
            'title': 'Test',
            'content': 'Content',
            'created_by_discord_id': 123,
            'created_at': datetime.now()
        }

        # Valid names
        valid_names = ['test', 'test-topic', 'test_topic', 'test123', 'abc']
        for name in valid_names:
            help_cmd = HelpCommand(name=name, **base_data)
            assert help_cmd.name == name.lower()

        # Invalid names - too short
        with pytest.raises(ValidationError):
            HelpCommand(name='a', **base_data)

        # Invalid names - too long
        with pytest.raises(ValidationError):
            HelpCommand(name='a' * 33, **base_data)

        # Invalid names - special characters
        with pytest.raises(ValidationError):
            HelpCommand(name='test@topic', **base_data)

        with pytest.raises(ValidationError):
            HelpCommand(name='test topic', **base_data)

    def test_help_command_title_validation(self):
        """Test help command title validation."""
        base_data = {
            'id': 4,
            'name': 'test',
            'content': 'Content',
            'created_by_discord_id': 123,
            'created_at': datetime.now()
        }

        # Valid title
        help_cmd = HelpCommand(title='Test Topic', **base_data)
        assert help_cmd.title == 'Test Topic'

        # Empty title
        with pytest.raises(ValidationError):
            HelpCommand(title='', **base_data)

        # Title too long
        with pytest.raises(ValidationError):
            HelpCommand(title='a' * 201, **base_data)

    def test_help_command_content_validation(self):
        """Test help command content validation."""
        base_data = {
            'id': 5,
            'name': 'test',
            'title': 'Test',
            'created_by_discord_id': 123,
            'created_at': datetime.now()
        }

        # Valid content
        help_cmd = HelpCommand(content='Test content', **base_data)
        assert help_cmd.content == 'Test content'

        # Empty content
        with pytest.raises(ValidationError):
            HelpCommand(content='', **base_data)

        # Content too long
        with pytest.raises(ValidationError):
            HelpCommand(content='a' * 4001, **base_data)

    def test_help_command_category_validation(self):
        """Test help command category validation."""
        base_data = {
            'id': 6,
            'name': 'test',
            'title': 'Test',
            'content': 'Content',
            'created_by_discord_id': 123,
            'created_at': datetime.now()
        }

        # Valid categories
        valid_categories = ['rules', 'guides', 'resources', 'info', 'faq']
        for category in valid_categories:
            help_cmd = HelpCommand(category=category, **base_data)
            assert help_cmd.category == category.lower()

        # None category
        help_cmd = HelpCommand(category=None, **base_data)
        assert help_cmd.category is None

        # Invalid category - special characters
        with pytest.raises(ValidationError):
            HelpCommand(category='test@category', **base_data)

    def test_help_command_is_deleted_property(self):
        """Test is_deleted property."""
        active = HelpCommand(
            id=7,
            name='active',
            title='Active Topic',
            content='Content',
            created_by_discord_id=123,
            created_at=datetime.now(),
            is_active=True
        )

        deleted = HelpCommand(
            id=8,
            name='deleted',
            title='Deleted Topic',
            content='Content',
            created_by_discord_id=123,
            created_at=datetime.now(),
            is_active=False
        )

        assert active.is_deleted is False
        assert deleted.is_deleted is True

    def test_help_command_days_since_update(self):
        """Test days_since_update property."""
        # No updates
        no_update = HelpCommand(
            id=9,
            name='test',
            title='Test',
            content='Content',
            created_by_discord_id=123,
            created_at=datetime.now(),
            updated_at=None
        )
        assert no_update.days_since_update is None

        # Recent update
        recent = HelpCommand(
            id=10,
            name='test',
            title='Test',
            content='Content',
            created_by_discord_id=123,
            created_at=datetime.now(),
            updated_at=datetime.now() - timedelta(days=5)
        )
        assert recent.days_since_update == 5

    def test_help_command_days_since_creation(self):
        """Test days_since_creation property."""
        old = HelpCommand(
            id=11,
            name='test',
            title='Test',
            content='Content',
            created_by_discord_id=123,
            created_at=datetime.now() - timedelta(days=30)
        )
        assert old.days_since_creation == 30

    def test_help_command_popularity_score(self):
        """Test popularity_score property."""
        # No views
        no_views = HelpCommand(
            id=12,
            name='test',
            title='Test',
            content='Content',
            created_by_discord_id=123,
            created_at=datetime.now(),
            view_count=0
        )
        assert no_views.popularity_score == 0.0

        # New topic with views
        new_popular = HelpCommand(
            id=13,
            name='test',
            title='Test',
            content='Content',
            created_by_discord_id=123,
            created_at=datetime.now() - timedelta(days=5),
            view_count=50
        )
        score = new_popular.popularity_score
        assert score > 5.0  # Base score (5.0) with new topic bonus (1.5x)

        # Old topic with views
        old_popular = HelpCommand(
            id=14,
            name='test',
            title='Test',
            content='Content',
            created_by_discord_id=123,
            created_at=datetime.now() - timedelta(days=100),
            view_count=50
        )
        old_score = old_popular.popularity_score
        assert old_score < new_popular.popularity_score  # Older topics get penalty


class TestHelpCommandSearchFilters:
    """Test HelpCommandSearchFilters model."""

    def test_search_filters_defaults(self):
        """Test search filters with default values."""
        filters = HelpCommandSearchFilters()

        assert filters.name_contains is None
        assert filters.category is None
        assert filters.is_active is True
        assert filters.sort_by == 'name'
        assert filters.sort_desc is False
        assert filters.page == 1
        assert filters.page_size == 25

    def test_search_filters_custom_values(self):
        """Test search filters with custom values."""
        filters = HelpCommandSearchFilters(
            name_contains='trading',
            category='rules',
            is_active=False,
            sort_by='view_count',
            sort_desc=True,
            page=2,
            page_size=50
        )

        assert filters.name_contains == 'trading'
        assert filters.category == 'rules'
        assert filters.is_active is False
        assert filters.sort_by == 'view_count'
        assert filters.sort_desc is True
        assert filters.page == 2
        assert filters.page_size == 50

    def test_search_filters_sort_by_validation(self):
        """Test sort_by field validation."""
        # Valid sort fields
        valid_sorts = ['name', 'title', 'category', 'created_at', 'updated_at', 'view_count', 'display_order']
        for sort_field in valid_sorts:
            filters = HelpCommandSearchFilters(sort_by=sort_field)
            assert filters.sort_by == sort_field

        # Invalid sort field
        with pytest.raises(ValidationError):
            HelpCommandSearchFilters(sort_by='invalid_field')

    def test_search_filters_page_validation(self):
        """Test page number validation."""
        # Valid page numbers
        filters = HelpCommandSearchFilters(page=1)
        assert filters.page == 1

        filters = HelpCommandSearchFilters(page=100)
        assert filters.page == 100

        # Invalid page numbers
        with pytest.raises(ValidationError):
            HelpCommandSearchFilters(page=0)

        with pytest.raises(ValidationError):
            HelpCommandSearchFilters(page=-1)

    def test_search_filters_page_size_validation(self):
        """Test page size validation."""
        # Valid page sizes
        filters = HelpCommandSearchFilters(page_size=1)
        assert filters.page_size == 1

        filters = HelpCommandSearchFilters(page_size=100)
        assert filters.page_size == 100

        # Invalid page sizes
        with pytest.raises(ValidationError):
            HelpCommandSearchFilters(page_size=0)

        with pytest.raises(ValidationError):
            HelpCommandSearchFilters(page_size=101)


class TestHelpCommandSearchResult:
    """Test HelpCommandSearchResult model."""

    def test_search_result_creation(self):
        """Test search result creation."""
        help_commands = [
            HelpCommand(
                id=i,
                name=f'topic-{i}',
                title=f'Topic {i}',
                content=f'Content {i}',
                created_by_discord_id=123,
                created_at=datetime.now()
            )
            for i in range(1, 11)
        ]

        result = HelpCommandSearchResult(
            help_commands=help_commands,
            total_count=50,
            page=1,
            page_size=10,
            total_pages=5,
            has_more=True
        )

        assert len(result.help_commands) == 10
        assert result.total_count == 50
        assert result.page == 1
        assert result.page_size == 10
        assert result.total_pages == 5
        assert result.has_more is True

    def test_search_result_start_index(self):
        """Test start_index property."""
        result = HelpCommandSearchResult(
            help_commands=[],
            total_count=100,
            page=3,
            page_size=25,
            total_pages=4,
            has_more=True
        )

        assert result.start_index == 51  # (3-1) * 25 + 1

    def test_search_result_end_index(self):
        """Test end_index property."""
        # Last page with remaining items
        result = HelpCommandSearchResult(
            help_commands=[],
            total_count=55,
            page=3,
            page_size=25,
            total_pages=3,
            has_more=False
        )

        assert result.end_index == 55  # min(3 * 25, 55)

        # Full page
        result = HelpCommandSearchResult(
            help_commands=[],
            total_count=100,
            page=2,
            page_size=25,
            total_pages=4,
            has_more=True
        )

        assert result.end_index == 50  # min(2 * 25, 100)


class TestHelpCommandStats:
    """Test HelpCommandStats model."""

    def test_stats_creation(self):
        """Test stats creation."""
        stats = HelpCommandStats(
            total_commands=50,
            active_commands=45,
            total_views=1000,
            most_viewed_command=None,
            recent_commands_count=5
        )

        assert stats.total_commands == 50
        assert stats.active_commands == 45
        assert stats.total_views == 1000
        assert stats.most_viewed_command is None
        assert stats.recent_commands_count == 5

    def test_stats_with_most_viewed(self):
        """Test stats with most viewed command."""
        most_viewed = HelpCommand(
            id=1,
            name='popular-topic',
            title='Popular Topic',
            content='Content',
            created_by_discord_id=123,
            created_at=datetime.now(),
            view_count=500
        )

        stats = HelpCommandStats(
            total_commands=50,
            active_commands=45,
            total_views=1000,
            most_viewed_command=most_viewed,
            recent_commands_count=5
        )

        assert stats.most_viewed_command is not None
        assert stats.most_viewed_command.name == 'popular-topic'
        assert stats.most_viewed_command.view_count == 500

    def test_stats_average_views_per_command(self):
        """Test average_views_per_command property."""
        # Normal case
        stats = HelpCommandStats(
            total_commands=50,
            active_commands=40,
            total_views=800,
            most_viewed_command=None,
            recent_commands_count=5
        )

        assert stats.average_views_per_command == 20.0  # 800 / 40

        # No active commands
        stats = HelpCommandStats(
            total_commands=10,
            active_commands=0,
            total_views=0,
            most_viewed_command=None,
            recent_commands_count=0
        )

        assert stats.average_views_per_command == 0.0


class TestHelpCommandFromAPIData:
    """Test creating HelpCommand from API data."""

    def test_from_api_data_complete(self):
        """Test from_api_data with complete data."""
        api_data = {
            'id': 1,
            'name': 'trading-rules',
            'title': 'Trading Rules & Guidelines',
            'content': 'Complete trading rules...',
            'category': 'rules',
            'created_by_discord_id': 123456789,
            'created_at': '2025-01-01T12:00:00',
            'updated_at': '2025-01-10T15:30:00',
            'last_modified_by': 987654321,
            'is_active': True,
            'view_count': 100,
            'display_order': 10
        }

        help_cmd = HelpCommand.from_api_data(api_data)

        assert help_cmd.id == 1
        assert help_cmd.name == 'trading-rules'
        assert help_cmd.title == 'Trading Rules & Guidelines'
        assert help_cmd.content == 'Complete trading rules...'
        assert help_cmd.category == 'rules'
        assert help_cmd.view_count == 100

    def test_from_api_data_minimal(self):
        """Test from_api_data with minimal required data."""
        api_data = {
            'id': 2,
            'name': 'simple-topic',
            'title': 'Simple Topic',
            'content': 'Simple content',
            'created_by_discord_id': 123456789,
            'created_at': '2025-01-01T12:00:00'
        }

        help_cmd = HelpCommand.from_api_data(api_data)

        assert help_cmd.id == 2
        assert help_cmd.name == 'simple-topic'
        assert help_cmd.category is None
        assert help_cmd.updated_at is None
        assert help_cmd.view_count == 0
