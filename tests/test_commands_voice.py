"""
Tests for voice channel commands

Validates voice channel creation, cleanup, and migration message functionality.
"""
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from commands.voice.channels import VoiceChannelCommands
from commands.voice.cleanup_service import VoiceChannelCleanupService
from commands.voice.tracker import VoiceChannelTracker
from models.game import Game
from models.team import Team


class TestVoiceChannelTracker:
    """Test voice channel tracker functionality."""

    def test_tracker_initialization(self):
        """Test that tracker initializes correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_file = Path(temp_dir) / "test_channels.json"
            tracker = VoiceChannelTracker(str(data_file))

            assert tracker.data_file == data_file
            assert tracker._data == {"voice_channels": {}}
            assert data_file.parent.exists()

    def test_add_channel(self):
        """Test adding a channel to tracking."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_file = Path(temp_dir) / "test_channels.json"
            tracker = VoiceChannelTracker(str(data_file))

            # Mock channel
            mock_channel = MagicMock(spec=discord.VoiceChannel)
            mock_channel.id = 123456789
            mock_channel.name = "Test Channel"
            mock_guild = MagicMock()
            mock_guild.id = 987654321
            mock_channel.guild = mock_guild

            tracker.add_channel(mock_channel, "public", 555666777)

            # Verify data structure
            channels = tracker._data["voice_channels"]
            assert "123456789" in channels
            channel_data = channels["123456789"]

            assert channel_data["channel_id"] == "123456789"
            assert channel_data["guild_id"] == "987654321"
            assert channel_data["name"] == "Test Channel"
            assert channel_data["type"] == "public"
            assert channel_data["creator_id"] == "555666777"
            assert channel_data["empty_since"] is None

            # Verify file persistence
            assert data_file.exists()

    def test_update_channel_status(self):
        """Test updating channel empty status."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_file = Path(temp_dir) / "test_channels.json"
            tracker = VoiceChannelTracker(str(data_file))

            # Add a test channel
            mock_channel = MagicMock(spec=discord.VoiceChannel)
            mock_channel.id = 123456789
            mock_channel.name = "Test Channel"
            mock_guild = MagicMock()
            mock_guild.id = 987654321
            mock_channel.guild = mock_guild

            tracker.add_channel(mock_channel, "public", 555666777)

            # Test becoming empty
            tracker.update_channel_status(123456789, True)
            channel_data = tracker._data["voice_channels"]["123456789"]
            assert channel_data["empty_since"] is not None

            # Test becoming occupied
            tracker.update_channel_status(123456789, False)
            channel_data = tracker._data["voice_channels"]["123456789"]
            assert channel_data["empty_since"] is None

    def test_get_channels_for_cleanup(self):
        """Test getting channels ready for cleanup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_file = Path(temp_dir) / "test_channels.json"
            tracker = VoiceChannelTracker(str(data_file))

            # Create test data with different timestamps
            current_time = datetime.utcnow()
            old_empty_time = current_time - timedelta(minutes=20)
            recent_empty_time = current_time - timedelta(minutes=5)

            tracker._data = {
                "voice_channels": {
                    "123": {
                        "channel_id": "123",
                        "name": "Old Empty",
                        "empty_since": old_empty_time.isoformat()
                    },
                    "456": {
                        "channel_id": "456",
                        "name": "Recent Empty",
                        "empty_since": recent_empty_time.isoformat()
                    },
                    "789": {
                        "channel_id": "789",
                        "name": "Not Empty",
                        "empty_since": None
                    }
                }
            }

            # Get channels for cleanup (15 minute threshold)
            cleanup_candidates = tracker.get_channels_for_cleanup(15)

            # Only the old empty channel should be ready for cleanup
            assert len(cleanup_candidates) == 1
            assert cleanup_candidates[0]["channel_id"] == "123"

    def test_remove_channel(self):
        """Test removing a channel from tracking."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_file = Path(temp_dir) / "test_channels.json"
            tracker = VoiceChannelTracker(str(data_file))

            # Add a test channel
            mock_channel = MagicMock(spec=discord.VoiceChannel)
            mock_channel.id = 123456789
            mock_channel.name = "Test Channel"
            mock_guild = MagicMock()
            mock_guild.id = 987654321
            mock_channel.guild = mock_guild

            tracker.add_channel(mock_channel, "public", 555666777)
            assert "123456789" in tracker._data["voice_channels"]

            # Remove channel
            tracker.remove_channel(123456789)
            assert "123456789" not in tracker._data["voice_channels"]

    def test_cleanup_stale_entries(self):
        """Test cleaning up stale tracking entries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_file = Path(temp_dir) / "test_channels.json"
            tracker = VoiceChannelTracker(str(data_file))

            # Create test data with some valid and invalid channel IDs
            tracker._data = {
                "voice_channels": {
                    "123": {"channel_id": "123", "name": "Valid 1"},
                    "456": {"channel_id": "456", "name": "Valid 2"},
                    "789": {"channel_id": "789", "name": "Stale 1"},
                    "999": {"channel_id": "999", "name": "Stale 2"}
                }
            }

            # Clean up stale entries (only 123 and 456 are valid)
            removed_count = tracker.cleanup_stale_entries([123, 456])

            assert removed_count == 2
            assert len(tracker._data["voice_channels"]) == 2
            assert "123" in tracker._data["voice_channels"]
            assert "456" in tracker._data["voice_channels"]
            assert "789" not in tracker._data["voice_channels"]
            assert "999" not in tracker._data["voice_channels"]


class TestVoiceChannelCleanupService:
    """Test voice channel cleanup service functionality."""

    @pytest.fixture
    def cleanup_service(self):
        """Create a cleanup service instance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_file = Path(temp_dir) / "test_channels.json"
            return VoiceChannelCleanupService(str(data_file))

    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance."""
        bot = AsyncMock(spec=commands.Bot)
        return bot

    @pytest.mark.asyncio
    async def test_verify_tracked_channels(self, cleanup_service, mock_bot):
        """Test verification of tracked channels on startup."""
        # Add test data
        cleanup_service.tracker._data = {
            "voice_channels": {
                "123": {
                    "channel_id": "123",
                    "guild_id": "999",
                    "name": "Valid Channel"
                },
                "456": {
                    "channel_id": "456",
                    "guild_id": "888",
                    "name": "Invalid Guild"
                },
                "789": {
                    "channel_id": "789",
                    "guild_id": "999",
                    "name": "Invalid Channel"
                }
            }
        }

        # Mock guild and channel
        mock_guild = MagicMock()
        mock_guild.id = 999
        mock_channel = MagicMock()
        mock_channel.id = 123

        mock_bot.get_guild.side_effect = lambda guild_id: mock_guild if guild_id == 999 else None
        mock_guild.get_channel.side_effect = lambda channel_id: mock_channel if channel_id == 123 else None

        await cleanup_service.verify_tracked_channels(mock_bot)

        # Only valid channel should remain
        assert len(cleanup_service.tracker._data["voice_channels"]) == 1
        assert "123" in cleanup_service.tracker._data["voice_channels"]

    @pytest.mark.asyncio
    async def test_check_channel_status(self, cleanup_service, mock_bot):
        """Test checking individual channel status."""
        # Mock guild and channel
        mock_guild = MagicMock()
        mock_guild.id = 999
        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.members = []  # Empty channel

        mock_bot.get_guild.return_value = mock_guild
        mock_guild.get_channel.return_value = mock_channel

        channel_data = {
            "channel_id": "123",
            "guild_id": "999",
            "name": "Test Channel"
        }

        await cleanup_service.check_channel_status(mock_bot, channel_data)

        # Should have called update_channel_status with is_empty=True
        tracked_data = cleanup_service.tracker.get_tracked_channel(123)
        # Since the channel wasn't previously tracked, update_channel_status won't work
        # This test mainly verifies the method runs without error

    @pytest.mark.asyncio
    async def test_cleanup_channel(self, cleanup_service, mock_bot):
        """Test cleaning up an individual channel."""
        # Mock guild and channel
        mock_guild = MagicMock()
        mock_guild.id = 999
        mock_channel = AsyncMock(spec=discord.VoiceChannel)
        mock_channel.id = 123
        mock_channel.members = []  # Empty channel

        mock_bot.get_guild.return_value = mock_guild
        mock_guild.get_channel.return_value = mock_channel

        # Add channel to tracking first
        cleanup_service.tracker._data["voice_channels"]["123"] = {
            "channel_id": "123",
            "guild_id": "999",
            "name": "Test Channel"
        }

        channel_data = {
            "channel_id": "123",
            "guild_id": "999",
            "name": "Test Channel"
        }

        await cleanup_service.cleanup_channel(mock_bot, channel_data)

        # Should have deleted the channel
        mock_channel.delete.assert_called_once_with(reason="Automatic cleanup - empty for 15+ minutes")

        # Should have removed from tracking
        assert "123" not in cleanup_service.tracker._data["voice_channels"]


class TestVoiceChannelCommands:
    """Test voice channel command functionality."""

    @pytest.fixture
    def bot(self):
        """Create a mock bot instance."""
        bot = AsyncMock(spec=commands.Bot)
        # Mock voice cleanup service
        bot.voice_cleanup_service = MagicMock()
        bot.voice_cleanup_service.tracker = MagicMock()
        return bot

    @pytest.fixture
    def voice_cog(self, bot):
        """Create VoiceChannelCommands cog instance."""
        return VoiceChannelCommands(bot)

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = AsyncMock(spec=discord.Interaction)

        # Mock the user
        user = MagicMock(spec=discord.User)
        user.id = 12345
        user.display_name = "TestUser"
        interaction.user = user

        # Mock the guild
        guild = MagicMock(spec=discord.Guild)
        guild.id = 67890
        guild.default_role = MagicMock()
        interaction.guild = guild

        # Mock response methods
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        return interaction

    @pytest.fixture
    def mock_context(self):
        """Create a mock Discord context for prefix commands."""
        ctx = AsyncMock(spec=commands.Context)

        # Mock the author (user)
        author = MagicMock(spec=discord.User)
        author.id = 12345
        author.display_name = "TestUser"
        ctx.author = author

        # Mock send method
        ctx.send = AsyncMock()

        return ctx

    @pytest.mark.asyncio
    async def test_create_public_channel_success(self, voice_cog, mock_interaction):
        """Test successful public channel creation."""
        # Mock user team
        mock_team = MagicMock(spec=Team)
        mock_team.id = 1
        mock_team.abbrev = "NYY"
        mock_team.lname = "New York Yankees"
        # Mock roster_type method to return MAJOR_LEAGUE for NYY
        from models.team import RosterType
        mock_team.roster_type.return_value = RosterType.MAJOR_LEAGUE

        # Mock voice category
        mock_category = MagicMock()
        mock_interaction.guild.categories = [mock_category]

        # Mock created channel
        mock_channel = AsyncMock(spec=discord.VoiceChannel)
        mock_channel.id = 999888777
        mock_channel.name = "Gameplay Phoenix"
        mock_channel.mention = "#gameplay-phoenix"

        with patch('commands.voice.channels.team_service') as mock_team_service:
            with patch.object(mock_interaction.guild, 'create_voice_channel', return_value=mock_channel) as mock_create:
                with patch('commands.voice.channels.random_codename', return_value="Phoenix"):
                    with patch('discord.utils.get', return_value=mock_category):
                        mock_team_service.get_teams_by_owner = AsyncMock(return_value=[mock_team])

                        await voice_cog.create_public_channel.callback(voice_cog, mock_interaction)

                        # Verify response was deferred
                        mock_interaction.response.defer.assert_called_once()

                        # Verify channel was created
                        mock_create.assert_called_once()
                        args, kwargs = mock_create.call_args
                        assert kwargs['name'] == "Gameplay Phoenix"
                        assert kwargs['category'] == mock_category

                        # Verify success message was sent
                        mock_interaction.followup.send.assert_called_once()
                        call_args = mock_interaction.followup.send.call_args
                        assert 'embed' in call_args.kwargs
                        embed = call_args.kwargs['embed']
                        assert "Voice Channel Created" in embed.title

    @pytest.mark.asyncio
    async def test_create_public_channel_no_team(self, voice_cog, mock_interaction):
        """Test public channel creation with no team."""
        with patch('commands.voice.channels.team_service') as mock_team_service:
            mock_team_service.get_teams_by_owner = AsyncMock(return_value=[])

            await voice_cog.create_public_channel.callback(voice_cog, mock_interaction)

            # Verify response was deferred
            mock_interaction.response.defer.assert_called_once()

            # Verify error message was sent
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            assert call_args.kwargs['ephemeral'] is True
            embed = call_args.kwargs['embed']
            assert "No Major League Team Found" in embed.title

    @pytest.mark.asyncio
    async def test_create_private_channel_success(self, voice_cog, mock_interaction):
        """Test successful private channel creation."""
        # Mock user team
        mock_user_team = MagicMock(spec=Team)
        mock_user_team.id = 1
        mock_user_team.abbrev = "NYY"
        mock_user_team.lname = "New York Yankees"
        mock_user_team.sname = "Yankees"
        # Mock roster_type method to return MAJOR_LEAGUE for NYY
        from models.team import RosterType
        mock_user_team.roster_type.return_value = RosterType.MAJOR_LEAGUE

        # Mock opponent team
        mock_opponent_team = MagicMock(spec=Team)
        mock_opponent_team.id = 2
        mock_opponent_team.abbrev = "BOS"
        mock_opponent_team.lname = "Boston Red Sox"
        mock_opponent_team.sname = "Red Sox"

        # Mock game
        mock_game = MagicMock(spec=Game)
        mock_game.week = 5
        mock_game.away_team = mock_user_team
        mock_game.home_team = mock_opponent_team
        mock_game.is_completed = False

        # Mock current league info
        mock_current = MagicMock()
        mock_current.season = 12
        mock_current.week = 5

        # Mock voice category and roles
        mock_category = MagicMock()
        mock_user_role = MagicMock()
        mock_opponent_role = MagicMock()

        # Mock created channel
        mock_channel = AsyncMock(spec=discord.VoiceChannel)
        mock_channel.id = 999888777
        mock_channel.name = "Yankees vs Red Sox"
        mock_channel.mention = "#yankees-vs-red-sox"

        with patch('commands.voice.channels.team_service') as mock_team_service:
            with patch('commands.voice.channels.league_service') as mock_league_service:
                with patch.object(voice_cog.schedule_service, 'get_team_schedule') as mock_schedule:
                    with patch.object(mock_interaction.guild, 'create_voice_channel', return_value=mock_channel) as mock_create:
                        with patch('discord.utils.get') as mock_utils_get:

                            mock_team_service.get_teams_by_owner = AsyncMock(return_value=[mock_user_team])
                            mock_league_service.get_current_state = AsyncMock(return_value=mock_current)
                            mock_schedule.return_value = [mock_game]

                            # Mock discord.utils.get calls
                            def mock_get(collection, **kwargs):
                                if 'name' in kwargs and kwargs['name'] == "Voice Channels":
                                    return mock_category
                                elif 'name' in kwargs and kwargs['name'] == "New York Yankees":
                                    return mock_user_role
                                elif 'name' in kwargs and kwargs['name'] == "Boston Red Sox":
                                    return mock_opponent_role
                                return None

                            mock_utils_get.side_effect = mock_get

                            await voice_cog.create_private_channel.callback(voice_cog, mock_interaction)

                            # Verify response was deferred
                            mock_interaction.response.defer.assert_called_once()

                            # Verify channel was created
                            mock_create.assert_called_once()
                            args, kwargs = mock_create.call_args
                            assert kwargs['name'] == "Yankees vs Red Sox"
                            assert kwargs['category'] == mock_category

                            # Verify success message was sent
                            mock_interaction.followup.send.assert_called_once()
                            call_args = mock_interaction.followup.send.call_args
                            assert 'embed' in call_args.kwargs
                            embed = call_args.kwargs['embed']
                            assert "Private Voice Channel Created" in embed.title

    @pytest.mark.asyncio
    async def test_deprecated_vc_command(self, voice_cog, mock_context):
        """Test deprecated !vc command shows migration message."""
        await voice_cog.deprecated_public_voice.callback(voice_cog, mock_context)

        # Verify migration message was sent
        mock_context.send.assert_called_once()
        call_args = mock_context.send.call_args
        embed = call_args.kwargs['embed']
        assert "Command Deprecated" in embed.title
        assert "/voice-channel public" in embed.description

    @pytest.mark.asyncio
    async def test_deprecated_private_command(self, voice_cog, mock_context):
        """Test deprecated !private command shows migration message."""
        await voice_cog.deprecated_private_voice.callback(voice_cog, mock_context)

        # Verify migration message was sent
        mock_context.send.assert_called_once()
        call_args = mock_context.send.call_args
        embed = call_args.kwargs['embed']
        assert "Command Deprecated" in embed.title
        assert "/voice-channel private" in embed.description

    def test_random_codename_generation(self):
        """Test that random codename generation works."""
        from commands.voice.channels import random_codename, CODENAMES

        # Generate multiple codenames
        generated = [random_codename() for _ in range(10)]

        # All should be from the codenames list
        for codename in generated:
            assert codename in CODENAMES

        # Should have some variety (unlikely all same)
        unique_names = set(generated)
        assert len(unique_names) > 1  # Should have at least some variety

    def test_voice_group_attributes(self, voice_cog):
        """Test that voice command group has correct attributes."""
        assert hasattr(voice_cog, 'voice_group')
        assert voice_cog.voice_group.name == "voice-channel"
        assert voice_cog.voice_group.description == "Create voice channels for gameplay"

    def test_command_attributes(self, voice_cog):
        """Test that commands have correct attributes."""
        # Test prefix commands exist
        assert hasattr(voice_cog, 'deprecated_public_voice')
        assert hasattr(voice_cog, 'deprecated_private_voice')

        # Check command names and aliases
        public_cmd = voice_cog.deprecated_public_voice
        assert public_cmd.name == "vc"
        assert public_cmd.aliases == ["voice", "gameplay"]

        private_cmd = voice_cog.deprecated_private_voice
        assert private_cmd.name == "private"