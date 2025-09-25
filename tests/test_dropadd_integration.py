"""
Integration tests for /dropadd functionality

Tests complete workflows from command invocation through transaction submission.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from commands.transactions.dropadd import DropAddCommands
from services.transaction_builder import (
    TransactionBuilder,
    TransactionMove,
    get_transaction_builder,
    clear_transaction_builder
)
from models.team import RosterType
from views.transaction_embed import (
    TransactionEmbedView,
    PlayerSelectionModal,
    SubmitConfirmationModal
)
from models.team import Team
from models.player import Player
from models.roster import TeamRoster, RosterPlayer
from models.transaction import Transaction
from models.current import Current


class TestDropAddIntegration:
    """Integration tests for complete /dropadd workflows."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create mock Discord bot."""
        return MagicMock()
    
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
        
        # Mock message history for embed updates
        mock_message = MagicMock()
        mock_message.author = interaction.client.user
        mock_message.embeds = [MagicMock()]
        mock_message.embeds[0].title = "📋 Transaction Builder"
        mock_message.edit = AsyncMock()
        
        interaction.channel.history.return_value.__aiter__ = AsyncMock(return_value=iter([mock_message]))
        
        return interaction
    
    @pytest.fixture
    def mock_team(self):
        """Create mock team."""
        return Team(
            id=499,
            abbrev='WV',
            sname='Black Bears',
            lname='West Virginia Black Bears',
            season=12
        )
    
    @pytest.fixture
    def mock_players(self):
        """Create mock players."""
        return [
            Player(id=12472, name='Mike Trout', season=12, primary_position='CF'),
            Player(id=12473, name='Ronald Acuna Jr.', season=12, primary_position='OF'),
            Player(id=12474, name='Mookie Betts', season=12, primary_position='RF')
        ]
    
    @pytest.fixture
    def mock_roster(self):
        """Create mock team roster."""
        # Create 24 ML players (under limit)
        ml_players = []
        for i in range(24):
            ml_players.append(RosterPlayer(
                id=1000 + i,
                name=f'ML Player {i}',
                season=12,
                primary_position='OF',
                is_minor_league=False
            ))
        
        # Create 10 MiL players
        mil_players = []
        for i in range(10):
            mil_players.append(RosterPlayer(
                id=2000 + i,
                name=f'MiL Player {i}',
                season=12,
                primary_position='OF',
                is_minor_league=True
            ))
        
        return TeamRoster(
            team_id=499,
            week=10,
            season=12,
            players=ml_players + mil_players
        )
    
    @pytest.fixture
    def mock_current_state(self):
        """Create mock current league state."""
        return Current(
            week=10,
            season=12,
            freeze=False
        )
    
    @pytest.mark.asyncio
    async def test_complete_single_move_workflow(self, commands_cog, mock_interaction, mock_team, mock_players, mock_roster):
        """Test complete workflow for single move transaction."""
        # Clear any existing builders
        clear_transaction_builder(mock_interaction.user.id)
        
        with patch('commands.transactions.dropadd.team_service') as mock_team_service:
            with patch('commands.transactions.dropadd.player_service') as mock_player_service:
                with patch('services.transaction_builder.roster_service') as mock_roster_service:
                    # Setup mocks
                    mock_team_service.get_teams_by_owner.return_value = [mock_team]
                    mock_player_service.get_players_by_name.return_value = [mock_players[0]]  # Mike Trout
                    mock_roster_service.get_current_roster.return_value = mock_roster
                    
                    # Execute /dropadd command with quick move
                    await commands_cog.dropadd(
                        mock_interaction,
                        player='Mike Trout',
                        action='add',
                        destination='ml'
                    )
                    
                    # Verify command execution
                    mock_interaction.response.defer.assert_called_once()
                    mock_interaction.followup.send.assert_called_once()
                    
                    # Get the builder that was created
                    builder = get_transaction_builder(mock_interaction.user.id, mock_team)
                    
                    # Verify the move was added
                    assert builder.move_count == 1
                    move = builder.moves[0]
                    assert move.player.name == 'Mike Trout'
                    # Note: TransactionMove no longer has 'action' field
                    assert move.to_roster == RosterType.MAJOR_LEAGUE
                    
                    # Verify roster validation
                    validation = await builder.validate_transaction()
                    assert validation.is_legal is True
                    assert validation.major_league_count == 25  # 24 + 1
    
    @pytest.mark.asyncio
    async def test_complete_multi_move_workflow(self, commands_cog, mock_interaction, mock_team, mock_players, mock_roster):
        """Test complete workflow for multi-move transaction."""
        clear_transaction_builder(mock_interaction.user.id)
        
        with patch('commands.transactions.dropadd.team_service') as mock_team_service:
            with patch('services.transaction_builder.roster_service') as mock_roster_service:
                mock_team_service.get_teams_by_owner.return_value = [mock_team]
                mock_roster_service.get_current_roster.return_value = mock_roster
                
                # Start with /dropadd command
                await commands_cog.dropadd(mock_interaction)
                
                # Get the builder
                builder = get_transaction_builder(mock_interaction.user.id, mock_team)
                
                # Manually add multiple moves (simulating UI interactions)
                add_move = TransactionMove(
                    player=mock_players[0],  # Mike Trout
                    from_roster=RosterType.FREE_AGENCY,
                    to_roster=RosterType.MAJOR_LEAGUE,
                    to_team=mock_team
                )
                
                drop_move = TransactionMove(
                    player=mock_players[1],  # Ronald Acuna Jr.
                    from_roster=RosterType.MAJOR_LEAGUE,
                    to_roster=RosterType.FREE_AGENCY,
                    from_team=mock_team
                )
                
                builder.add_move(add_move)
                builder.add_move(drop_move)
                
                # Verify multi-move transaction
                assert builder.move_count == 2
                validation = await builder.validate_transaction()
                assert validation.is_legal is True
                assert validation.major_league_count == 24  # 24 + 1 - 1 = 24
    
    @pytest.mark.asyncio
    async def test_complete_submission_workflow(self, commands_cog, mock_interaction, mock_team, mock_players, mock_roster, mock_current_state):
        """Test complete transaction submission workflow."""
        clear_transaction_builder(mock_interaction.user.id)
        
        with patch('commands.transactions.dropadd.team_service') as mock_team_service:
            with patch('services.transaction_builder.roster_service') as mock_roster_service:
                with patch('services.league_service.LeagueService') as mock_league_service_class:
                    # Setup mocks
                    mock_team_service.get_teams_by_owner.return_value = [mock_team]
                    mock_roster_service.get_current_roster.return_value = mock_roster
                    
                    mock_league_service = MagicMock()
                    mock_league_service_class.return_value = mock_league_service
                    mock_league_service.get_current_state.return_value = mock_current_state
                    
                    # Create builder and add move
                    builder = get_transaction_builder(mock_interaction.user.id, mock_team)
                    move = TransactionMove(
                        player=mock_players[0],
                            from_roster=RosterType.FREE_AGENCY,
                        to_roster=RosterType.MAJOR_LEAGUE,
                        to_team=mock_team
                    )
                    builder.add_move(move)
                    
                    # Test submission
                    transactions = await builder.submit_transaction(week=11)
                    
                    # Verify transaction creation
                    assert len(transactions) == 1
                    transaction = transactions[0]
                    assert isinstance(transaction, Transaction)
                    assert transaction.player.name == 'Mike Trout'
                    assert transaction.week == 11
                    assert transaction.season == 12
                    assert "Season-012-Week-11-" in transaction.moveid
    
    @pytest.mark.asyncio
    async def test_modal_interaction_workflow(self, mock_interaction, mock_team, mock_players, mock_roster):
        """Test modal interaction workflow."""
        clear_transaction_builder(mock_interaction.user.id)
        
        with patch('services.transaction_builder.roster_service') as mock_roster_service:
            with patch('services.player_service.player_service') as mock_player_service:
                mock_roster_service.get_current_roster.return_value = mock_roster
                mock_player_service.get_players_by_name.return_value = [mock_players[0]]
                
                # Create builder
                builder = get_transaction_builder(mock_interaction.user.id, mock_team)
                
                # Create and test PlayerSelectionModal
                modal = PlayerSelectionModal(builder)
                modal.player_name.value = 'Mike Trout'
                modal.action.value = 'add'
                modal.destination.value = 'ml'
                
                await modal.on_submit(mock_interaction)
                
                # Verify move was added
                assert builder.move_count == 1
                move = builder.moves[0]
                assert move.player.name == 'Mike Trout'
                # Note: TransactionMove no longer has 'action' field
                
                # Verify success message
                mock_interaction.followup.send.assert_called()
                call_args = mock_interaction.followup.send.call_args
                assert "✅ Added:" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_submission_modal_workflow(self, mock_interaction, mock_team, mock_players, mock_roster, mock_current_state):
        """Test submission confirmation modal workflow."""
        clear_transaction_builder(mock_interaction.user.id)
        
        with patch('services.transaction_builder.roster_service') as mock_roster_service:
            with patch('services.league_service.LeagueService') as mock_league_service_class:
                mock_roster_service.get_current_roster.return_value = mock_roster
                
                mock_league_service = MagicMock()
                mock_league_service_class.return_value = mock_league_service
                mock_league_service.get_current_state.return_value = mock_current_state
                
                # Create builder with move
                builder = get_transaction_builder(mock_interaction.user.id, mock_team)
                move = TransactionMove(
                    player=mock_players[0],
                    from_roster=RosterType.FREE_AGENCY,
                    to_roster=RosterType.MAJOR_LEAGUE,
                    to_team=mock_team
                )
                builder.add_move(move)
                
                # Create and test SubmitConfirmationModal
                modal = SubmitConfirmationModal(builder)
                modal.confirmation.value = 'CONFIRM'
                
                await modal.on_submit(mock_interaction)
                
                # Verify submission process
                mock_league_service.get_current_state.assert_called_once()
                mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
                mock_interaction.followup.send.assert_called_once()
                
                # Verify success message
                call_args = mock_interaction.followup.send.call_args
                success_msg = call_args[0][0]
                assert "Transaction Submitted Successfully" in success_msg
                assert "Move ID:" in success_msg
    
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, commands_cog, mock_interaction, mock_team):
        """Test error handling throughout the workflow."""
        clear_transaction_builder(mock_interaction.user.id)
        
        with patch('commands.transactions.dropadd.team_service') as mock_team_service:
            # Test API error handling
            mock_team_service.get_teams_by_owner.side_effect = Exception("API Error")
            
            # Should not raise exception
            await commands_cog.dropadd(mock_interaction)
            
            # Should still defer (error handling in decorator)
            mock_interaction.response.defer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_roster_validation_workflow(self, commands_cog, mock_interaction, mock_team, mock_players):
        """Test roster validation throughout workflow."""
        clear_transaction_builder(mock_interaction.user.id)
        
        # Create roster at limit (25 ML players)
        ml_players = []
        for i in range(25):
            ml_players.append(RosterPlayer(
                id=1000 + i,
                name=f'ML Player {i}',
                season=12,
                primary_position='OF',
                is_minor_league=False
            ))
        
        full_roster = TeamRoster(
            team_id=499,
            week=10,
            season=12,
            players=ml_players
        )
        
        with patch('commands.transactions.dropadd.team_service') as mock_team_service:
            with patch('services.transaction_builder.roster_service') as mock_roster_service:
                mock_team_service.get_teams_by_owner.return_value = [mock_team]
                mock_roster_service.get_current_roster.return_value = full_roster
                
                # Create builder and try to add player (should exceed limit)
                builder = get_transaction_builder(mock_interaction.user.id, mock_team)
                move = TransactionMove(
                    player=mock_players[0],
                    from_roster=RosterType.FREE_AGENCY,
                    to_roster=RosterType.MAJOR_LEAGUE,
                    to_team=mock_team
                )
                builder.add_move(move)
                
                # Test validation
                validation = await builder.validate_transaction()
                assert validation.is_legal is False
                assert validation.major_league_count == 26  # Over limit
                assert len(validation.errors) > 0
                assert "26 players (limit: 25)" in validation.errors[0]
                assert len(validation.suggestions) > 0
                assert "Drop 1 ML player" in validation.suggestions[0]
    
    @pytest.mark.asyncio
    async def test_builder_persistence_workflow(self, commands_cog, mock_interaction, mock_team, mock_players, mock_roster):
        """Test that transaction builder persists across command calls."""
        clear_transaction_builder(mock_interaction.user.id)
        
        with patch('commands.transactions.dropadd.team_service') as mock_team_service:
            with patch('services.transaction_builder.roster_service') as mock_roster_service:
                mock_team_service.get_teams_by_owner.return_value = [mock_team]
                mock_roster_service.get_current_roster.return_value = mock_roster
                
                # First command call
                await commands_cog.dropadd(mock_interaction)
                builder1 = get_transaction_builder(mock_interaction.user.id, mock_team)
                
                # Add a move
                move = TransactionMove(
                    player=mock_players[0],
                    from_roster=RosterType.FREE_AGENCY,
                    to_roster=RosterType.MAJOR_LEAGUE,
                    to_team=mock_team
                )
                builder1.add_move(move)
                assert builder1.move_count == 1
                
                # Second command call should get same builder
                await commands_cog.dropadd(mock_interaction)
                builder2 = get_transaction_builder(mock_interaction.user.id, mock_team)
                
                # Should be same instance with same moves
                assert builder1 is builder2
                assert builder2.move_count == 1
                assert builder2.moves[0].player.name == 'Mike Trout'
    
    @pytest.mark.asyncio
    async def test_transaction_status_workflow(self, commands_cog, mock_interaction, mock_team, mock_players, mock_roster):
        """Test transaction status command workflow."""
        clear_transaction_builder(mock_interaction.user.id)
        
        with patch('commands.transactions.dropadd.team_service') as mock_team_service:
            with patch('services.transaction_builder.roster_service') as mock_roster_service:
                mock_team_service.get_teams_by_owner.return_value = [mock_team]
                mock_roster_service.get_current_roster.return_value = mock_roster
                
                # Test with empty builder
                await commands_cog.transaction_status(mock_interaction)
                
                call_args = mock_interaction.followup.send.call_args
                assert "transaction builder is empty" in call_args[0][0]
                
                # Add move and test again
                builder = get_transaction_builder(mock_interaction.user.id, mock_team)
                move = TransactionMove(
                    player=mock_players[0],
                    from_roster=RosterType.FREE_AGENCY,
                    to_roster=RosterType.MAJOR_LEAGUE,
                    to_team=mock_team
                )
                builder.add_move(move)
                
                # Reset mock
                mock_interaction.followup.send.reset_mock()
                
                await commands_cog.transaction_status(mock_interaction)
                
                call_args = mock_interaction.followup.send.call_args
                status_msg = call_args[0][0]
                assert "Moves:** 1" in status_msg
                assert "✅ Legal" in status_msg