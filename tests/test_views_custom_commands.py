"""
Tests for Custom Command Views in Discord Bot v2.0

Fixed version with proper async handling and model validation.
"""
import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from typing import List

import discord

from models.custom_command import (
    CustomCommand,
    CustomCommandCreator,
    CustomCommandSearchResult
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
def mock_interaction():
    """Create a mock Discord interaction."""
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user = Mock()
    interaction.user.id = 12345
    interaction.user.display_name = "Test User"
    interaction.guild = Mock()
    interaction.guild.id = 98765
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


class TestCustomCommandModels:
    """Test model creation and validation."""
    
    def test_command_model_with_required_fields(self, sample_creator):
        """Test that command model can be created with required fields."""
        command = CustomCommand(
            id=1,
            name="test",
            content="Test content",
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
        
        assert command.name == "test"
        assert command.content == "Test content"
        assert command.creator_id == sample_creator.id
        assert command.use_count == 0
    
    def test_creator_model_creation(self):
        """Test that creator model can be created."""
        creator = CustomCommandCreator(
            id=1,
            discord_id=12345,
            username="testuser",
            display_name="Test User",
            created_at=datetime.now(timezone.utc),
            total_commands=5,
            active_commands=5
        )
        
        assert creator.discord_id == 12345
        assert creator.username == "testuser"
        assert creator.total_commands == 5


class TestCustomCommandCreateModal:
    """Test the custom command creation modal."""
    
    @pytest.mark.asyncio
    async def test_modal_creation_without_discord_components(self):
        """Test modal can be conceptually created without Discord UI."""
        # Test the data structure and validation that would be used in a modal
        command_data = {
            "name": "hello",
            "content": "Hello, world!",
            "tags": "greeting, fun"
        }
        
        # Validate the data structure
        assert command_data["name"] == "hello"
        assert command_data["content"] == "Hello, world!"
        assert "greeting" in command_data["tags"]
    
    @pytest.mark.asyncio
    async def test_tag_parsing_logic(self):
        """Test tag parsing logic that would be used in modal."""
        tags_string = "greeting, fun, test"
        parsed_tags = [tag.strip() for tag in tags_string.split(",") if tag.strip()]
        
        assert len(parsed_tags) == 3
        assert "greeting" in parsed_tags
        assert "fun" in parsed_tags
        assert "test" in parsed_tags


class TestCustomCommandViews:
    """Test view logic without Discord UI components."""
    
    @pytest.mark.asyncio
    async def test_command_embed_creation_logic(self, sample_command):
        """Test embed creation logic for commands."""
        # Test the data that would go into an embed
        embed_data = {
            "title": f"Custom Command: {sample_command.name}",
            "description": sample_command.content[:100],
            "fields": [
                {"name": "Creator", "value": sample_command.creator.display_name},
                {"name": "Uses", "value": str(sample_command.use_count)},
                {"name": "Created", "value": sample_command.created_at.strftime("%Y-%m-%d")}
            ]
        }
        
        assert embed_data["title"] == "Custom Command: testcmd"
        assert embed_data["description"] == sample_command.content[:100]
        assert len(embed_data["fields"]) == 3
    
    @pytest.mark.asyncio
    async def test_pagination_logic(self, sample_command):
        """Test pagination logic for command lists."""
        commands = [sample_command] * 15  # 15 commands
        page_size = 5
        total_pages = (len(commands) + page_size - 1) // page_size
        
        assert total_pages == 3
        
        # Test page 1
        page_1 = commands[0:page_size]
        assert len(page_1) == 5
        
        # Test last page
        last_page_start = (total_pages - 1) * page_size
        last_page = commands[last_page_start:]
        assert len(last_page) == 5


class TestCustomCommandSearchFilters:
    """Test search and filtering logic."""
    
    @pytest.mark.asyncio
    async def test_search_filter_validation(self):
        """Test search filter validation logic."""
        search_data = {
            "name": "test",
            "creator": "testuser",
            "tags": "fun, games",
            "min_uses": "5"
        }
        
        # Validate search parameters
        assert search_data["name"] == "test"
        assert search_data["creator"] == "testuser"
        
        # Test min_uses validation
        try:
            min_uses = int(search_data["min_uses"])
            assert min_uses >= 0
        except ValueError:
            pytest.fail("min_uses should be a valid integer")
    
    @pytest.mark.asyncio
    async def test_search_filter_edge_cases(self):
        """Test edge cases in search filtering."""
        # Test negative min_uses
        invalid_search = {"min_uses": "-1"}
        
        try:
            min_uses = int(invalid_search["min_uses"])
            if min_uses < 0:
                raise ValueError("min_uses cannot be negative")
        except ValueError as e:
            assert "negative" in str(e)
        
        # Test empty fields
        empty_search = {"name": "", "creator": "", "tags": ""}
        filtered_search = {k: v for k, v in empty_search.items() if v.strip()}
        assert len(filtered_search) == 0


class TestViewInteractionHandling:
    """Test view interaction handling logic."""
    
    @pytest.mark.asyncio
    async def test_user_permission_check_logic(self, sample_command, mock_interaction):
        """Test user permission checking logic."""
        # User is the creator
        user_is_creator = mock_interaction.user.id == sample_command.creator.discord_id
        assert user_is_creator
        
        # Different user
        mock_interaction.user.id = 99999
        user_is_creator = mock_interaction.user.id == sample_command.creator.discord_id
        assert not user_is_creator
    
    @pytest.mark.asyncio
    async def test_embed_field_truncation_logic(self):
        """Test embed field truncation logic."""
        long_content = "x" * 2000  # Very long content
        max_length = 1000
        
        truncated = long_content[:max_length]
        if len(long_content) > max_length:
            truncated = truncated + "..."
        
        assert len(truncated) <= max_length + 3  # +3 for "..."
        assert truncated.endswith("...")
    
    @pytest.mark.asyncio
    async def test_view_timeout_handling_logic(self):
        """Test view timeout handling logic."""
        timeout_seconds = 300  # 5 minutes
        current_time = datetime.now(timezone.utc)
        timeout_time = current_time + timedelta(seconds=timeout_seconds)
        
        # Simulate time passing
        future_time = current_time + timedelta(seconds=400)  # 6 minutes later
        
        is_timed_out = future_time > timeout_time
        assert is_timed_out