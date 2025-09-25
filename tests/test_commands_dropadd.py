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
        return interaction
    
    @pytest.fixture
    def mock_team(self):
        """Create mock team data."""
        return Team(
            id=499,
            abbrev='WV',
            sname='Black Bears',
            lname='West Virginia Black Bears',
            season=12
        )
    
    @pytest.fixture
    def mock_player(self):
        """Create mock player data."""
        return Player(
            id=12472,
            name='Mike Trout',
            season=12,
            primary_position='CF'
        )
    
    @pytest.mark.asyncio
    async def test_player_autocomplete_success(self, commands_cog, mock_interaction):
        """Test successful player autocomplete."""
        mock_players = [
            Player(id=1, name='Mike Trout', season=12, primary_position='CF'),
            Player(id=2, name='Ronald Acuna Jr.', season=12, primary_position='OF')
        ]
        
        with patch('commands.transactions.dropadd.player_service') as mock_service:
            mock_service.get_players_by_name.return_value = mock_players
            
            choices = await commands_cog.player_autocomplete(mock_interaction, 'Trout')
            
            assert len(choices) == 2
            assert choices[0].name == 'Mike Trout (CF)'
            assert choices[0].value == 'Mike Trout'
            assert choices[1].name == 'Ronald Acuna Jr. (OF)'
            assert choices[1].value == 'Ronald Acuna Jr.'
    
    @pytest.mark.asyncio
    async def test_player_autocomplete_with_team(self, commands_cog, mock_interaction):
        """Test player autocomplete with team information."""
        mock_team = Team(id=499, abbrev='LAA', sname='Angels', lname='Los Angeles Angels', season=12)
        mock_player = Player(
            id=1, 
            name='Mike Trout', 
            season=12, 
            primary_position='CF'
        )
        mock_player.team = mock_team  # Add team info
        
        with patch('commands.transactions.dropadd.player_service') as mock_service:
            mock_service.get_players_by_name.return_value = [mock_player]
            
            choices = await commands_cog.player_autocomplete(mock_interaction, 'Trout')
            
            assert len(choices) == 1
            assert choices[0].name == 'Mike Trout (CF - LAA)'
            assert choices[0].value == 'Mike Trout'
    
    @pytest.mark.asyncio
    async def test_player_autocomplete_short_input(self, commands_cog, mock_interaction):
        """Test player autocomplete with short input returns empty."""
        choices = await commands_cog.player_autocomplete(mock_interaction, 'T')
        assert len(choices) == 0
    
    @pytest.mark.asyncio
    async def test_player_autocomplete_error_handling(self, commands_cog, mock_interaction):
        """Test player autocomplete error handling."""
        with patch('commands.transactions.dropadd.player_service') as mock_service:
            mock_service.get_players_by_name.side_effect = Exception("API Error")
            
            choices = await commands_cog.player_autocomplete(mock_interaction, 'Trout')
            assert len(choices) == 0
    
    @pytest.mark.asyncio
    async def test_dropadd_command_no_team(self, commands_cog, mock_interaction):
        """Test /dropadd command when user has no team."""
        with patch('commands.transactions.dropadd.team_service') as mock_service:
            mock_service.get_teams_by_owner.return_value = []
            
            await commands_cog.dropadd(mock_interaction)
            
            mock_interaction.response.defer.assert_called_once()
            mock_interaction.followup.send.assert_called_once()
            
            # Check error message
            call_args = mock_interaction.followup.send.call_args
            assert "don't appear to own a team" in call_args[0][0]
            assert call_args[1]['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_dropadd_command_success_no_params(self, commands_cog, mock_interaction, mock_team):
        """Test /dropadd command success without parameters."""
        with patch('commands.transactions.dropadd.team_service') as mock_team_service:
            with patch('commands.transactions.dropadd.get_transaction_builder') as mock_get_builder:
                with patch('commands.transactions.dropadd.create_transaction_embed') as mock_create_embed:
                    mock_team_service.get_teams_by_owner.return_value = [mock_team]
                    
                    mock_builder = MagicMock()
                    mock_builder.team = mock_team
                    mock_get_builder.return_value = mock_builder
                    
                    mock_embed = MagicMock()
                    mock_create_embed.return_value = mock_embed
                    
                    await commands_cog.dropadd(mock_interaction)
                    
                    # Verify flow
                    mock_interaction.response.defer.assert_called_once()
                    mock_team_service.get_teams_by_owner.assert_called_once_with(
                        mock_interaction.user.id, 12
                    )
                    mock_get_builder.assert_called_once_with(mock_interaction.user.id, mock_team)
                    mock_create_embed.assert_called_once_with(mock_builder)
                    mock_interaction.followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_dropadd_command_with_quick_move(self, commands_cog, mock_interaction, mock_team):
        """Test /dropadd command with quick move parameters."""
        with patch('commands.transactions.dropadd.team_service') as mock_team_service:
            with patch('commands.transactions.dropadd.get_transaction_builder') as mock_get_builder:
                with patch.object(commands_cog, '_add_quick_move') as mock_add_quick:
                    with patch('commands.transactions.dropadd.create_transaction_embed') as mock_create_embed:
                        mock_team_service.get_teams_by_owner.return_value = [mock_team]
                        
                        mock_builder = MagicMock()
                        mock_get_builder.return_value = mock_builder
                        mock_add_quick.return_value = True
                        mock_create_embed.return_value = MagicMock()
                        
                        await commands_cog.dropadd(
                            mock_interaction, 
                            player='Mike Trout',
                            action='add',
                            destination='ml'
                        )
                        
                        # Verify quick move was attempted
                        mock_add_quick.assert_called_once_with(
                            mock_builder, 'Mike Trout', 'add', 'ml'
                        )
    
    @pytest.mark.asyncio
    async def test_add_quick_move_success(self, commands_cog, mock_team, mock_player):
        """Test successful quick move addition."""
        mock_builder = MagicMock()
        mock_builder.team = mock_team
        mock_builder.add_move.return_value = True
        
        with patch('commands.transactions.dropadd.player_service') as mock_service:
            mock_service.get_players_by_name.return_value = [mock_player]
            
            success = await commands_cog._add_quick_move(
                mock_builder, 'Mike Trout', 'add', 'ml'
            )
            
            assert success is True
            mock_service.get_players_by_name.assert_called_once_with('Mike Trout', 12)
            mock_builder.add_move.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_quick_move_player_not_found(self, commands_cog, mock_team):
        """Test quick move when player not found."""
        mock_builder = MagicMock()
        mock_builder.team = mock_team
        
        with patch('commands.transactions.dropadd.player_service') as mock_service:
            mock_service.get_players_by_name.return_value = []
            
            success = await commands_cog._add_quick_move(
                mock_builder, 'Nonexistent Player', 'add', 'ml'
            )
            
            assert success is False
    
    @pytest.mark.asyncio
    async def test_add_quick_move_invalid_action(self, commands_cog, mock_team):
        """Test quick move with invalid action."""
        mock_builder = MagicMock()
        mock_builder.team = mock_team
        
        success = await commands_cog._add_quick_move(
            mock_builder, 'Mike Trout', 'invalid_action', 'ml'
        )
        
        assert success is False
    
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
            await commands_cog.clear_transaction(mock_interaction)
            
            mock_clear.assert_called_once_with(mock_interaction.user.id)
            mock_interaction.response.send_message.assert_called_once()
            
            # Check success message
            call_args = mock_interaction.response.send_message.call_args
            assert "transaction builder has been cleared" in call_args[0][0]
            assert call_args[1]['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_transaction_status_no_team(self, commands_cog, mock_interaction):
        """Test /transactionstatus when user has no team."""
        with patch('commands.transactions.dropadd.team_service') as mock_service:
            mock_service.get_teams_by_owner.return_value = []
            
            await commands_cog.transaction_status(mock_interaction)
            
            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_interaction.followup.send.assert_called_once()
            
            call_args = mock_interaction.followup.send.call_args
            assert "don't appear to own a team" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_transaction_status_empty_builder(self, commands_cog, mock_interaction, mock_team):
        """Test /transactionstatus with empty builder."""
        with patch('commands.transactions.dropadd.team_service') as mock_team_service:
            with patch('commands.transactions.dropadd.get_transaction_builder') as mock_get_builder:
                mock_team_service.get_teams_by_owner.return_value = [mock_team]
                
                mock_builder = MagicMock()
                mock_builder.is_empty = True
                mock_get_builder.return_value = mock_builder
                
                await commands_cog.transaction_status(mock_interaction)
                
                call_args = mock_interaction.followup.send.call_args
                assert "transaction builder is empty" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_transaction_status_with_moves(self, commands_cog, mock_interaction, mock_team):
        """Test /transactionstatus with moves in builder."""
        from services.transaction_builder import RosterValidationResult
        
        with patch('commands.transactions.dropadd.team_service') as mock_team_service:
            with patch('commands.transactions.dropadd.get_transaction_builder') as mock_get_builder:
                mock_team_service.get_teams_by_owner.return_value = [mock_team]
                
                mock_builder = MagicMock()
                mock_builder.is_empty = False
                mock_builder.move_count = 2
                mock_builder.validate_transaction = AsyncMock(return_value=RosterValidationResult(
                    is_legal=True,
                    major_league_count=25,
                    minor_league_count=10,
                    warnings=[],
                    errors=[],
                    suggestions=[]
                ))
                mock_get_builder.return_value = mock_builder
                
                await commands_cog.transaction_status(mock_interaction)
                
                call_args = mock_interaction.followup.send.call_args
                status_msg = call_args[0][0]
                assert "Moves:** 2" in status_msg
                assert "✅ Legal" in status_msg


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
        
        mock_team = Team(
            id=499,
            abbrev='WV', 
            sname='Black Bears',
            lname='West Virginia Black Bears',
            season=12
        )
        
        mock_player = Player(
            id=12472,
            name='Mike Trout',
            season=12,
            primary_position='CF'
        )
        
        with patch('commands.transactions.dropadd.team_service') as mock_team_service:
            with patch('commands.transactions.dropadd.player_service') as mock_player_service:
                with patch('commands.transactions.dropadd.get_transaction_builder') as mock_get_builder:
                    with patch('commands.transactions.dropadd.create_transaction_embed') as mock_create_embed:
                        # Setup mocks
                        mock_team_service.get_teams_by_owner.return_value = [mock_team]
                        mock_player_service.get_players_by_name.return_value = [mock_player]
                        
                        mock_builder = TransactionBuilder(mock_team, 123456789, 12)
                        mock_get_builder.return_value = mock_builder
                        mock_create_embed.return_value = MagicMock()
                        
                        # Execute command with parameters
                        await commands_cog.dropadd(
                            mock_interaction,
                            player='Mike Trout',
                            action='add',
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
        
        with patch('commands.transactions.dropadd.team_service') as mock_service:
            # Simulate API error
            mock_service.get_teams_by_owner.side_effect = Exception("API Error")
            
            # Should not raise exception, should handle gracefully
            await commands_cog.dropadd(mock_interaction)
            
            # Should have deferred and attempted to send error (which will also fail gracefully)
            mock_interaction.response.defer.assert_called_once()