"""
Tests for Injury Modal Validation in Discord Bot v2.0

Tests week and game validation for BatterInjuryModal and PitcherRestModal,
including regular season and playoff round validation.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch, PropertyMock
from datetime import datetime, timezone

import discord

from views.modals import BatterInjuryModal, PitcherRestModal
from views.embeds import EmbedTemplate
from models.player import Player


@pytest.fixture
def mock_config():
    """Mock configuration with standard season structure."""
    config = MagicMock()
    config.weeks_per_season = 18
    config.playoff_weeks_per_season = 3
    config.games_per_week = 4
    config.playoff_round_one_games = 5
    config.playoff_round_two_games = 7
    config.playoff_round_three_games = 7
    return config


@pytest.fixture
def sample_player():
    """Create a sample player for testing."""
    return Player(
        id=1,
        name="Test Player",
        wara=2.5,
        season=12,
        team_id=1,
        image="https://example.com/player.jpg",
        pos_1="1B"
    )


@pytest.fixture
def mock_interaction():
    """Create a mock Discord interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    return interaction


def create_mock_text_input(value: str):
    """Create a mock TextInput with a specific value."""
    mock_input = MagicMock()
    type(mock_input).value = PropertyMock(return_value=value)
    return mock_input


class TestBatterInjuryModalWeekValidation:
    """Test week validation in BatterInjuryModal."""

    @pytest.mark.asyncio
    async def test_regular_season_week_valid(self, sample_player, mock_interaction, mock_config):
        """Test that regular season weeks (1-18) are accepted."""
        modal = BatterInjuryModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        # Mock the TextInput values
        modal.current_week = create_mock_text_input("10")
        modal.current_game = create_mock_text_input("2")

        with patch('config.get_config', return_value=mock_config), \
             patch('services.player_service.player_service') as mock_player_service, \
             patch('services.injury_service.injury_service') as mock_injury_service:

            # Mock successful injury creation
            mock_injury_service.create_injury = AsyncMock(return_value=MagicMock(id=1))
            mock_player_service.update_player = AsyncMock()

            await modal.on_submit(mock_interaction)

            # Should not send error message
            assert not any(
                call[1].get('embed') and
                'Invalid Week' in str(call[1]['embed'].title)
                for call in mock_interaction.response.send_message.call_args_list
            )

    @pytest.mark.asyncio
    async def test_playoff_week_19_valid(self, sample_player, mock_interaction, mock_config):
        """Test that playoff week 19 (round 1) is accepted."""
        modal = BatterInjuryModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        modal.current_week = create_mock_text_input("19")
        modal.current_game = create_mock_text_input("3")

        with patch('config.get_config', return_value=mock_config), \
             patch('services.player_service.player_service') as mock_player_service, \
             patch('services.injury_service.injury_service') as mock_injury_service:

            mock_injury_service.create_injury = AsyncMock(return_value=MagicMock(id=1))
            mock_player_service.update_player = AsyncMock()

            await modal.on_submit(mock_interaction)

            # Should not send error message
            assert not any(
                call[1].get('embed') and
                'Invalid Week' in str(call[1]['embed'].title)
                for call in mock_interaction.response.send_message.call_args_list
            )

    @pytest.mark.asyncio
    async def test_playoff_week_21_valid(self, sample_player, mock_interaction, mock_config):
        """Test that playoff week 21 (round 3) is accepted."""
        modal = BatterInjuryModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        modal.current_week = create_mock_text_input("21")
        modal.current_game = create_mock_text_input("5")

        with patch('config.get_config', return_value=mock_config), \
             patch('services.player_service.player_service') as mock_player_service, \
             patch('services.injury_service.injury_service') as mock_injury_service:

            mock_injury_service.create_injury = AsyncMock(return_value=MagicMock(id=1))
            mock_player_service.update_player = AsyncMock()

            await modal.on_submit(mock_interaction)

            # Should not send error message
            assert not any(
                call[1].get('embed') and
                'Invalid Week' in str(call[1]['embed'].title)
                for call in mock_interaction.response.send_message.call_args_list
            )

    @pytest.mark.asyncio
    async def test_week_too_high_rejected(self, sample_player, mock_interaction, mock_config):
        """Test that week > 21 is rejected."""
        modal = BatterInjuryModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        modal.current_week = create_mock_text_input("22")
        modal.current_game = create_mock_text_input("2")

        with patch('config.get_config', return_value=mock_config):
            await modal.on_submit(mock_interaction)

            # Should send error message
            mock_interaction.response.send_message.assert_called_once()
            call_kwargs = mock_interaction.response.send_message.call_args[1]
            assert 'embed' in call_kwargs
            assert 'Invalid Week' in call_kwargs['embed'].title
            assert '21 (including playoffs)' in call_kwargs['embed'].description

    @pytest.mark.asyncio
    async def test_week_zero_rejected(self, sample_player, mock_interaction, mock_config):
        """Test that week 0 is rejected."""
        modal = BatterInjuryModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        modal.current_week = create_mock_text_input("0")
        modal.current_game = create_mock_text_input("2")

        with patch('config.get_config', return_value=mock_config):
            await modal.on_submit(mock_interaction)

            # Should send error message
            mock_interaction.response.send_message.assert_called_once()
            call_kwargs = mock_interaction.response.send_message.call_args[1]
            assert 'embed' in call_kwargs
            assert 'Invalid Week' in call_kwargs['embed'].title


class TestBatterInjuryModalGameValidation:
    """Test game validation in BatterInjuryModal."""

    @pytest.mark.asyncio
    async def test_regular_season_game_4_valid(self, sample_player, mock_interaction, mock_config):
        """Test that game 4 is accepted in regular season."""
        modal = BatterInjuryModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        modal.current_week = create_mock_text_input("10")
        modal.current_game = create_mock_text_input("4")

        with patch('config.get_config', return_value=mock_config), \
             patch('services.player_service.player_service') as mock_player_service, \
             patch('services.injury_service.injury_service') as mock_injury_service:

            mock_injury_service.create_injury = AsyncMock(return_value=MagicMock(id=1))
            mock_player_service.update_player = AsyncMock()

            await modal.on_submit(mock_interaction)

            # Should not send error about invalid game
            assert not any(
                call[1].get('embed') and
                'Invalid Game' in str(call[1]['embed'].title)
                for call in mock_interaction.response.send_message.call_args_list
            )

    @pytest.mark.asyncio
    async def test_regular_season_game_5_rejected(self, sample_player, mock_interaction, mock_config):
        """Test that game 5 is rejected in regular season (only 4 games)."""
        modal = BatterInjuryModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        modal.current_week = create_mock_text_input("10")
        modal.current_game = create_mock_text_input("5")

        with patch('config.get_config', return_value=mock_config):
            await modal.on_submit(mock_interaction)

            # Should send error message
            mock_interaction.response.send_message.assert_called_once()
            call_kwargs = mock_interaction.response.send_message.call_args[1]
            assert 'embed' in call_kwargs
            assert 'Invalid Game' in call_kwargs['embed'].title
            assert 'between 1 and 4' in call_kwargs['embed'].description

    @pytest.mark.asyncio
    async def test_playoff_round_1_game_5_valid(self, sample_player, mock_interaction, mock_config):
        """Test that game 5 is accepted in playoff round 1 (week 19)."""
        modal = BatterInjuryModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        modal.current_week = create_mock_text_input("19")
        modal.current_game = create_mock_text_input("5")

        with patch('config.get_config', return_value=mock_config), \
             patch('services.player_service.player_service') as mock_player_service, \
             patch('services.injury_service.injury_service') as mock_injury_service:

            mock_injury_service.create_injury = AsyncMock(return_value=MagicMock(id=1))
            mock_player_service.update_player = AsyncMock()

            await modal.on_submit(mock_interaction)

            # Should not send error about invalid game
            assert not any(
                call[1].get('embed') and
                'Invalid Game' in str(call[1]['embed'].title)
                for call in mock_interaction.response.send_message.call_args_list
            )

    @pytest.mark.asyncio
    async def test_playoff_round_1_game_6_rejected(self, sample_player, mock_interaction, mock_config):
        """Test that game 6 is rejected in playoff round 1 (only 5 games)."""
        modal = BatterInjuryModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        modal.current_week = create_mock_text_input("19")
        modal.current_game = create_mock_text_input("6")

        with patch('config.get_config', return_value=mock_config):
            await modal.on_submit(mock_interaction)

            # Should send error message
            mock_interaction.response.send_message.assert_called_once()
            call_kwargs = mock_interaction.response.send_message.call_args[1]
            assert 'embed' in call_kwargs
            assert 'Invalid Game' in call_kwargs['embed'].title
            assert 'between 1 and 5' in call_kwargs['embed'].description

    @pytest.mark.asyncio
    async def test_playoff_round_2_game_7_valid(self, sample_player, mock_interaction, mock_config):
        """Test that game 7 is accepted in playoff round 2 (week 20)."""
        modal = BatterInjuryModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        modal.current_week = create_mock_text_input("20")
        modal.current_game = create_mock_text_input("7")

        with patch('config.get_config', return_value=mock_config), \
             patch('services.player_service.player_service') as mock_player_service, \
             patch('services.injury_service.injury_service') as mock_injury_service:

            mock_injury_service.create_injury = AsyncMock(return_value=MagicMock(id=1))
            mock_player_service.update_player = AsyncMock()

            await modal.on_submit(mock_interaction)

            # Should not send error about invalid game
            assert not any(
                call[1].get('embed') and
                'Invalid Game' in str(call[1]['embed'].title)
                for call in mock_interaction.response.send_message.call_args_list
            )

    @pytest.mark.asyncio
    async def test_playoff_round_3_game_7_valid(self, sample_player, mock_interaction, mock_config):
        """Test that game 7 is accepted in playoff round 3 (week 21)."""
        modal = BatterInjuryModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        modal.current_week = create_mock_text_input("21")
        modal.current_game = create_mock_text_input("7")

        with patch('config.get_config', return_value=mock_config), \
             patch('services.player_service.player_service') as mock_player_service, \
             patch('services.injury_service.injury_service') as mock_injury_service:

            mock_injury_service.create_injury = AsyncMock(return_value=MagicMock(id=1))
            mock_player_service.update_player = AsyncMock()

            await modal.on_submit(mock_interaction)

            # Should not send error about invalid game
            assert not any(
                call[1].get('embed') and
                'Invalid Game' in str(call[1]['embed'].title)
                for call in mock_interaction.response.send_message.call_args_list
            )


class TestPitcherRestModalValidation:
    """Test week and game validation in PitcherRestModal (should match BatterInjuryModal)."""

    @pytest.mark.asyncio
    async def test_playoff_week_19_valid(self, sample_player, mock_interaction, mock_config):
        """Test that playoff week 19 is accepted for pitchers."""
        modal = PitcherRestModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        modal.current_week = create_mock_text_input("19")
        modal.current_game = create_mock_text_input("3")
        modal.rest_games = create_mock_text_input("2")

        with patch('config.get_config', return_value=mock_config), \
             patch('services.player_service.player_service') as mock_player_service, \
             patch('services.injury_service.injury_service') as mock_injury_service:

            mock_injury_service.create_injury = AsyncMock(return_value=MagicMock(id=1))
            mock_player_service.update_player = AsyncMock()

            await modal.on_submit(mock_interaction)

            # Should not send error about invalid week
            assert not any(
                call[1].get('embed') and
                'Invalid Week' in str(call[1]['embed'].title)
                for call in mock_interaction.response.send_message.call_args_list
            )

    @pytest.mark.asyncio
    async def test_week_22_rejected(self, sample_player, mock_interaction, mock_config):
        """Test that week 22 is rejected for pitchers."""
        modal = PitcherRestModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        modal.current_week = create_mock_text_input("22")
        modal.current_game = create_mock_text_input("2")
        modal.rest_games = create_mock_text_input("2")

        with patch('config.get_config', return_value=mock_config):
            await modal.on_submit(mock_interaction)

            # Should send error message
            mock_interaction.response.send_message.assert_called_once()
            call_kwargs = mock_interaction.response.send_message.call_args[1]
            assert 'embed' in call_kwargs
            assert 'Invalid Week' in call_kwargs['embed'].title
            assert '21 (including playoffs)' in call_kwargs['embed'].description

    @pytest.mark.asyncio
    async def test_playoff_round_2_game_7_valid(self, sample_player, mock_interaction, mock_config):
        """Test that game 7 is accepted in playoff round 2 for pitchers."""
        modal = PitcherRestModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        modal.current_week = create_mock_text_input("20")
        modal.current_game = create_mock_text_input("7")
        modal.rest_games = create_mock_text_input("3")

        with patch('config.get_config', return_value=mock_config), \
             patch('services.player_service.player_service') as mock_player_service, \
             patch('services.injury_service.injury_service') as mock_injury_service:

            mock_injury_service.create_injury = AsyncMock(return_value=MagicMock(id=1))
            mock_player_service.update_player = AsyncMock()

            await modal.on_submit(mock_interaction)

            # Should not send error about invalid game
            assert not any(
                call[1].get('embed') and
                'Invalid Game' in str(call[1]['embed'].title)
                for call in mock_interaction.response.send_message.call_args_list
            )

    @pytest.mark.asyncio
    async def test_playoff_round_1_game_6_rejected(self, sample_player, mock_interaction, mock_config):
        """Test that game 6 is rejected in playoff round 1 for pitchers (only 5 games)."""
        modal = PitcherRestModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        modal.current_week = create_mock_text_input("19")
        modal.current_game = create_mock_text_input("6")
        modal.rest_games = create_mock_text_input("2")

        with patch('config.get_config', return_value=mock_config):
            await modal.on_submit(mock_interaction)

            # Should send error message
            mock_interaction.response.send_message.assert_called_once()
            call_kwargs = mock_interaction.response.send_message.call_args[1]
            assert 'embed' in call_kwargs
            assert 'Invalid Game' in call_kwargs['embed'].title
            assert 'between 1 and 5' in call_kwargs['embed'].description


class TestConfigDrivenValidation:
    """Test that validation correctly uses config values."""

    @pytest.mark.asyncio
    async def test_custom_config_values_respected(self, sample_player, mock_interaction):
        """Test that custom config values change validation behavior."""
        # Create config with different values
        custom_config = MagicMock()
        custom_config.weeks_per_season = 20  # Different from default
        custom_config.playoff_weeks_per_season = 2  # Different from default
        custom_config.games_per_week = 4
        custom_config.playoff_round_one_games = 5
        custom_config.playoff_round_two_games = 7
        custom_config.playoff_round_three_games = 7

        modal = BatterInjuryModal(
            player=sample_player,
            injury_games=4,
            season=12
        )

        # Week 22 should be valid with this config (20 + 2 = 22)
        modal.current_week = create_mock_text_input("22")
        modal.current_game = create_mock_text_input("3")

        with patch('config.get_config', return_value=custom_config), \
             patch('services.player_service.player_service') as mock_player_service, \
             patch('services.injury_service.injury_service') as mock_injury_service:

            mock_injury_service.create_injury = AsyncMock(return_value=MagicMock(id=1))
            mock_player_service.update_player = AsyncMock()

            await modal.on_submit(mock_interaction)

            # Should not send error about invalid week
            assert not any(
                call[1].get('embed') and
                'Invalid Week' in str(call[1]['embed'].title)
                for call in mock_interaction.response.send_message.call_args_list
            )
