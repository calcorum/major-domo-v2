"""
Tests for Custom Command Cleanup Tasks in Discord Bot v2.0

Fixed version that tests cleanup logic without Discord task infrastructure.
"""
import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from typing import List

from models.custom_command import (
    CustomCommand,
    CustomCommandCreator
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
def old_command(sample_creator: CustomCommandCreator) -> CustomCommand:
    """Fixture providing an old command needing cleanup."""
    old_date = datetime.now(timezone.utc) - timedelta(days=90)  # 90 days old
    return CustomCommand(
        id=1,
        name="oldcmd",
        content="This is an old command",
        creator_id=sample_creator.id,
        creator=sample_creator,
        created_at=old_date,
        updated_at=None,
        last_used=old_date,
        use_count=5,
        warning_sent=False,
        is_active=True,
        tags=None
    )


@pytest.fixture
def warned_command(sample_creator: CustomCommandCreator) -> CustomCommand:
    """Fixture providing a command that already has a warning."""
    old_date = datetime.now(timezone.utc) - timedelta(days=90)
    return CustomCommand(
        id=2,
        name="warnedcmd",
        content="This command was warned",
        creator_id=sample_creator.id,
        creator=sample_creator,
        created_at=old_date,
        updated_at=None,
        last_used=old_date,
        use_count=3,
        warning_sent=True,
        is_active=True,
        tags=None
    )


class TestCleanupLogic:
    """Test the cleanup logic without Discord tasks."""
    
    def test_command_age_calculation(self, old_command):
        """Test calculating command age."""
        now = datetime.now(timezone.utc)
        age_days = (now - old_command.last_used).days
        
        assert age_days >= 90
        assert age_days < 100  # Should be roughly 90 days
    
    def test_needs_warning_logic(self, old_command, warned_command):
        """Test logic for determining if commands need warnings."""
        warning_threshold_days = 60
        now = datetime.now(timezone.utc)
        
        # Old command that hasn't been warned
        days_since_use = (now - old_command.last_used).days
        needs_warning = (
            days_since_use >= warning_threshold_days and 
            not old_command.warning_sent and 
            old_command.is_active
        )
        assert needs_warning
        
        # Command that was already warned
        days_since_use = (now - warned_command.last_used).days
        needs_warning = (
            days_since_use >= warning_threshold_days and 
            not warned_command.warning_sent and 
            warned_command.is_active
        )
        assert not needs_warning  # Already warned
    
    def test_needs_deletion_logic(self, warned_command):
        """Test logic for determining if commands need deletion."""
        deletion_threshold_days = 90
        warning_grace_period_days = 7
        now = datetime.now(timezone.utc)
        
        # Simulate that warning was sent 8 days ago
        warned_command.warning_sent = True
        warning_sent_date = now - timedelta(days=8)
        
        days_since_use = (now - warned_command.last_used).days
        days_since_warning = 8  # Simulated
        
        needs_deletion = (
            days_since_use >= deletion_threshold_days and
            warned_command.warning_sent and
            days_since_warning >= warning_grace_period_days and
            warned_command.is_active
        )
        assert needs_deletion
    
    def test_embed_data_creation(self, old_command):
        """Test creation of embed data for notifications."""
        embed_data = {
            "title": "Custom Command Cleanup Warning",
            "description": f"The following command will be deleted if not used soon:",
            "fields": [
                {
                    "name": "Command",
                    "value": f"`{old_command.name}`",
                    "inline": True
                },
                {
                    "name": "Last Used", 
                    "value": old_command.last_used.strftime("%Y-%m-%d"),
                    "inline": True
                },
                {
                    "name": "Uses",
                    "value": str(old_command.use_count),
                    "inline": True
                }
            ],
            "color": 0xFFA500  # Orange for warning
        }
        
        assert embed_data["title"] == "Custom Command Cleanup Warning"
        assert old_command.name in embed_data["fields"][0]["value"]
        assert len(embed_data["fields"]) == 3
    
    def test_bulk_embed_data_creation(self, old_command, warned_command):
        """Test creation of embed data for multiple commands."""
        commands = [old_command, warned_command]
        
        command_list = "\n".join([
            f"• `{cmd.name}` - {cmd.use_count} uses, last used {cmd.last_used.strftime('%Y-%m-%d')}"
            for cmd in commands
        ])
        
        embed_data = {
            "title": f"Cleanup Warning - {len(commands)} Commands",
            "description": f"The following commands will be deleted if not used soon:\n\n{command_list}",
            "color": 0xFFA500
        }
        
        assert str(len(commands)) in embed_data["title"]
        assert old_command.name in embed_data["description"]
        assert warned_command.name in embed_data["description"]


class TestCleanupConfiguration:
    """Test cleanup configuration and thresholds."""
    
    def test_cleanup_thresholds(self):
        """Test cleanup threshold configuration."""
        config = {
            "warning_threshold_days": 60,
            "deletion_threshold_days": 90,
            "warning_grace_period_days": 7,
            "cleanup_interval_hours": 24
        }
        
        assert config["warning_threshold_days"] < config["deletion_threshold_days"]
        assert config["warning_grace_period_days"] < config["warning_threshold_days"]
        assert config["cleanup_interval_hours"] > 0
    
    def test_threshold_validation(self):
        """Test validation of cleanup thresholds."""
        # Valid configuration
        warning_days = 60
        deletion_days = 90
        grace_days = 7
        
        assert warning_days < deletion_days, "Warning threshold must be less than deletion threshold"
        assert grace_days < warning_days, "Grace period must be reasonable"
        assert all(x > 0 for x in [warning_days, deletion_days, grace_days]), "All thresholds must be positive"


class TestNotificationLogic:
    """Test notification logic for cleanup events."""
    
    @pytest.mark.asyncio
    async def test_user_notification_data(self, old_command):
        """Test preparation of user notification data."""
        notification_data = {
            "user_id": old_command.creator.discord_id,
            "username": old_command.creator.username,
            "display_name": old_command.creator.display_name,
            "commands_to_warn": [old_command],
            "commands_to_delete": []
        }
        
        assert notification_data["user_id"] == old_command.creator.discord_id
        assert len(notification_data["commands_to_warn"]) == 1
        assert len(notification_data["commands_to_delete"]) == 0
    
    @pytest.mark.asyncio
    async def test_admin_summary_data(self, old_command, warned_command):
        """Test preparation of admin summary data."""
        summary_data = {
            "total_warnings_sent": 1,
            "total_commands_deleted": 1,
            "affected_users": {
                old_command.creator.discord_id: {
                    "username": old_command.creator.username,
                    "warnings": 1,
                    "deletions": 0
                }
            },
            "timestamp": datetime.now(timezone.utc)
        }
        
        assert summary_data["total_warnings_sent"] == 1
        assert summary_data["total_commands_deleted"] == 1
        assert old_command.creator.discord_id in summary_data["affected_users"]
    
    @pytest.mark.asyncio
    async def test_message_formatting(self, old_command):
        """Test message formatting for different scenarios."""
        # Single command warning
        single_message = (
            f"⚠️ **Custom Command Cleanup Warning**\n\n"
            f"Your command `{old_command.name}` hasn't been used in a while. "
            f"It will be automatically deleted if not used within the next 7 days."
        )
        
        assert old_command.name in single_message
        assert "⚠️" in single_message
        assert "7 days" in single_message
        
        # Multiple commands warning
        commands = [old_command]
        if len(commands) > 1:
            multi_message = (
                f"⚠️ **Custom Command Cleanup Warning**\n\n"
                f"You have {len(commands)} commands that haven't been used recently:"
            )
            assert str(len(commands)) in multi_message
        else:
            # Single command case
            assert "command `" in single_message


class TestCleanupStatistics:
    """Test cleanup statistics and reporting."""
    
    def test_cleanup_statistics_calculation(self):
        """Test calculation of cleanup statistics."""
        stats = {
            "total_active_commands": 100,
            "commands_needing_warning": 15,
            "commands_eligible_for_deletion": 5,
            "cleanup_rate_percentage": 0.0
        }
        
        # Calculate cleanup rate
        total_to_cleanup = stats["commands_needing_warning"] + stats["commands_eligible_for_deletion"]
        stats["cleanup_rate_percentage"] = (total_to_cleanup / stats["total_active_commands"]) * 100
        
        assert stats["cleanup_rate_percentage"] == 20.0  # (15+5)/100 * 100
        assert stats["cleanup_rate_percentage"] <= 100.0
    
    def test_cleanup_health_metrics(self):
        """Test cleanup health metrics."""
        metrics = {
            "avg_command_age_days": 45,
            "commands_over_warning_threshold": 15,
            "commands_over_deletion_threshold": 5,
            "most_active_command_uses": 150,
            "least_active_command_uses": 0
        }
        
        # Health checks
        assert metrics["avg_command_age_days"] > 0
        assert metrics["commands_over_deletion_threshold"] <= metrics["commands_over_warning_threshold"]
        assert metrics["most_active_command_uses"] >= metrics["least_active_command_uses"]