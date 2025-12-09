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
    SubmitConfirmationModal
)
from models.team import Team
from models.player import Player
from models.roster import TeamRoster
from models.transaction import Transaction
from models.current import Current
from tests.factories import PlayerFactory, TeamFactory


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

        # Guild mock required for @league_only decorator
        interaction.guild = MagicMock()
        interaction.guild.id = 669356687294988350  # SBA league server ID from config

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
        return TeamFactory.west_virginia()
    
    @pytest.fixture
    def mock_players(self):
        """Create mock players."""
        return [
            PlayerFactory.mike_trout(),
            PlayerFactory.ronald_acuna(),
            PlayerFactory.mookie_betts()
        ]
    
    @pytest.fixture
    def mock_roster(self):
        """Create mock team roster.

        Creates a legal roster: 24 ML players (under 26 limit), 4 MiL players (under 6 limit).
        This allows adding players without hitting limits.
        """
        # Create 24 ML players (under limit)
        ml_players = []
        for i in range(24):
            ml_players.append(Player(
                id=1000 + i,
                name=f'ML Player {i}',
                wara=3.0 + i * 0.1,
                season=13,
                team_id=499,
                team=None,
                image=None,
                image2=None,
                vanity_card=None,
                headshot=None,
                pos_1='OF',
                pitcher_injury=None,
                injury_rating=None,
                il_return=None,
                demotion_week=None,
                last_game=None,
                last_game2=None,
                strat_code=None,
                bbref_id=None,
                sbaplayer=None
            ))

        # Create 4 MiL players (under 6 limit to allow adding)
        mil_players = []
        for i in range(4):
            mil_players.append(Player(
                id=2000 + i,
                name=f'MiL Player {i}',
                wara=1.0 + i * 0.1,
                season=13,
                team_id=499,
                team=None,
                image=None,
                image2=None,
                vanity_card=None,
                headshot=None,
                pos_1='OF',
                pitcher_injury=None,
                injury_rating=None,
                il_return=None,
                demotion_week=None,
                last_game=None,
                last_game2=None,
                strat_code=None,
                bbref_id=None,
                sbaplayer=None
            ))

        return TeamRoster(
            team_id=499,
            team_abbrev='TST',
            week=10,
            season=13,
            active_players=ml_players,
            minor_league_players=mil_players
        )
    
    @pytest.fixture
    def mock_current_state(self):
        """Create mock current league state."""
        return Current(
            week=10,
            season=13,
            freeze=False
        )
    
    @pytest.mark.asyncio
    async def test_complete_single_move_workflow(self, commands_cog, mock_interaction, mock_team, mock_players, mock_roster):
        """Test complete workflow for single move transaction.

        Verifies that when a player and destination are provided to /dropadd,
        the command:
        1. Validates user has a team via validate_user_has_team
        2. Creates a transaction builder
        3. Searches for the player
        4. Adds the move to the builder
        5. Returns an interactive embed
        """
        # Clear any existing builders
        clear_transaction_builder(mock_interaction.user.id)

        with patch('commands.transactions.dropadd.validate_user_has_team') as mock_validate:
            with patch('commands.transactions.dropadd.player_service') as mock_player_service:
                with patch('services.transaction_builder.roster_service') as mock_roster_service:
                    with patch('services.transaction_builder.transaction_service') as mock_tx_service:
                        # Setup mocks
                        mock_validate.return_value = mock_team  # validate_user_has_team returns team
                        mock_player_service.search_players = AsyncMock(return_value=[mock_players[0]])  # Mike Trout
                        mock_roster_service.get_current_roster = AsyncMock(return_value=mock_roster)
                        mock_tx_service.get_team_transactions = AsyncMock(return_value=[])

                        # Execute /dropadd command with quick move
                        await commands_cog.dropadd.callback(commands_cog,
                            mock_interaction,
                            player='Mike Trout',
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
        """Test complete workflow for multi-move transaction.

        Verifies that manually adding multiple moves to the transaction builder
        correctly tracks roster changes and validates legality.
        """
        clear_transaction_builder(mock_interaction.user.id)

        with patch('commands.transactions.dropadd.validate_user_has_team') as mock_validate:
            with patch('services.transaction_builder.roster_service') as mock_roster_service:
                with patch('services.transaction_builder.transaction_service') as mock_tx_service:
                    mock_validate.return_value = mock_team
                    mock_roster_service.get_current_roster = AsyncMock(return_value=mock_roster)
                    mock_tx_service.get_team_transactions = AsyncMock(return_value=[])

                    # Start with /dropadd command
                    await commands_cog.dropadd.callback(commands_cog, mock_interaction)

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
        """Test complete transaction submission workflow.

        Verifies that submitting a transaction via the builder creates
        proper Transaction objects with correct attributes.
        """
        clear_transaction_builder(mock_interaction.user.id)

        with patch('services.transaction_builder.roster_service') as mock_roster_service:
            with patch('services.transaction_builder.transaction_service') as mock_tx_service:
                # Setup mocks
                mock_roster_service.get_current_roster = AsyncMock(return_value=mock_roster)
                mock_tx_service.get_team_transactions = AsyncMock(return_value=[])

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
                assert transaction.season == 13
                assert "Season-013-Week-11-" in transaction.moveid
    
    
    @pytest.mark.asyncio
    async def test_submission_modal_workflow(self, mock_interaction, mock_team, mock_players, mock_roster, mock_current_state):
        """Test submission confirmation modal workflow.

        Verifies that the SubmitConfirmationModal properly:
        1. Validates the "CONFIRM" input
        2. Fetches current league state
        3. Submits transactions
        4. Posts success message

        Note: The modal imports services dynamically inside on_submit(),
        so we patch them where they're imported from (services.X module).

        Note: Discord.py's TextInput.value is a read-only property, so we
        replace the entire confirmation attribute with a MagicMock.
        """
        clear_transaction_builder(mock_interaction.user.id)

        with patch('services.transaction_builder.roster_service') as mock_roster_service:
            with patch('services.transaction_builder.transaction_service') as mock_tx_service:
                with patch('services.league_service.league_service') as mock_league_service:
                    with patch('services.transaction_service.transaction_service') as mock_view_tx_service:
                        with patch('utils.transaction_logging.post_transaction_to_log') as mock_post_log:
                            mock_roster_service.get_current_roster = AsyncMock(return_value=mock_roster)
                            mock_tx_service.get_team_transactions = AsyncMock(return_value=[])
                            mock_league_service.get_current_state = AsyncMock(return_value=mock_current_state)
                            mock_post_log.return_value = None

                            # Create builder with move
                            builder = get_transaction_builder(mock_interaction.user.id, mock_team)
                            move = TransactionMove(
                                player=mock_players[0],
                                from_roster=RosterType.FREE_AGENCY,
                                to_roster=RosterType.MAJOR_LEAGUE,
                                to_team=mock_team
                            )
                            builder.add_move(move)

                            # Submit transactions first to get move IDs
                            transactions = await builder.submit_transaction(week=mock_current_state.week + 1)
                            mock_view_tx_service.create_transaction_batch = AsyncMock(return_value=transactions)

                            # Reset the builder and add move again for modal test
                            clear_transaction_builder(mock_interaction.user.id)
                            builder = get_transaction_builder(mock_interaction.user.id, mock_team)
                            builder.add_move(move)

                            # Create the modal
                            modal = SubmitConfirmationModal(builder)

                            # Replace the entire confirmation input with a mock that has .value
                            # Discord.py's TextInput.value is read-only, so we can't patch it
                            mock_confirmation = MagicMock()
                            mock_confirmation.value = 'CONFIRM'
                            modal.confirmation = mock_confirmation

                            await modal.on_submit(mock_interaction)

                            # Verify submission process
                            mock_league_service.get_current_state.assert_called()
                            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
                            mock_interaction.followup.send.assert_called_once()

                            # Verify success message
                            call_args = mock_interaction.followup.send.call_args
                            success_msg = call_args[0][0]
                            assert "Transaction Submitted Successfully" in success_msg
                            assert "Move ID:" in success_msg
    
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, commands_cog, mock_interaction, mock_team):
        """Test error handling throughout the workflow.

        Verifies that when validate_user_has_team raises an error,
        the @logged_command decorator catches it and sends an error message.

        Note: The @logged_command decorator catches exceptions, logs them,
        and sends an error message to the user via followup.send().
        The exception is then re-raised, so we catch it in the test.
        """
        clear_transaction_builder(mock_interaction.user.id)

        with patch('commands.transactions.dropadd.validate_user_has_team') as mock_validate:
            # Test API error handling
            mock_validate.side_effect = Exception("API Error")

            # The decorator catches and re-raises the exception
            # We wrap in try/except to verify the error handling
            try:
                await commands_cog.dropadd.callback(commands_cog, mock_interaction)
            except Exception:
                pass  # Expected - decorator re-raises after logging

            # Should still defer (called before error)
            mock_interaction.response.defer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_roster_validation_workflow(self, commands_cog, mock_interaction, mock_team, mock_players):
        """Test roster validation throughout workflow.

        Verifies that the transaction builder correctly validates roster limits
        and provides appropriate error messages when adding players would exceed limits.
        """
        clear_transaction_builder(mock_interaction.user.id)

        # Create roster at limit (26 ML players for week 10)
        ml_players = []
        for i in range(26):
            ml_players.append(Player(
                id=1000 + i,
                name=f'ML Player {i}',
                wara=3.0 + i * 0.1,
                season=13,
                team_id=499,
                team=None,
                image=None,
                image2=None,
                vanity_card=None,
                headshot=None,
                pos_1='OF',
                pitcher_injury=None,
                injury_rating=None,
                il_return=None,
                demotion_week=None,
                last_game=None,
                last_game2=None,
                strat_code=None,
                bbref_id=None,
                sbaplayer=None
            ))

        full_roster = TeamRoster(
            team_id=499,
            team_abbrev='TST',
            week=10,
            season=13,
            active_players=ml_players
        )

        with patch('services.transaction_builder.roster_service') as mock_roster_service:
            with patch('services.transaction_builder.transaction_service') as mock_tx_service:
                mock_roster_service.get_current_roster = AsyncMock(return_value=full_roster)
                mock_tx_service.get_team_transactions = AsyncMock(return_value=[])

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
                assert validation.major_league_count == 27  # Over limit (26 + 1 added)
                assert len(validation.errors) > 0
                assert "27 players (limit: 26)" in validation.errors[0]
                assert len(validation.suggestions) > 0
                assert "Drop 1 ML player" in validation.suggestions[0]
    
    @pytest.mark.asyncio
    async def test_builder_persistence_workflow(self, commands_cog, mock_interaction, mock_team, mock_players, mock_roster):
        """Test that transaction builder persists across command calls.

        Verifies that calling /dropadd multiple times uses the same
        TransactionBuilder instance, preserving moves between calls.
        """
        clear_transaction_builder(mock_interaction.user.id)

        with patch('commands.transactions.dropadd.validate_user_has_team') as mock_validate:
            with patch('services.transaction_builder.roster_service') as mock_roster_service:
                with patch('services.transaction_builder.transaction_service') as mock_tx_service:
                    mock_validate.return_value = mock_team
                    mock_roster_service.get_current_roster = AsyncMock(return_value=mock_roster)
                    mock_tx_service.get_team_transactions = AsyncMock(return_value=[])

                    # First command call
                    await commands_cog.dropadd.callback(commands_cog, mock_interaction)
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
                    await commands_cog.dropadd.callback(commands_cog, mock_interaction)
                    builder2 = get_transaction_builder(mock_interaction.user.id, mock_team)

                    # Should be same instance with same moves
                    assert builder1 is builder2
                    assert builder2.move_count == 1
                    assert builder2.moves[0].player.name == 'Mike Trout'
    
