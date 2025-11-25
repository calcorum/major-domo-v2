"""
Tests for team branding management commands.

Covers validation functions, permission checking, and command execution.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aioresponses import aioresponses

from commands.teams.branding import (
    validate_hex_color,
    validate_image_url,
    BrandingCommands
)
from models.team import Team
from tests.factories import TeamFactory


class TestHexColorValidation:
    """Test hex color format validation."""

    def test_valid_hex_no_prefix(self):
        """Test that valid hex without # prefix passes validation."""
        is_valid, normalized, error = validate_hex_color("FF5733")
        assert is_valid is True
        assert normalized == "FF5733"
        assert error == ""

    def test_valid_hex_with_prefix(self):
        """Test that valid hex with # prefix passes validation."""
        is_valid, normalized, error = validate_hex_color("#FF5733")
        assert is_valid is True
        assert normalized == "FF5733"  # Prefix stripped
        assert error == ""

    def test_valid_hex_lowercase(self):
        """Test that lowercase hex is normalized to uppercase."""
        is_valid, normalized, error = validate_hex_color("ff5733")
        assert is_valid is True
        assert normalized == "FF5733"
        assert error == ""

    def test_valid_hex_with_prefix_and_lowercase(self):
        """Test that lowercase hex with # prefix is normalized."""
        is_valid, normalized, error = validate_hex_color("#ff5733")
        assert is_valid is True
        assert normalized == "FF5733"
        assert error == ""

    def test_empty_string_valid(self):
        """Test that empty string is valid (means keep current value)."""
        is_valid, normalized, error = validate_hex_color("")
        assert is_valid is True
        assert normalized == ""
        assert error == ""

    def test_invalid_length_too_short(self):
        """Test that hex color with wrong length fails validation."""
        is_valid, normalized, error = validate_hex_color("FF57")
        assert is_valid is False
        assert "6 characters" in error

    def test_invalid_length_too_long(self):
        """Test that hex color with wrong length fails validation."""
        is_valid, normalized, error = validate_hex_color("FF57331")
        assert is_valid is False
        assert "6 characters" in error

    def test_invalid_characters(self):
        """Test that non-hex characters fail validation."""
        is_valid, normalized, error = validate_hex_color("GGGGGG")
        assert is_valid is False
        assert "hex digits" in error

    def test_invalid_special_characters(self):
        """Test that special characters fail validation."""
        is_valid, normalized, error = validate_hex_color("FF57@3")
        assert is_valid is False
        assert "hex digits" in error


@pytest.mark.asyncio
class TestImageURLValidation:
    """Test image URL format and accessibility validation."""

    async def test_valid_png_url(self):
        """Test that valid PNG URL passes format validation and accessibility check."""
        url = "https://example.com/logo.png"

        with aioresponses() as m:
            m.head(url, status=200, headers={'Content-Type': 'image/png'})

            is_valid, error = await validate_image_url(url)
            assert is_valid is True
            assert error == ""

    async def test_valid_jpg_url(self):
        """Test that valid JPG URL passes validation."""
        url = "https://example.com/logo.jpg"

        with aioresponses() as m:
            m.head(url, status=200, headers={'Content-Type': 'image/jpeg'})

            is_valid, error = await validate_image_url(url)
            assert is_valid is True
            assert error == ""

    async def test_valid_webp_url(self):
        """Test that valid WebP URL passes validation."""
        url = "https://example.com/logo.webp"

        with aioresponses() as m:
            m.head(url, status=200, headers={'Content-Type': 'image/webp'})

            is_valid, error = await validate_image_url(url)
            assert is_valid is True
            assert error == ""

    async def test_url_with_query_params(self):
        """Test that URL with query parameters passes validation."""
        url = "https://example.com/logo.png?size=large"

        with aioresponses() as m:
            m.head(url, status=200, headers={'Content-Type': 'image/png'})

            is_valid, error = await validate_image_url(url)
            assert is_valid is True
            assert error == ""

    async def test_empty_url_valid(self):
        """Test that empty URL is valid (means keep current value)."""
        is_valid, error = await validate_image_url("")
        assert is_valid is True
        assert error == ""

    async def test_invalid_protocol_ftp(self):
        """Test that FTP protocol fails validation."""
        url = "ftp://example.com/logo.png"
        is_valid, error = await validate_image_url(url)
        assert is_valid is False
        assert "http" in error.lower()

    async def test_invalid_no_protocol(self):
        """Test that URL without protocol fails validation."""
        url = "example.com/logo.png"
        is_valid, error = await validate_image_url(url)
        assert is_valid is False
        assert "http" in error.lower()

    async def test_invalid_extension(self):
        """Test that invalid extension fails validation."""
        url = "https://example.com/document.pdf"
        is_valid, error = await validate_image_url(url)
        assert is_valid is False
        assert any(ext in error for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp'])

    async def test_url_not_accessible_404(self):
        """Test that inaccessible URL (404) fails validation."""
        url = "https://example.com/logo.png"

        with aioresponses() as m:
            m.head(url, status=404)

            is_valid, error = await validate_image_url(url)
            assert is_valid is False
            assert "404" in error

    async def test_url_wrong_content_type(self):
        """Test that URL with wrong content-type fails validation."""
        url = "https://example.com/logo.png"

        with aioresponses() as m:
            m.head(url, status=200, headers={'Content-Type': 'text/html'})

            is_valid, error = await validate_image_url(url)
            assert is_valid is False
            assert "image" in error.lower()

    async def test_url_timeout(self):
        """Test that timeout fails validation gracefully."""
        url = "https://example.com/logo.png"

        with aioresponses() as m:
            m.head(url, exception=asyncio.TimeoutError())

            is_valid, error = await validate_image_url(url)
            assert is_valid is False
            assert "timed out" in error.lower()


@pytest.mark.asyncio
class TestBrandingCommand:
    """Test branding command workflows."""

    @pytest.fixture
    def mock_bot(self):
        """Create mock bot instance."""
        bot = MagicMock()
        return bot

    @pytest.fixture
    def branding_cog(self, mock_bot):
        """Create BrandingCommands cog instance."""
        return BrandingCommands(mock_bot)

    @pytest.fixture
    def mock_interaction(self):
        """Create mock Discord interaction."""
        interaction = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 123456789
        interaction.guild = MagicMock()
        interaction.guild.roles = []
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        return interaction

    @pytest.fixture
    def sample_team(self):
        """Create sample team data."""
        return Team(
            id=1,
            abbrev="NYY",
            sname="Yankees",
            lname="New York Yankees",
            color="003087",
            dice_color="E4002B",
            thumbnail="https://example.com/yankees.png",
            stadium="Yankee Stadium",
            season=12,
            roster_type="majors",
            owner_id=123456789
        )

    async def test_validate_all_inputs_major_color_only(self, branding_cog):
        """Test validating major league color only."""
        modal_data = {
            'major_color': 'FF5733',
            'major_logo': '',
            'minor_color': '',
            'minor_logo': '',
            'dice_color': '',
        }

        updates, errors = await branding_cog._validate_all_inputs(modal_data)

        assert len(errors) == 0
        assert updates['major']['color'] == 'FF5733'
        assert 'thumbnail' not in updates['major']
        assert len(updates['minor']) == 0

    async def test_validate_all_inputs_dice_color(self, branding_cog):
        """Test validating dice color update."""
        modal_data = {
            'major_color': '',
            'major_logo': '',
            'minor_color': '',
            'minor_logo': '',
            'dice_color': '#A6CE39',
        }

        updates, errors = await branding_cog._validate_all_inputs(modal_data)

        assert len(errors) == 0
        assert updates['major']['dice_color'] == 'A6CE39'

    async def test_validate_all_inputs_invalid_color(self, branding_cog):
        """Test that invalid color produces error."""
        modal_data = {
            'major_color': 'GGGGGG',  # Invalid hex
            'major_logo': '',
            'minor_color': '',
            'minor_logo': '',
            'dice_color': '',
        }

        updates, errors = await branding_cog._validate_all_inputs(modal_data)

        assert len(errors) == 1
        assert "Major Team Color" in errors[0]
        assert "hex digits" in errors[0]

    async def test_validate_all_inputs_multiple_errors(self, branding_cog):
        """Test that multiple validation errors are collected."""
        modal_data = {
            'major_color': 'GGG',  # Invalid
            'major_logo': 'not-a-url',  # Invalid
            'minor_color': '',
            'minor_logo': '',
            'dice_color': 'ZZZ',  # Invalid
        }

        updates, errors = await branding_cog._validate_all_inputs(modal_data)

        assert len(errors) >= 2  # At least color errors
        assert any("Major Team Color" in e for e in errors)
        assert any("Dice" in e for e in errors)

    async def test_validate_all_inputs_valid_url(self, branding_cog):
        """Test that valid URLs are added to updates."""
        url = "https://example.com/logo.png"

        with aioresponses() as m:
            m.head(url, status=200, headers={'Content-Type': 'image/png'})

            modal_data = {
                'major_color': '',
                'major_logo': url,
                'minor_color': '',
                'minor_logo': '',
                'dice_color': '',
            }

            updates, errors = await branding_cog._validate_all_inputs(modal_data)

            assert len(errors) == 0
            assert updates['major']['thumbnail'] == url

    async def test_create_preview_embeds_major_only(self, branding_cog, sample_team):
        """Test creating preview embeds for major league team only."""
        updates = {
            'major': {'color': 'FF5733', 'thumbnail': 'https://example.com/new.png'},
            'minor': {}
        }

        embeds = await branding_cog._create_preview_embeds(sample_team, None, updates)

        assert len(embeds) >= 1
        assert "New York Yankees" in embeds[0].title
        assert embeds[0].color.value == int('FF5733', 16)

    async def test_create_preview_embeds_with_dice_color(self, branding_cog, sample_team):
        """Test creating preview embeds including dice color."""
        updates = {
            'major': {'dice_color': 'A6CE39'},
            'minor': {}
        }

        embeds = await branding_cog._create_preview_embeds(sample_team, None, updates)

        # Should have at least 1 embed (major) and possibly dice embed
        assert len(embeds) >= 1

    async def test_format_success_message_major_updates(self, branding_cog):
        """Test formatting success message for major league updates."""
        updates = {
            'major': {'color': 'FF5733', 'thumbnail': 'https://example.com/new.png'},
            'minor': {}
        }

        message = branding_cog._format_success_message(updates, True, None)

        assert "Major League" in message
        assert "FF5733" in message
        assert "Logo" in message
        assert "✅" in message

    async def test_format_success_message_with_role_error(self, branding_cog):
        """Test formatting success message when role update fails."""
        updates = {
            'major': {'color': 'FF5733'},
            'minor': {}
        }

        message = branding_cog._format_success_message(updates, False, "Missing permissions")

        assert "Major League" in message
        assert "FF5733" in message
        assert "Missing permissions" in message or "⚠️" in message

    async def test_format_success_message_minor_updates(self, branding_cog):
        """Test formatting success message for minor league updates."""
        updates = {
            'major': {},
            'minor': {'color': '33C3FF', 'thumbnail': 'https://example.com/mil.png'}
        }

        message = branding_cog._format_success_message(updates, False, None)

        assert "Minor League" in message
        assert "33C3FF" in message


@pytest.mark.asyncio
class TestDiscordRoleUpdate:
    """Test Discord role color update functionality."""

    @pytest.fixture
    def mock_bot(self):
        """Create mock bot instance."""
        return MagicMock()

    @pytest.fixture
    def branding_cog(self, mock_bot):
        """Create BrandingCommands cog instance."""
        return BrandingCommands(mock_bot)

    @pytest.fixture
    def mock_interaction(self):
        """Create mock Discord interaction with guild and roles."""
        interaction = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 123456789
        interaction.guild = MagicMock()
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        return interaction

    @pytest.fixture
    def sample_team(self):
        """Create sample team data."""
        return Team(
            id=1,
            abbrev="NYY",
            sname="Yankees",
            lname="New York Yankees",
            color="003087",
            dice_color="E4002B",
            thumbnail="https://example.com/yankees.png",
            stadium="Yankee Stadium",
            season=12,
            roster_type="majors",
            owner_id=123456789
        )

    async def test_update_discord_role_success(self, branding_cog, mock_interaction, sample_team):
        """Test successful Discord role color update."""
        # Create mock role
        mock_role = AsyncMock()
        mock_role.name = "New York Yankees"
        mock_role.edit = AsyncMock()
        mock_interaction.guild.roles = [mock_role]

        # Patch discord.utils.get to return our mock role
        with patch('commands.teams.branding.discord.utils.get', return_value=mock_role):
            success, error = await branding_cog._update_discord_role_color(
                mock_interaction,
                sample_team,
                "FF5733"
            )

            assert success is True
            assert error is None
            mock_role.edit.assert_called_once()

    async def test_update_discord_role_not_found(self, branding_cog, mock_interaction, sample_team):
        """Test Discord role update when role is not found."""
        mock_interaction.guild.roles = []

        # Patch discord.utils.get to return None
        with patch('commands.teams.branding.discord.utils.get', return_value=None):
            success, error = await branding_cog._update_discord_role_color(
                mock_interaction,
                sample_team,
                "FF5733"
            )

            assert success is False
            assert "not found" in error.lower()

    async def test_update_discord_role_forbidden(self, branding_cog, mock_interaction, sample_team):
        """Test Discord role update when missing permissions."""
        import discord as discord_module

        # Create mock role that raises Forbidden
        mock_role = AsyncMock()
        mock_role.name = "New York Yankees"
        mock_role.edit = AsyncMock(side_effect=discord_module.Forbidden(
            MagicMock(status=403), "Missing Permissions"
        ))
        mock_interaction.guild.roles = [mock_role]

        with patch('commands.teams.branding.discord.utils.get', return_value=mock_role):
            success, error = await branding_cog._update_discord_role_color(
                mock_interaction,
                sample_team,
                "FF5733"
            )

            assert success is False
            assert "permission" in error.lower()
