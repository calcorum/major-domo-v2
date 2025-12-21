"""
Tests for /dropadd Discord Commands

Validates the Discord command interface, autocomplete, and user interactions.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord import app_commands

from commands.transactions.dropadd import DropAddCommands
from services.transaction_builder import TransactionBuilder
from models.team import RosterType
from models.team import Team
from models.player import Player
from tests.factories import PlayerFactory, TeamFactory


class TestDropAddCommands:
    """Test DropAddCommands Discord command functionality."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create mock Discord bot."""
        bot = MagicMock()
        bot.user = MagicMock()
        bot.user.id = 123456789
        return bot
    
    @pytest.fixture
    def commands_cog(self, mock_bot):
        """Create DropAddCommands cog instance."""
        return DropAddCommands(mock_bot)
    
    @pytest.fixture
    def mock_interaction(self):
        """Create mock Discord interaction."""
        interaction = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 258104532423147520
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.client = MagicMock()
        interaction.client.user = MagicMock()
        interaction.channel = MagicMock()
        # Guild mock required for @league_only decorator
        interaction.guild = MagicMock()
        interaction.guild.id = 669356687294988350  # Test guild ID matching config
        return interaction
    
    @pytest.fixture
    def mock_team(self):
        """Create mock team data."""
        return TeamFactory.west_virginia()
    
    @pytest.fixture
    def mock_player(self):
        """Create mock player data."""
        return PlayerFactory.mike_trout()
    
    @pytest.mark.asyncio
    async def test_player_autocomplete_success(self, commands_cog, mock_interaction):
        """Test successful player autocomplete."""
        mock_players = [
            PlayerFactory.mike_trout(id=1),
            PlayerFactory.ronald_acuna(id=2)
        ]

        with patch('utils.autocomplete.player_service') as mock_service:
            mock_service.search_players = AsyncMock(return_value=mock_players)

            from utils.autocomplete import player_autocomplete
            choices = await player_autocomplete(mock_interaction, 'Trout')

            assert len(choices) == 2
            assert choices[0].name == 'Mike Trout (CF)'
            assert choices[0].value == 'Mike Trout'
            assert choices[1].name == 'Ronald Acuna Jr. (OF)'
            assert choices[1].value == 'Ronald Acuna Jr.'
    
    @pytest.mark.asyncio
    async def test_player_autocomplete_with_team(self, commands_cog, mock_interaction):
        """Test player autocomplete with team information."""
        mock_team = TeamFactory.create(id=499, abbrev='LAA', sname='Angels', lname='Los Angeles Angels')
        mock_player = PlayerFactory.mike_trout(id=1)
        mock_player.team = mock_team  # Add team info

        with patch('utils.autocomplete.player_service') as mock_service:
            mock_service.search_players = AsyncMock(return_value=[mock_player])

            from utils.autocomplete import player_autocomplete
            choices = await player_autocomplete(mock_interaction, 'Trout')

            assert len(choices) == 1
            assert choices[0].name == 'Mike Trout (CF - LAA)'
            assert choices[0].value == 'Mike Trout'
    
    @pytest.mark.asyncio
    async def test_player_autocomplete_short_input(self, commands_cog, mock_interaction):
        """Test player autocomplete with short input returns empty."""
        from utils.autocomplete import player_autocomplete
        choices = await player_autocomplete(mock_interaction, 'T')
        assert len(choices) == 0
    
    @pytest.mark.asyncio
    async def test_player_autocomplete_error_handling(self, commands_cog, mock_interaction):
        """Test player autocomplete error handling."""
        with patch('utils.autocomplete.player_service') as mock_service:
            mock_service.search_players.side_effect = Exception("API Error")

            from utils.autocomplete import player_autocomplete
            choices = await player_autocomplete(mock_interaction, 'Trout')
            assert len(choices) == 0
    
    @pytest.mark.asyncio
    async def test_dropadd_command_no_team(self, commands_cog, mock_interaction):
        """Test /dropadd command when user has no team."""
        with patch('commands.transactions.dropadd.validate_user_has_team') as mock_validate:
            mock_validate.return_value = None
            await commands_cog.dropadd.callback(commands_cog, mock_interaction)

            mock_interaction.response.defer.assert_called_once()
            # validate_user_has_team sends its own error message, command just returns
            mock_validate.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_dropadd_command_success_no_params(self, commands_cog, mock_interaction, mock_team):
        """Test /dropadd command success without parameters."""
        with patch('commands.transactions.dropadd.validate_user_has_team') as mock_validate:
            with patch('commands.transactions.dropadd.get_transaction_builder') as mock_get_builder:
                with patch('commands.transactions.dropadd.create_transaction_embed') as mock_create_embed:
                    mock_validate.return_value = mock_team

                    mock_builder = MagicMock()
                    mock_builder.team = mock_team
                    mock_get_builder.return_value = mock_builder

                    mock_embed = MagicMock()
                    mock_create_embed.return_value = mock_embed

                    await commands_cog.dropadd.callback(commands_cog, mock_interaction)

                    # Verify flow
                    mock_interaction.response.defer.assert_called_once()
                    mock_validate.assert_called_once_with(mock_interaction)
                    mock_get_builder.assert_called_once_with(mock_interaction.user.id, mock_team)
                    mock_create_embed.assert_called_once_with(mock_builder, command_name='/dropadd')
                    mock_interaction.followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_dropadd_command_with_quick_move(self, commands_cog, mock_interaction, mock_team):
        """Test /dropadd command with quick move parameters."""
        with patch('commands.transactions.dropadd.validate_user_has_team') as mock_validate:
            with patch('commands.transactions.dropadd.get_transaction_builder') as mock_get_builder:
                with patch.object(commands_cog, '_add_quick_move') as mock_add_quick:
                    with patch('commands.transactions.dropadd.create_transaction_embed') as mock_create_embed:
                        mock_validate.return_value = mock_team

                        mock_builder = MagicMock()
                        mock_builder.move_count = 1
                        mock_get_builder.return_value = mock_builder
                        mock_add_quick.return_value = (True, "")
                        mock_create_embed.return_value = MagicMock()

                        await commands_cog.dropadd.callback(commands_cog,
                            mock_interaction,
                            player='Mike Trout',
                            destination='ml'
                        )

                        # Verify quick move was attempted
                        mock_add_quick.assert_called_once_with(
                            mock_builder, 'Mike Trout', 'ml'
                        )
    
    @pytest.mark.asyncio
    async def test_add_quick_move_success(self, commands_cog, mock_team, mock_player):
        """Test successful quick move addition."""
        mock_builder = MagicMock()
        mock_builder.team = mock_team
        mock_builder.add_move = AsyncMock(return_value=(True, ""))  # Now async
        mock_builder.load_roster_data = AsyncMock()
        mock_builder._current_roster = MagicMock()
        mock_builder._current_roster.active_players = []
        mock_builder._current_roster.minor_league_players = []
        mock_builder._current_roster.il_players = []

        with patch('commands.transactions.dropadd.player_service') as mock_service:
            mock_service.search_players = AsyncMock(return_value=[mock_player])

            success, error_message = await commands_cog._add_quick_move(
                mock_builder, 'Mike Trout', 'ml'
            )

            assert success is True
            assert error_message == ""
            mock_service.search_players.assert_called_once_with('Mike Trout', limit=10, season=13)
            mock_builder.add_move.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_quick_move_player_not_found(self, commands_cog, mock_team):
        """Test quick move when player not found."""
        mock_builder = MagicMock()
        mock_builder.team = mock_team
        
        with patch('commands.transactions.dropadd.player_service') as mock_service:
            mock_service.search_players = AsyncMock(return_value=[])
            
            success, error_message = await commands_cog._add_quick_move(
                mock_builder, 'Nonexistent Player', 'ml'
            )

            assert success is False
            assert "not found" in error_message
    
    @pytest.mark.asyncio
    async def test_add_quick_move_invalid_action(self, commands_cog, mock_team, mock_player):
        """Test quick move with invalid action."""
        mock_builder = MagicMock()
        mock_builder.team = mock_team

        with patch('commands.transactions.dropadd.player_service') as mock_service:
            mock_service.search_players = AsyncMock(return_value=[mock_player])

            success, error_message = await commands_cog._add_quick_move(
                mock_builder, 'Mike Trout', 'invalid_destination'
            )

            assert success is False
            assert "Invalid destination" in error_message

    @pytest.mark.asyncio
    async def test_add_quick_move_player_from_other_team(self, commands_cog, mock_team):
        """Test quick move when player belongs to another team."""
        mock_builder = MagicMock()
        mock_builder.team = mock_team  # West Virginia (team_id=499)

        # Create a player from another team (not Free Agency)
        other_team = MagicMock()
        other_team.id = 100  # Different team
        other_team.abbrev = "LAA"  # Not 'FA'

        mock_player = MagicMock()
        mock_player.name = "Mike Trout"
        mock_player.team = other_team

        with patch('commands.transactions.dropadd.player_service') as mock_service:
            mock_service.search_players = AsyncMock(return_value=[mock_player])

            success, error_message = await commands_cog._add_quick_move(
                mock_builder, 'Mike Trout', 'ml'
            )

            assert success is False
            assert "belongs to LAA" in error_message
            assert "cannot be added to your transaction" in error_message

    @pytest.mark.asyncio
    async def test_add_quick_move_free_agent_allowed(self, commands_cog, mock_team):
        """Test quick move when player is a Free Agent (should be allowed)."""
        from tests.factories import PlayerFactory, TeamFactory

        mock_builder = MagicMock()
        mock_builder.team = mock_team
        mock_builder.add_move = AsyncMock(return_value=(True, ""))  # Now async
        mock_builder.load_roster_data = AsyncMock()
        mock_builder._current_roster = MagicMock()
        mock_builder._current_roster.active_players = []
        mock_builder._current_roster.minor_league_players = []
        mock_builder._current_roster.il_players = []

        # Create a Free Agent team and player
        fa_team = TeamFactory.create(id=1, abbrev="FA", sname="Free Agency", lname="Free Agency")
        fa_player = PlayerFactory.create(id=12472, name="Mike Trout", team_id=1)
        fa_player.team = fa_team

        with patch('commands.transactions.dropadd.player_service') as mock_service:
            mock_service.search_players = AsyncMock(return_value=[fa_player])

            success, error_message = await commands_cog._add_quick_move(
                mock_builder, 'Mike Trout', 'ml'
            )

            assert success is True
            assert error_message == ""

    # TODO: These tests are for obsolete MoveAction-based functionality
    # The transaction system now uses from_roster/to_roster directly
    # def test_determine_roster_types_add(self, commands_cog):
    # def test_determine_roster_types_drop(self, commands_cog):
    # def test_determine_roster_types_recall(self, commands_cog):
    # def test_determine_roster_types_demote(self, commands_cog):
    pass  # Placeholder
    
    @pytest.mark.asyncio
    async def test_clear_transaction_command(self, commands_cog, mock_interaction):
        """Test /cleartransaction command."""
        with patch('commands.transactions.dropadd.clear_transaction_builder') as mock_clear:
            await commands_cog.clear_transaction.callback(commands_cog, mock_interaction)
            
            mock_clear.assert_called_once_with(mock_interaction.user.id)
            mock_interaction.response.send_message.assert_called_once()
            
            # Check success message
            call_args = mock_interaction.response.send_message.call_args
            assert "transaction builder has been cleared" in call_args[0][0]
            assert call_args[1]['ephemeral'] is True
    

    @pytest.mark.asyncio
    async def test_dropadd_first_move_shows_full_embed(self, commands_cog, mock_interaction, mock_team):
        """Test /dropadd command with first move shows full interactive embed."""
        with patch('commands.transactions.dropadd.validate_user_has_team') as mock_validate:
            with patch('commands.transactions.dropadd.get_transaction_builder') as mock_get_builder:
                with patch.object(commands_cog, '_add_quick_move') as mock_add_quick:
                    with patch('commands.transactions.dropadd.create_transaction_embed') as mock_create_embed:
                        mock_validate.return_value = mock_team

                        # Create empty builder (first move)
                        mock_builder = MagicMock()
                        mock_builder.is_empty = True
                        mock_builder.move_count = 1
                        mock_get_builder.return_value = mock_builder
                        mock_add_quick.return_value = (True, "")
                        mock_create_embed.return_value = MagicMock()

                        await commands_cog.dropadd.callback(commands_cog,
                            mock_interaction,
                            player='Mike Trout',
                            destination='ml'
                        )

                        # Should show full embed with view (now ephemeral)
                        mock_interaction.followup.send.assert_called_once()
                        call_args = mock_interaction.followup.send.call_args
                        assert call_args[1]['ephemeral'] is True
                        assert 'embed' in call_args[1]
                        assert 'view' in call_args[1]
                        assert 'content' in call_args[1]

    @pytest.mark.asyncio
    async def test_dropadd_append_mode_shows_confirmation(self, commands_cog, mock_interaction, mock_team):
        """Test /dropadd command in append mode shows ephemeral confirmation."""
        with patch('commands.transactions.dropadd.validate_user_has_team') as mock_validate:
            with patch('commands.transactions.dropadd.get_transaction_builder') as mock_get_builder:
                with patch.object(commands_cog, '_add_quick_move') as mock_add_quick:
                    mock_validate.return_value = mock_team

                    # Create builder with existing moves (append mode)
                    mock_builder = MagicMock()
                    mock_builder.is_empty = False
                    mock_builder.move_count = 2
                    mock_builder.validate_transaction = AsyncMock(return_value=MagicMock(
                        is_legal=True,
                        major_league_count=25,
                        minor_league_count=10,
                        warnings=[],
                        errors=[],
                        suggestions=[]
                    ))
                    mock_get_builder.return_value = mock_builder
                    mock_add_quick.return_value = (True, "")

                    with patch('commands.transactions.dropadd.create_transaction_embed') as mock_create_embed:
                        mock_create_embed.return_value = MagicMock()

                        await commands_cog.dropadd.callback(commands_cog,
                            mock_interaction,
                            player='Kevin Ginkel',
                            destination='ml'
                        )

                        # Should show embed with ephemeral confirmation
                        mock_interaction.followup.send.assert_called_once()
                        call_args = mock_interaction.followup.send.call_args
                        assert call_args[1]['ephemeral'] is True
                        assert 'embed' in call_args[1]
                        assert 'view' in call_args[1]
                        content = call_args[1]['content']
                        assert "Added Kevin Ginkel → ML" in content
                        assert "Transaction now has 2 moves" in content


class TestDropAddCommandsIntegration:
    """Integration tests for dropadd commands with real-like data flows."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create mock Discord bot."""
        return MagicMock()
    
    @pytest.fixture
    def commands_cog(self, mock_bot):
        """Create DropAddCommands cog instance."""
        return DropAddCommands(mock_bot)
    
    @pytest.mark.asyncio
    async def test_full_dropadd_workflow(self, commands_cog):
        """Test complete dropadd workflow from command to builder creation."""
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456789
        # Add guild mock for @league_only decorator
        mock_interaction.guild = MagicMock()
        mock_interaction.guild.id = 669356687294988350

        mock_team = TeamFactory.west_virginia()

        mock_player = PlayerFactory.mike_trout(id=12472)

        with patch('commands.transactions.dropadd.validate_user_has_team') as mock_validate:
            with patch('commands.transactions.dropadd.player_service') as mock_player_service:
                with patch('commands.transactions.dropadd.get_transaction_builder') as mock_get_builder:
                    with patch('commands.transactions.dropadd.create_transaction_embed') as mock_create_embed:
                        # Setup mocks
                        mock_validate.return_value = mock_team
                        mock_player_service.search_players = AsyncMock(return_value=[mock_player])

                        mock_builder = TransactionBuilder(mock_team, 123456789, 13)
                        mock_get_builder.return_value = mock_builder

                        # Mock the async function
                        async def mock_create_embed_func(builder, command_name=None):
                            return MagicMock()
                        mock_create_embed.side_effect = mock_create_embed_func

                        # Execute command with parameters
                        await commands_cog.dropadd.callback(commands_cog,
                            mock_interaction,
                            player='Mike Trout',
                            destination='ml'
                        )

                        # Verify the builder has the move
                        assert mock_builder.move_count == 1
                        move = mock_builder.moves[0]
                        assert move.player == mock_player
                        # Note: TransactionMove no longer has 'action' field - uses from_roster/to_roster instead
                        assert move.to_roster == RosterType.MAJOR_LEAGUE
    
    @pytest.mark.asyncio
    async def test_error_recovery_in_workflow(self, commands_cog):
        """Test error recovery in dropadd workflow."""
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456789
        # Add guild mock for @league_only decorator
        mock_interaction.guild = MagicMock()
        mock_interaction.guild.id = 669356687294988350

        with patch('commands.transactions.dropadd.validate_user_has_team') as mock_validate:
            # Simulate API error
            mock_validate.side_effect = Exception("API Error")

            # Exception should be raised (logged_command decorator re-raises)
            with pytest.raises(Exception, match="API Error"):
                await commands_cog.dropadd.callback(commands_cog, mock_interaction)

            # Should have deferred before the error occurred
            mock_interaction.response.defer.assert_called_once()