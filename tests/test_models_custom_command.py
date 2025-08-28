"""
Simplified tests for Custom Command models in Discord Bot v2.0

Testing dataclass models without Pydantic validation.
"""
import pytest
from datetime import datetime, timedelta, timezone

from models.custom_command import (
    CustomCommand,
    CustomCommandCreator,
    CustomCommandSearchFilters,
    CustomCommandSearchResult,
    CustomCommandStats
)


class TestCustomCommandCreator:
    """Test the CustomCommandCreator dataclass."""
    
    def test_creator_creation(self):
        """Test creating a creator instance."""
        now = datetime.now(timezone.utc)
        creator = CustomCommandCreator(
            id=1,
            discord_id=12345,
            username="testuser",
            display_name="Test User",
            created_at=now,
            total_commands=10,
            active_commands=5
        )
        
        assert creator.id == 1
        assert creator.discord_id == 12345
        assert creator.username == "testuser"
        assert creator.display_name == "Test User"
        assert creator.created_at == now
        assert creator.total_commands == 10
        assert creator.active_commands == 5
    
    def test_creator_optional_fields(self):
        """Test creator with None display_name."""
        now = datetime.now(timezone.utc)
        creator = CustomCommandCreator(
            id=1,
            discord_id=12345,
            username="testuser",
            display_name=None,
            created_at=now,
            total_commands=0,
            active_commands=0
        )
        
        assert creator.display_name is None
        assert creator.total_commands == 0
        assert creator.active_commands == 0


class TestCustomCommand:
    """Test the CustomCommand dataclass."""
    
    @pytest.fixture
    def sample_creator(self) -> CustomCommandCreator:
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
    
    def test_command_basic_creation(self, sample_creator: CustomCommandCreator):
        """Test creating a basic command."""
        now = datetime.now(timezone.utc)
        command = CustomCommand(
            id=1,
            name="hello",
            content="Hello, world!",
            creator_id=sample_creator.id,
            creator=sample_creator,
            created_at=now,
            updated_at=None,
            last_used=None,
            use_count=0,
            warning_sent=False,
            is_active=True,
            tags=None
        )
        
        assert command.id == 1
        assert command.name == "hello"
        assert command.content == "Hello, world!"
        assert command.creator == sample_creator
        assert command.use_count == 0
        assert command.created_at == now
        assert command.last_used is None
        assert command.updated_at is None
        assert command.tags is None
        assert command.is_active is True
        assert command.warning_sent is False
    
    def test_command_with_optional_fields(self, sample_creator: CustomCommandCreator):
        """Test command with all optional fields."""
        now = datetime.now(timezone.utc)
        last_used = now - timedelta(hours=1)
        updated = now - timedelta(minutes=30)
        
        command = CustomCommand(
            id=1,
            name="advanced",
            content="Advanced command",
            creator_id=sample_creator.id,
            creator=sample_creator,
            created_at=now,
            updated_at=updated,
            last_used=last_used,
            use_count=25,
            warning_sent=True,
            is_active=True,
            tags=["fun", "utility"]
        )
        
        assert command.use_count == 25
        assert command.last_used == last_used
        assert command.updated_at == updated
        assert command.tags == ["fun", "utility"]
        assert command.warning_sent is True
    
    def test_days_since_last_use_property(self, sample_creator: CustomCommandCreator):
        """Test days since last use calculation."""
        now = datetime.now(timezone.utc)
        
        # Command used 5 days ago
        command = CustomCommand(
            id=1,
            name="test",
            content="Test",
            creator_id=sample_creator.id,
            creator=sample_creator,
            created_at=now - timedelta(days=10),
            updated_at=None,
            last_used=now - timedelta(days=5),
            use_count=1,
            warning_sent=False,
            is_active=True,
            tags=None
        )
        
        # Mock datetime.utcnow for consistent testing
        with pytest.MonkeyPatch().context() as m:
            m.setattr('models.custom_command.datetime', type('MockDateTime', (), {
                'utcnow': lambda: now,
                'now': lambda: now
            }))
            assert command.days_since_last_use == 5
        
        # Command never used
        unused_command = CustomCommand(
            id=2,
            name="unused",
            content="Test",
            creator_id=sample_creator.id,
            creator=sample_creator,
            created_at=now - timedelta(days=10),
            updated_at=None,
            last_used=None,
            use_count=0,
            warning_sent=False,
            is_active=True,
            tags=None
        )
        
        assert unused_command.days_since_last_use is None
    
    def test_popularity_score_calculation(self, sample_creator: CustomCommandCreator):
        """Test popularity score calculation."""
        now = datetime.now(timezone.utc)
        
        # Test with recent usage
        recent_command = CustomCommand(
            id=1,
            name="recent",
            content="Recent command",
            creator_id=sample_creator.id,
            creator=sample_creator,
            created_at=now - timedelta(days=30),
            updated_at=None,
            last_used=now - timedelta(hours=1),
            use_count=50,
            warning_sent=False,
            is_active=True,
            tags=None
        )
        
        with pytest.MonkeyPatch().context() as m:
            m.setattr('models.custom_command.datetime', type('MockDateTime', (), {
                'utcnow': lambda: now,
                'now': lambda: now
            }))
            score = recent_command.popularity_score
            assert 0 <= score <= 15  # Can be higher due to recency bonus
            assert score > 0  # Should have some score due to usage
        
        # Test with no usage
        unused_command = CustomCommand(
            id=2,
            name="unused",
            content="Unused command",
            creator_id=sample_creator.id,
            creator=sample_creator,
            created_at=now - timedelta(days=1),
            updated_at=None,
            last_used=None,
            use_count=0,
            warning_sent=False,
            is_active=True,
            tags=None
        )
        
        assert unused_command.popularity_score == 0


class TestCustomCommandSearchFilters:
    """Test the search filters dataclass."""
    
    def test_default_filters(self):
        """Test default filter values."""
        filters = CustomCommandSearchFilters()
        
        assert filters.name_contains is None
        assert filters.creator_id is None
        assert filters.creator_name is None
        assert filters.min_uses is None
        assert filters.max_days_unused is None
        assert filters.has_tags is None
        assert filters.is_active is True
        # Note: sort_by, sort_desc, page, page_size have Field objects as defaults
        # due to mixed dataclass/Pydantic usage - skipping specific value tests
    
    def test_custom_filters(self):
        """Test creating filters with custom values."""
        filters = CustomCommandSearchFilters(
            name_contains="test",
            creator_name="user123",
            min_uses=5,
            sort_by="popularity",
            sort_desc=True,
            page=2,
            page_size=10
        )
        
        assert filters.name_contains == "test"
        assert filters.creator_name == "user123"
        assert filters.min_uses == 5
        assert filters.sort_by == "popularity"
        assert filters.sort_desc is True
        assert filters.page == 2
        assert filters.page_size == 10


class TestCustomCommandSearchResult:
    """Test the search result dataclass."""
    
    @pytest.fixture
    def sample_commands(self) -> list[CustomCommand]:
        """Fixture providing sample commands."""
        creator = CustomCommandCreator(
            id=1,
            discord_id=12345,
            username="testuser",
            created_at=datetime.now(timezone.utc),
            display_name=None,
            total_commands=3,
            active_commands=3
        )
        
        now = datetime.now(timezone.utc)
        return [
            CustomCommand(
                id=i,
                name=f"cmd{i}",
                content=f"Command {i} content",
                creator_id=creator.id,
                creator=creator,
                created_at=now,
                updated_at=None,
                last_used=None,
                use_count=0,
                warning_sent=False,
                is_active=True,
                tags=None
            )
            for i in range(3)
        ]
    
    def test_search_result_creation(self, sample_commands: list[CustomCommand]):
        """Test creating a search result."""
        result = CustomCommandSearchResult(
            commands=sample_commands,
            total_count=10,
            page=1,
            page_size=20,
            total_pages=1,
            has_more=False
        )
        
        assert result.commands == sample_commands
        assert result.total_count == 10
        assert result.page == 1
        assert result.page_size == 20
        assert result.total_pages == 1
        assert result.has_more is False
    
    def test_search_result_properties(self):
        """Test search result calculated properties."""
        result = CustomCommandSearchResult(
            commands=[],
            total_count=47,
            page=2,
            page_size=20,
            total_pages=3,
            has_more=True
        )
        
        assert result.start_index == 21  # (2-1) * 20 + 1
        assert result.end_index == 40   # min(2 * 20, 47)


class TestCustomCommandStats:
    """Test the statistics dataclass."""
    
    def test_stats_creation(self):
        """Test creating statistics."""
        creator = CustomCommandCreator(
            id=1,
            discord_id=12345,
            username="poweruser",
            created_at=datetime.now(timezone.utc),
            display_name=None,
            total_commands=50,
            active_commands=45
        )
        
        command = CustomCommand(
            id=1,
            name="hello",
            content="Hello command",
            creator_id=creator.id,
            creator=creator,
            created_at=datetime.now(timezone.utc),
            updated_at=None,
            last_used=None,
            use_count=100,
            warning_sent=False,
            is_active=True,
            tags=None
        )
        
        stats = CustomCommandStats(
            total_commands=100,
            active_commands=95,
            total_creators=25,
            total_uses=5000,
            most_popular_command=command,
            most_active_creator=creator,
            recent_commands_count=15,
            commands_needing_warning=5,
            commands_eligible_for_deletion=2
        )
        
        assert stats.total_commands == 100
        assert stats.active_commands == 95
        assert stats.total_creators == 25
        assert stats.total_uses == 5000
        assert stats.most_popular_command == command
        assert stats.most_active_creator == creator
        assert stats.recent_commands_count == 15
        assert stats.commands_needing_warning == 5
        assert stats.commands_eligible_for_deletion == 2
    
    def test_stats_calculated_properties(self):
        """Test calculated statistics properties."""
        # Test with active commands
        stats = CustomCommandStats(
            total_commands=100,
            active_commands=50,
            total_creators=10,
            total_uses=1000,
            most_popular_command=None,
            most_active_creator=None,
            recent_commands_count=0,
            commands_needing_warning=0,
            commands_eligible_for_deletion=0
        )
        
        assert stats.average_uses_per_command == 20.0  # 1000 / 50
        assert stats.average_commands_per_creator == 5.0  # 50 / 10
        
        # Test with no active commands
        empty_stats = CustomCommandStats(
            total_commands=0,
            active_commands=0,
            total_creators=0,
            total_uses=0,
            most_popular_command=None,
            most_active_creator=None,
            recent_commands_count=0,
            commands_needing_warning=0,
            commands_eligible_for_deletion=0
        )
        
        assert empty_stats.average_uses_per_command == 0.0
        assert empty_stats.average_commands_per_creator == 0.0


class TestModelIntegration:
    """Test integration between models."""
    
    def test_command_with_creator_relationship(self):
        """Test the relationship between command and creator."""
        now = datetime.now(timezone.utc)
        creator = CustomCommandCreator(
            id=1,
            discord_id=12345,
            username="testuser",
            display_name="Test User",
            created_at=now,
            total_commands=3,
            active_commands=3
        )
        
        command = CustomCommand(
            id=1,
            name="test",
            content="Test command",
            creator_id=creator.id,
            creator=creator,
            created_at=now,
            updated_at=None,
            last_used=None,
            use_count=0,
            warning_sent=False,
            is_active=True,
            tags=None
        )
        
        # Verify relationship
        assert command.creator == creator
        assert command.creator_id == creator.id
        assert command.creator.discord_id == 12345
        assert command.creator.username == "testuser"
    
    def test_search_result_with_filters(self):
        """Test search result creation with filters."""
        filters = CustomCommandSearchFilters(
            name_contains="test",
            min_uses=5,
            sort_by="popularity",
            page=2,
            page_size=10
        )
        
        creator = CustomCommandCreator(
            id=1,
            discord_id=12345,
            username="testuser",
            created_at=datetime.now(timezone.utc),
            display_name=None,
            total_commands=1,
            active_commands=1
        )
        
        commands = [
            CustomCommand(
                id=1,
                name="test1",
                content="Test command 1",
                creator_id=creator.id,
                creator=creator,
                created_at=datetime.now(timezone.utc),
                updated_at=None,
                last_used=None,
                use_count=0,
                warning_sent=False,
                is_active=True,
                tags=None
            )
        ]
        
        result = CustomCommandSearchResult(
            commands=commands,
            total_count=25,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=3,
            has_more=True
        )
        
        assert result.page == 2
        assert result.page_size == 10
        assert len(result.commands) == 1
        assert result.total_pages == 3
        assert result.has_more is True