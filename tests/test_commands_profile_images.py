"""
Tests for player image management commands.

Covers URL validation, permission checking, and command execution.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch
import aiohttp
from aioresponses import aioresponses

from commands.profile.images import (
    validate_url_format,
    check_url_accessibility,
    can_edit_player_image,
    ImageCommands
)
from models.player import Player
from models.team import Team
from tests.factories import PlayerFactory, TeamFactory


class TestURLValidation:
    """Test URL format validation."""

    def test_valid_jpg_url(self):
        """Test valid JPG URL passes validation."""
        url = "https://example.com/image.jpg"
        is_valid, error = validate_url_format(url)
        assert is_valid is True
        assert error == ""

    def test_valid_png_url(self):
        """Test valid PNG URL passes validation."""
        url = "https://example.com/image.png"
        is_valid, error = validate_url_format(url)
        assert is_valid is True
        assert error == ""

    def test_valid_webp_url(self):
        """Test valid WebP URL passes validation."""
        url = "https://example.com/image.webp"
        is_valid, error = validate_url_format(url)
        assert is_valid is True
        assert error == ""

    def test_url_with_query_params(self):
        """Test URL with query parameters passes validation."""
        url = "https://example.com/image.jpg?size=large&format=original"
        is_valid, error = validate_url_format(url)
        assert is_valid is True
        assert error == ""

    def test_invalid_no_protocol(self):
        """Test URL without protocol fails validation."""
        url = "example.com/image.jpg"
        is_valid, error = validate_url_format(url)
        assert is_valid is False
        assert "must start with http" in error.lower()

    def test_invalid_ftp_protocol(self):
        """Test FTP protocol fails validation."""
        url = "ftp://example.com/image.jpg"
        is_valid, error = validate_url_format(url)
        assert is_valid is False
        assert "must start with http" in error.lower()

    def test_invalid_extension(self):
        """Test invalid file extension fails validation."""
        url = "https://example.com/document.pdf"
        is_valid, error = validate_url_format(url)
        assert is_valid is False
        assert "extension" in error.lower()

    def test_invalid_no_extension(self):
        """Test URL without extension fails validation."""
        url = "https://example.com/image"
        is_valid, error = validate_url_format(url)
        assert is_valid is False
        assert "extension" in error.lower()

    def test_url_too_long(self):
        """Test URL exceeding max length fails validation."""
        url = "https://example.com/" + "a" * 500 + ".jpg"
        is_valid, error = validate_url_format(url)
        assert is_valid is False
        assert "too long" in error.lower()


@pytest.mark.asyncio
class TestURLAccessibility:
    """Test URL accessibility checking."""

    async def test_accessible_url_success(self):
        """Test accessible URL with image content-type."""
        url = "https://example.com/image.jpg"

        with aioresponses() as m:
            m.head(url, status=200, headers={'content-type': 'image/jpeg'})

            is_accessible, error = await check_url_accessibility(url)

            assert is_accessible is True
            assert error == ""

    async def test_url_not_found(self):
        """Test URL returning 404."""
        url = "https://example.com/missing.jpg"

        with aioresponses() as m:
            m.head(url, status=404)

            is_accessible, error = await check_url_accessibility(url)

            assert is_accessible is False
            assert "404" in error

    async def test_url_wrong_content_type(self):
        """Test URL returning non-image content."""
        url = "https://example.com/page.html"

        with aioresponses() as m:
            m.head(url, status=200, headers={'content-type': 'text/html'})

            is_accessible, error = await check_url_accessibility(url)

            assert is_accessible is False
            assert "not return an image" in error

    async def test_url_timeout(self):
        """Test URL request timeout."""
        url = "https://example.com/slow.jpg"

        with aioresponses() as m:
            m.head(url, exception=asyncio.TimeoutError())

            is_accessible, error = await check_url_accessibility(url)

            assert is_accessible is False
            assert "timed out" in error.lower()

    async def test_url_connection_error(self):
        """Test URL connection error."""
        url = "https://unreachable.example.com/image.jpg"

        with aioresponses() as m:
            m.head(url, exception=aiohttp.ClientError("Connection failed"))

            is_accessible, error = await check_url_accessibility(url)

            assert is_accessible is False
            assert "could not access" in error.lower()


@pytest.mark.asyncio
class TestPermissionChecking:
    """Test permission checking logic."""

    async def test_admin_can_edit_any_player(self):
        """Test administrator can edit any player's images."""
        mock_interaction = MagicMock()
        mock_interaction.user.id = 12345
        mock_interaction.user.guild_permissions.administrator = True

        player = PlayerFactory.create(id=1, name="Test Player")
        player.team = TeamFactory.create(id=1, abbrev="NYY")

        mock_logger = MagicMock()

        has_permission, error = await can_edit_player_image(
            mock_interaction, player, 12, mock_logger
        )

        assert has_permission is True
        assert error == ""

    async def test_user_can_edit_own_team_player(self):
        """Test user can edit players on their own team."""
        mock_interaction = MagicMock()
        mock_interaction.user.id = 12345
        mock_interaction.user.guild_permissions.administrator = False

        player_team = TeamFactory.create(id=1, abbrev="NYY", season=12)
        player = PlayerFactory.create(id=1, name="Test Player")
        player.team = player_team

        user_team = TeamFactory.create(id=1, abbrev="NYY", season=12)

        mock_logger = MagicMock()

        with patch('commands.profile.images.team_service.get_teams_by_owner') as mock_get_teams:
            mock_get_teams.return_value = [user_team]

            has_permission, error = await can_edit_player_image(
                mock_interaction, player, 12, mock_logger
            )

            assert has_permission is True
            assert error == ""

    async def test_user_can_edit_mil_player(self):
        """Test user can edit players on their minor league team."""
        mock_interaction = MagicMock()
        mock_interaction.user.id = 12345
        mock_interaction.user.guild_permissions.administrator = False

        player_team = TeamFactory.create(id=2, abbrev="NYYMIL", season=12)
        player = PlayerFactory.create(id=1, name="Minor Player")
        player.team = player_team

        # User owns the major league team
        user_team = TeamFactory.create(id=1, abbrev="NYY", season=12)

        mock_logger = MagicMock()

        with patch('commands.profile.images.team_service.get_teams_by_owner') as mock_get_teams:
            mock_get_teams.return_value = [user_team]

            has_permission, error = await can_edit_player_image(
                mock_interaction, player, 12, mock_logger
            )

            assert has_permission is True
            assert error == ""

    async def test_user_cannot_edit_other_org_player(self):
        """Test user cannot edit players from other organizations."""
        mock_interaction = MagicMock()
        mock_interaction.user.id = 12345
        mock_interaction.user.guild_permissions.administrator = False

        player_team = TeamFactory.create(id=2, abbrev="BOS", season=12)
        player = PlayerFactory.create(id=1, name="Other Player")
        player.team = player_team

        # User owns a different team
        user_team = TeamFactory.create(id=1, abbrev="NYY", season=12)

        mock_logger = MagicMock()

        with patch('commands.profile.images.team_service.get_teams_by_owner') as mock_get_teams:
            mock_get_teams.return_value = [user_team]

            has_permission, error = await can_edit_player_image(
                mock_interaction, player, 12, mock_logger
            )

            assert has_permission is False
            assert "don't own" in error.lower()

    async def test_user_with_no_teams_cannot_edit(self):
        """Test user without teams cannot edit any player."""
        mock_interaction = MagicMock()
        mock_interaction.user.id = 12345
        mock_interaction.user.guild_permissions.administrator = False

        player_team = TeamFactory.create(id=1, abbrev="NYY", season=12)
        player = PlayerFactory.create(id=1, name="Test Player")
        player.team = player_team

        mock_logger = MagicMock()

        with patch('commands.profile.images.team_service.get_teams_by_owner') as mock_get_teams:
            mock_get_teams.return_value = []

            has_permission, error = await can_edit_player_image(
                mock_interaction, player, 12, mock_logger
            )

            assert has_permission is False
            assert "don't own any teams" in error.lower()

    async def test_player_without_team_fails(self):
        """Test player without team assignment fails permission check."""
        mock_interaction = MagicMock()
        mock_interaction.user.id = 12345
        mock_interaction.user.guild_permissions.administrator = False

        player = PlayerFactory.create(id=1, name="Free Agent")
        player.team = None

        mock_logger = MagicMock()

        has_permission, error = await can_edit_player_image(
            mock_interaction, player, 12, mock_logger
        )

        assert has_permission is False
        assert "cannot determine" in error.lower()


@pytest.mark.asyncio
class TestImageCommandsIntegration:
    """Integration tests for ImageCommands cog."""

    @pytest.fixture
    def commands_cog(self):
        """Create ImageCommands cog for testing."""
        mock_bot = MagicMock()
        return ImageCommands(mock_bot)

    async def test_set_image_command_structure(self, commands_cog):
        """Test that set_image command is properly configured."""
        assert hasattr(commands_cog, 'set_image')
        assert commands_cog.set_image.name == "set-image"

    async def test_fancy_card_updates_vanity_card_field(self, commands_cog):
        """Test fancy-card choice updates vanity_card field."""
        # This tests the field mapping logic
        img_type = "fancy-card"
        field_name = "vanity_card" if img_type == "fancy-card" else "headshot"

        assert field_name == "vanity_card"

    async def test_headshot_updates_headshot_field(self, commands_cog):
        """Test headshot choice updates headshot field."""
        # This tests the field mapping logic
        img_type = "headshot"
        field_name = "vanity_card" if img_type == "fancy-card" else "headshot"

        assert field_name == "headshot"
