"""
Tests for chart display and management commands.
"""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from discord import app_commands

from commands.utilities.charts import ChartCommands, ChartAdminCommands
from services.chart_service import ChartService, Chart, get_chart_service
from exceptions import BotException


@pytest.fixture
def temp_charts_file():
    """Create a temporary charts.json file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        charts_data = {
            "charts": {
                "rest": {
                    "name": "Pitcher Rest",
                    "category": "gameplay",
                    "description": "Pitcher rest and endurance rules",
                    "urls": ["https://example.com/rest.png"]
                },
                "defense": {
                    "name": "Defense Chart",
                    "category": "defense",
                    "description": "General defensive play chart",
                    "urls": ["https://example.com/defense.png"]
                },
                "multi-image": {
                    "name": "Multi Image Chart",
                    "category": "gameplay",
                    "description": "Chart with multiple images",
                    "urls": [
                        "https://example.com/image1.png",
                        "https://example.com/image2.png",
                        "https://example.com/image3.png"
                    ]
                }
            },
            "categories": {
                "gameplay": "Gameplay Mechanics",
                "defense": "Defensive Play",
                "reference": "Reference Charts"
            }
        }
        json.dump(charts_data, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def chart_service(temp_charts_file):
    """Create a chart service with test data."""
    with patch.object(ChartService, 'CHARTS_FILE', temp_charts_file):
        service = ChartService()
        return service


@pytest.fixture
def mock_interaction():
    """Create a mock Discord interaction."""
    interaction = AsyncMock()
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.user = MagicMock()
    interaction.user.id = 123456789
    interaction.user.display_name = "TestUser"
    interaction.guild = MagicMock()
    interaction.guild.id = 987654321
    interaction.channel = MagicMock()
    interaction.channel.name = "test-channel"
    return interaction


class TestChartService:
    """Tests for ChartService class."""

    def test_load_charts(self, chart_service):
        """Test loading charts from file."""
        assert len(chart_service._charts) == 3
        assert 'rest' in chart_service._charts
        assert 'defense' in chart_service._charts
        assert 'multi-image' in chart_service._charts

    def test_get_chart(self, chart_service):
        """Test getting a chart by key."""
        chart = chart_service.get_chart('rest')
        assert chart is not None
        assert chart.key == 'rest'
        assert chart.name == 'Pitcher Rest'
        assert chart.category == 'gameplay'
        assert len(chart.urls) == 1

    def test_get_chart_not_found(self, chart_service):
        """Test getting a non-existent chart."""
        chart = chart_service.get_chart('nonexistent')
        assert chart is None

    def test_get_all_charts(self, chart_service):
        """Test getting all charts."""
        charts = chart_service.get_all_charts()
        assert len(charts) == 3
        assert all(isinstance(c, Chart) for c in charts)

    def test_get_charts_by_category(self, chart_service):
        """Test getting charts by category."""
        gameplay_charts = chart_service.get_charts_by_category('gameplay')
        assert len(gameplay_charts) == 2
        assert all(c.category == 'gameplay' for c in gameplay_charts)

        defense_charts = chart_service.get_charts_by_category('defense')
        assert len(defense_charts) == 1
        assert defense_charts[0].key == 'defense'

    def test_get_chart_keys(self, chart_service):
        """Test getting chart keys for autocomplete."""
        keys = chart_service.get_chart_keys()
        assert keys == ['defense', 'multi-image', 'rest']  # Sorted

    def test_get_categories(self, chart_service):
        """Test getting categories."""
        categories = chart_service.get_categories()
        assert 'gameplay' in categories
        assert 'defense' in categories
        assert categories['gameplay'] == 'Gameplay Mechanics'

    def test_add_chart(self, chart_service):
        """Test adding a new chart."""
        chart_service.add_chart(
            key='new-chart',
            name='New Chart',
            category='reference',
            urls=['https://example.com/new.png'],
            description='A new chart'
        )

        chart = chart_service.get_chart('new-chart')
        assert chart is not None
        assert chart.name == 'New Chart'
        assert chart.category == 'reference'

    def test_add_duplicate_chart(self, chart_service):
        """Test adding a duplicate chart raises exception."""
        with pytest.raises(BotException, match="already exists"):
            chart_service.add_chart(
                key='rest',  # Already exists
                name='Duplicate',
                category='gameplay',
                urls=['https://example.com/dup.png']
            )

    def test_update_chart(self, chart_service):
        """Test updating an existing chart."""
        chart_service.update_chart(
            key='rest',
            name='Updated Rest Chart',
            description='Updated description'
        )

        chart = chart_service.get_chart('rest')
        assert chart.name == 'Updated Rest Chart'
        assert chart.description == 'Updated description'
        assert chart.category == 'gameplay'  # Unchanged

    def test_update_nonexistent_chart(self, chart_service):
        """Test updating a non-existent chart raises exception."""
        with pytest.raises(BotException, match="not found"):
            chart_service.update_chart(
                key='nonexistent',
                name='New Name'
            )

    def test_remove_chart(self, chart_service):
        """Test removing a chart."""
        chart_service.remove_chart('rest')
        assert chart_service.get_chart('rest') is None
        assert len(chart_service._charts) == 2

    def test_remove_nonexistent_chart(self, chart_service):
        """Test removing a non-existent chart raises exception."""
        with pytest.raises(BotException, match="not found"):
            chart_service.remove_chart('nonexistent')


class TestChartCommands:
    """Tests for ChartCommands class."""

    @pytest.fixture
    def chart_cog(self, chart_service):
        """Create ChartCommands cog with mocked service."""
        bot = AsyncMock()
        cog = ChartCommands(bot)

        with patch.object(cog, 'chart_service', chart_service):
            yield cog

    @pytest.mark.asyncio
    async def test_charts_command_single_image(self, chart_cog, mock_interaction):
        """Test displaying a chart with a single image."""
        await chart_cog.charts.callback(chart_cog, mock_interaction, 'rest')

        # Verify response was sent with embed
        mock_interaction.response.send_message.assert_called_once()
        call_kwargs = mock_interaction.response.send_message.call_args[1]
        embed = call_kwargs['embed']

        assert '📊 Pitcher Rest' in embed.title
        assert embed.description == 'Pitcher rest and endurance rules'
        assert embed.image.url == 'https://example.com/rest.png'

        # Verify no followups for single image
        mock_interaction.followup.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_charts_command_multiple_images(self, chart_cog, mock_interaction):
        """Test displaying a chart with multiple images."""
        await chart_cog.charts.callback(chart_cog, mock_interaction, 'multi-image')

        # Verify initial response
        mock_interaction.response.send_message.assert_called_once()
        call_kwargs = mock_interaction.response.send_message.call_args[1]
        embed = call_kwargs['embed']

        assert '📊 Multi Image Chart' in embed.title
        assert embed.image.url == 'https://example.com/image1.png'

        # Verify followup messages for additional images
        assert mock_interaction.followup.send.call_count == 2

    @pytest.mark.asyncio
    async def test_charts_command_not_found(self, chart_cog, mock_interaction):
        """Test displaying a non-existent chart."""
        with pytest.raises(BotException, match="not found"):
            await chart_cog.charts.callback(chart_cog, mock_interaction, 'nonexistent')

    @pytest.mark.asyncio
    async def test_chart_autocomplete(self, chart_cog, mock_interaction):
        """Test chart autocomplete functionality."""
        # Test with empty current input
        choices = await chart_cog.chart_autocomplete(mock_interaction, '')
        assert len(choices) == 3

        # Test with partial match
        choices = await chart_cog.chart_autocomplete(mock_interaction, 'def')
        assert len(choices) == 1
        assert choices[0].value == 'defense'

        # Test with no match
        choices = await chart_cog.chart_autocomplete(mock_interaction, 'xyz')
        assert len(choices) == 0


class TestChartAdminCommands:
    """Tests for ChartAdminCommands class."""

    @pytest.fixture
    def admin_cog(self, chart_service):
        """Create ChartAdminCommands cog with mocked service."""
        bot = AsyncMock()
        cog = ChartAdminCommands(bot)

        with patch.object(cog, 'chart_service', chart_service):
            yield cog

    @pytest.mark.asyncio
    async def test_chart_add_command(self, admin_cog, mock_interaction):
        """Test adding a new chart via command."""
        await admin_cog.chart_add.callback(
            admin_cog,
            mock_interaction,
            key='new-chart',
            name='New Chart',
            category='gameplay',
            url='https://example.com/new.png',
            description='Test chart'
        )

        # Verify success response
        mock_interaction.response.send_message.assert_called_once()
        call_kwargs = mock_interaction.response.send_message.call_args[1]
        embed = call_kwargs['embed']

        assert '✅ Chart Added' in embed.title
        assert call_kwargs['ephemeral'] is True

        # Verify chart was added
        chart = admin_cog.chart_service.get_chart('new-chart')
        assert chart is not None
        assert chart.name == 'New Chart'

    @pytest.mark.asyncio
    async def test_chart_add_invalid_category(self, admin_cog, mock_interaction):
        """Test adding a chart with invalid category."""
        with pytest.raises(BotException, match="Invalid category"):
            await admin_cog.chart_add.callback(
                admin_cog,
                mock_interaction,
                key='new-chart',
                name='New Chart',
                category='invalid-category',
                url='https://example.com/new.png',
                description=None
            )

    @pytest.mark.asyncio
    async def test_chart_remove_command(self, admin_cog, mock_interaction):
        """Test removing a chart via command."""
        await admin_cog.chart_remove.callback(admin_cog, mock_interaction, 'rest')

        # Verify success response
        mock_interaction.response.send_message.assert_called_once()
        call_kwargs = mock_interaction.response.send_message.call_args[1]
        embed = call_kwargs['embed']

        assert '✅ Chart Removed' in embed.title
        assert call_kwargs['ephemeral'] is True

        # Verify chart was removed
        chart = admin_cog.chart_service.get_chart('rest')
        assert chart is None

    @pytest.mark.asyncio
    async def test_chart_remove_not_found(self, admin_cog, mock_interaction):
        """Test removing a non-existent chart."""
        with pytest.raises(BotException, match="not found"):
            await admin_cog.chart_remove.callback(admin_cog, mock_interaction, 'nonexistent')

    @pytest.mark.asyncio
    async def test_chart_list_all(self, admin_cog, mock_interaction):
        """Test listing all charts."""
        await admin_cog.chart_list.callback(admin_cog, mock_interaction, category=None)

        # Verify response
        mock_interaction.response.send_message.assert_called_once()
        call_kwargs = mock_interaction.response.send_message.call_args[1]
        embed = call_kwargs['embed']

        assert '📊 All Available Charts' in embed.title
        assert 'Total: 3 chart(s)' in embed.description

    @pytest.mark.asyncio
    async def test_chart_list_by_category(self, admin_cog, mock_interaction):
        """Test listing charts by category."""
        await admin_cog.chart_list.callback(admin_cog, mock_interaction, category='gameplay')

        # Verify response
        mock_interaction.response.send_message.assert_called_once()
        call_kwargs = mock_interaction.response.send_message.call_args[1]
        embed = call_kwargs['embed']

        assert "Charts in 'gameplay'" in embed.title
        assert 'Total: 2 chart(s)' in embed.description

    @pytest.mark.asyncio
    async def test_chart_update_command(self, admin_cog, mock_interaction):
        """Test updating a chart via command."""
        await admin_cog.chart_update.callback(
            admin_cog,
            mock_interaction,
            key='rest',
            name='Updated Rest Chart',
            category=None,
            url=None,
            description='Updated description'
        )

        # Verify success response
        mock_interaction.response.send_message.assert_called_once()
        call_kwargs = mock_interaction.response.send_message.call_args[1]
        embed = call_kwargs['embed']

        assert '✅ Chart Updated' in embed.title

        # Verify chart was updated
        chart = admin_cog.chart_service.get_chart('rest')
        assert chart.name == 'Updated Rest Chart'
        assert chart.description == 'Updated description'

    @pytest.mark.asyncio
    async def test_chart_update_no_fields(self, admin_cog, mock_interaction):
        """Test updating with no fields raises exception."""
        with pytest.raises(BotException, match="Must provide at least one field"):
            await admin_cog.chart_update.callback(
                admin_cog,
                mock_interaction,
                key='rest',
                name=None,
                category=None,
                url=None,
                description=None
            )

    @pytest.mark.asyncio
    async def test_chart_update_invalid_category(self, admin_cog, mock_interaction):
        """Test updating with invalid category."""
        with pytest.raises(BotException, match="Invalid category"):
            await admin_cog.chart_update.callback(
                admin_cog,
                mock_interaction,
                key='rest',
                name=None,
                category='invalid-category',
                url=None,
                description=None
            )
