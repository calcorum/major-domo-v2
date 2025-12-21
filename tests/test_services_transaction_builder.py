"""
Tests for TransactionBuilder service

Validates transaction building, roster validation, and move management.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from services.transaction_builder import (
    TransactionBuilder,
    TransactionMove,
    RosterType,
    RosterValidationResult,
    get_transaction_builder,
    clear_transaction_builder
)
from models.team import Team
from models.player import Player
from models.roster import TeamRoster
from models.transaction import Transaction
from tests.factories import PlayerFactory, TeamFactory


class TestTransactionBuilder:
    """Test TransactionBuilder core functionality."""
    
    @pytest.fixture
    def mock_team(self):
        """Create a mock team for testing."""
        return Team(
            id=499,
            abbrev='WV',
            sname='Black Bears',
            lname='West Virginia Black Bears',
            season=12
        )
    
    @pytest.fixture
    def mock_player(self):
        """Create a mock player for testing."""
        return Player(
            id=12472,
            name='Test Player',
            wara=2.5,
            season=12,
            pos_1='OF'
        )
    
    @pytest.fixture
    def mock_roster(self):
        """Create a mock roster for testing."""
        # Create roster players
        ml_players = []
        for i in range(24):  # 24 ML players (under limit)
            ml_players.append(Player(
                id=1000 + i,
                name=f'ML Player {i}',
                wara=1.5,
                season=12,
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
        
        mil_players = []
        for i in range(6):  # 6 MiL players (at limit)
            mil_players.append(Player(
                id=2000 + i,
                name=f'MiL Player {i}',
                wara=0.5,
                season=12,
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
            team_abbrev='WV',
            week=10,
            season=12,
            active_players=ml_players,
            minor_league_players=mil_players
        )
    
    @pytest.fixture
    def builder(self, mock_team):
        """Create a TransactionBuilder for testing."""
        return TransactionBuilder(mock_team, user_id=123456789, season=12)
    
    def test_builder_initialization(self, builder, mock_team):
        """Test transaction builder initialization."""
        assert builder.team == mock_team
        assert builder.user_id == 123456789
        assert builder.season == 12
        assert builder.is_empty is True
        assert builder.move_count == 0
        assert len(builder.moves) == 0
    
    @pytest.mark.asyncio
    async def test_add_move_success(self, builder, mock_player):
        """Test successfully adding a move."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            to_team=builder.team
        )

        # Skip pending transaction check for unit tests
        success, error_message = await builder.add_move(move, check_pending_transactions=False)

        assert success is True
        assert error_message == ""
        assert builder.move_count == 1
        assert builder.is_empty is False
        assert move in builder.moves

    @pytest.mark.asyncio
    async def test_add_duplicate_move_fails(self, builder, mock_player):
        """Test that adding duplicate moves for same player fails."""
        move1 = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            to_team=builder.team
        )

        move2 = TransactionMove(
            player=mock_player,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.FREE_AGENCY,
            from_team=builder.team
        )

        success1, error_message1 = await builder.add_move(move1, check_pending_transactions=False)
        success2, error_message2 = await builder.add_move(move2, check_pending_transactions=False)

        assert success1 is True
        assert error_message1 == ""
        assert success2 is False  # Should fail due to duplicate player
        assert "already has a move" in error_message2
        assert builder.move_count == 1

    @pytest.mark.asyncio
    async def test_add_move_same_team_same_roster_fails(self, builder, mock_player):
        """Test that adding a move where from_team, to_team, from_roster, and to_roster are all the same fails."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.MAJOR_LEAGUE,  # Same roster
            from_team=builder.team,
            to_team=builder.team  # Same team - should fail when roster is also same
        )

        success, error_message = await builder.add_move(move, check_pending_transactions=False)

        assert success is False
        assert "already in that location" in error_message
        assert builder.move_count == 0
        assert builder.is_empty is True

    @pytest.mark.asyncio
    async def test_add_move_same_team_different_roster_succeeds(self, builder, mock_player):
        """Test that adding a move where teams are same but rosters are different succeeds."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.MINOR_LEAGUE,  # Different roster
            from_team=builder.team,
            to_team=builder.team  # Same team - should succeed when rosters differ
        )

        success, error_message = await builder.add_move(move, check_pending_transactions=False)

        assert success is True
        assert error_message == ""
        assert builder.move_count == 1
        assert builder.is_empty is False

    @pytest.mark.asyncio
    async def test_add_move_different_teams_succeeds(self, builder, mock_player):
        """Test that adding a move where from_team and to_team are different succeeds."""
        other_team = Team(
            id=500,
            abbrev='NY',
            sname='Mets',
            lname='New York Mets',
            season=12
        )

        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.MAJOR_LEAGUE,
            from_team=other_team,
            to_team=builder.team
        )

        success, error_message = await builder.add_move(move, check_pending_transactions=False)

        assert success is True
        assert error_message == ""
        assert builder.move_count == 1
        assert builder.is_empty is False

    @pytest.mark.asyncio
    async def test_add_move_none_teams_succeeds(self, builder, mock_player):
        """Test that adding a move where one or both teams are None succeeds."""
        # From FA to team (from_team=None)
        move1 = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            from_team=None,
            to_team=builder.team
        )

        success1, error_message1 = await builder.add_move(move1, check_pending_transactions=False)
        assert success1 is True
        assert error_message1 == ""

        builder.clear_moves()

        # Create different player for second test
        other_player = Player(
            id=12473,
            name='Other Player',
            wara=1.5,
            season=12,
            pos_1='OF'
        )

        # From team to FA (to_team=None)
        move2 = TransactionMove(
            player=other_player,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.FREE_AGENCY,
            from_team=builder.team,
            to_team=None
        )

        success2, error_message2 = await builder.add_move(move2, check_pending_transactions=False)
        assert success2 is True
        assert error_message2 == ""

    @pytest.mark.asyncio
    async def test_remove_move_success(self, builder, mock_player):
        """Test successfully removing a move."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            to_team=builder.team
        )

        success, _ = await builder.add_move(move, check_pending_transactions=False)
        assert success
        assert builder.move_count == 1

        removed = builder.remove_move(mock_player.id)

        assert removed is True
        assert builder.move_count == 0
        assert builder.is_empty is True
    
    def test_remove_nonexistent_move(self, builder):
        """Test removing a move that doesn't exist."""
        removed = builder.remove_move(99999)
        
        assert removed is False
        assert builder.move_count == 0
    
    @pytest.mark.asyncio
    async def test_get_move_for_player(self, builder, mock_player):
        """Test getting move for a specific player."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            to_team=builder.team
        )

        await builder.add_move(move, check_pending_transactions=False)

        found_move = builder.get_move_for_player(mock_player.id)
        not_found = builder.get_move_for_player(99999)

        assert found_move == move
        assert not_found is None

    @pytest.mark.asyncio
    async def test_clear_moves(self, builder, mock_player):
        """Test clearing all moves."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            to_team=builder.team
        )

        success, _ = await builder.add_move(move, check_pending_transactions=False)
        assert success
        assert builder.move_count == 1

        builder.clear_moves()

        assert builder.move_count == 0
        assert builder.is_empty is True

    @pytest.mark.asyncio
    async def test_validate_transaction_no_roster(self, builder):
        """Test validation when roster data cannot be loaded."""
        with patch.object(builder, '_current_roster', None):
            with patch.object(builder, '_roster_loaded', True):
                validation = await builder.validate_transaction()

                assert validation.is_legal is False
                assert len(validation.errors) == 1
                assert "Could not load current roster data" in validation.errors[0]

    @pytest.mark.asyncio
    async def test_validate_transaction_legal(self, builder, mock_roster, mock_player):
        """Test validation of a legal transaction."""
        with patch.object(builder, '_current_roster', mock_roster):
            with patch.object(builder, '_roster_loaded', True):
                # Add a move that keeps roster under limit (24 -> 25)
                move = TransactionMove(
                    player=mock_player,
                    from_roster=RosterType.FREE_AGENCY,
                    to_roster=RosterType.MAJOR_LEAGUE,
                    to_team=builder.team
                )
                success, _ = await builder.add_move(move, check_pending_transactions=False)
                assert success

                validation = await builder.validate_transaction()

                assert validation.is_legal is True
                assert validation.major_league_count == 25  # 24 + 1
                assert len(validation.errors) == 0

    @pytest.mark.asyncio
    async def test_validate_transaction_over_limit(self, builder, mock_roster):
        """Test validation when transaction would exceed roster limit."""
        with patch.object(builder, '_current_roster', mock_roster):
            with patch.object(builder, '_roster_loaded', True):
                # Add 3 players to exceed limit (24 + 3 = 27 > 26)
                for i in range(3):
                    player = Player(
                        id=3000 + i,
                        name=f'New Player {i}',
                        wara=1.0,
                        season=12,
                        pos_1='OF'
                    )
                    move = TransactionMove(
                        player=player,
                        from_roster=RosterType.FREE_AGENCY,
                        to_roster=RosterType.MAJOR_LEAGUE,
                        to_team=builder.team
                    )
                    success, _ = await builder.add_move(move, check_pending_transactions=False)
                assert success

                validation = await builder.validate_transaction()
                
                assert validation.is_legal is False
                assert validation.major_league_count == 27  # 24 + 3
                assert len(validation.errors) == 1
                assert "27 players (limit: 26)" in validation.errors[0]
                assert len(validation.suggestions) == 1
                assert "Drop 1 ML player" in validation.suggestions[0]
    
    @pytest.mark.asyncio
    async def test_validate_transaction_empty(self, builder, mock_roster):
        """Test validation of empty transaction."""
        with patch.object(builder, '_current_roster', mock_roster):
            with patch.object(builder, '_roster_loaded', True):
                validation = await builder.validate_transaction()
                
                assert validation.is_legal is True  # Empty transaction is legal
                assert validation.major_league_count == 24  # No changes
                assert len(validation.suggestions) == 1
                assert "Add player moves" in validation.suggestions[0]
    
    @pytest.mark.asyncio
    async def test_submit_transaction_empty(self, builder):
        """Test submitting empty transaction fails."""
        with pytest.raises(ValueError, match="Cannot submit empty transaction"):
            await builder.submit_transaction(week=11)
    
    @pytest.mark.asyncio
    async def test_submit_transaction_illegal(self, builder, mock_roster):
        """Test submitting illegal transaction fails."""
        with patch.object(builder, '_current_roster', mock_roster):
            with patch.object(builder, '_roster_loaded', True):
                # Add moves that exceed limit
                for i in range(3):  # 24 + 3 = 27 > 25
                    player = Player(
                        id=4000 + i,
                        name=f'Illegal Player {i}',
                        wara=1.5,
                        season=12,
                        pos_1='OF'
                    )
                    move = TransactionMove(
                        player=player,
                        from_roster=RosterType.FREE_AGENCY,
                        to_roster=RosterType.MAJOR_LEAGUE,
                        to_team=builder.team
                    )
                    success, _ = await builder.add_move(move, check_pending_transactions=False)
                assert success

                with pytest.raises(ValueError, match="Cannot submit illegal transaction"):
                    await builder.submit_transaction(week=11)

    @pytest.mark.asyncio
    async def test_submit_transaction_success(self, builder, mock_roster, mock_player):
        """Test successful transaction submission."""
        with patch.object(builder, '_current_roster', mock_roster):
            with patch.object(builder, '_roster_loaded', True):
                # Add a legal move
                move = TransactionMove(
                    player=mock_player,
                    from_roster=RosterType.FREE_AGENCY,
                    to_roster=RosterType.MAJOR_LEAGUE,
                    to_team=builder.team
                )
                success, _ = await builder.add_move(move, check_pending_transactions=False)
                assert success

                transactions = await builder.submit_transaction(week=11)

                assert len(transactions) == 1
                transaction = transactions[0]
                assert isinstance(transaction, Transaction)
                assert transaction.week == 11
                assert transaction.season == 12
                assert transaction.player == mock_player
                assert transaction.newteam == builder.team
                assert "Season-012-Week-11-" in transaction.moveid

    @pytest.mark.asyncio
    async def test_submit_complex_transaction(self, builder, mock_roster):
        """Test submitting transaction with multiple moves."""
        with patch.object(builder, '_current_roster', mock_roster):
            with patch.object(builder, '_roster_loaded', True):
                # Add one player and drop one player (net zero)
                add_player = Player(id=5001, name='Add Player', wara=2.0, season=12, pos_1='OF')
                drop_player = Player(id=5002, name='Drop Player', wara=1.0, season=12, pos_1='OF')

                add_move = TransactionMove(
                    player=add_player,
                    from_roster=RosterType.FREE_AGENCY,
                    to_roster=RosterType.MAJOR_LEAGUE,
                    to_team=builder.team
                )

                drop_move = TransactionMove(
                    player=drop_player,
                    from_roster=RosterType.MAJOR_LEAGUE,
                    to_roster=RosterType.FREE_AGENCY,
                    from_team=builder.team
                )

                success1, _ = await builder.add_move(add_move, check_pending_transactions=False)
                success2, _ = await builder.add_move(drop_move, check_pending_transactions=False)
                assert success1 and success2

                transactions = await builder.submit_transaction(week=11)

                assert len(transactions) == 2
                # Both transactions should have the same move_id
                assert transactions[0].moveid == transactions[1].moveid


class TestTransactionMove:
    """Test TransactionMove dataclass functionality."""
    
    @pytest.fixture
    def mock_player(self):
        """Create a mock player."""
        return Player(id=123, name='Test Player', wara=2.0, season=12, pos_1='OF')
    
    @pytest.fixture
    def mock_team(self):
        """Create a mock team."""
        return Team(id=499, abbrev='WV', sname='Black Bears', lname='West Virginia Black Bears', season=12)
    
    def test_add_move_description(self, mock_player, mock_team):
        """Test ADD move description."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            to_team=mock_team
        )

        expected = "➕ Test Player: FA → WV (ML)"
        assert move.description == expected

    def test_drop_move_description(self, mock_player, mock_team):
        """Test DROP move description."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.FREE_AGENCY,
            from_team=mock_team
        )

        expected = "➖ Test Player: WV (ML) → FA"
        assert move.description == expected

    def test_recall_move_description(self, mock_player, mock_team):
        """Test RECALL move description."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.MINOR_LEAGUE,
            to_roster=RosterType.MAJOR_LEAGUE,
            from_team=mock_team,
            to_team=mock_team
        )

        expected = "⬆️ Test Player: WV (MiL) → WV (ML)"
        assert move.description == expected

    def test_demote_move_description(self, mock_player, mock_team):
        """Test DEMOTE move description."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.MINOR_LEAGUE,
            from_team=mock_team,
            to_team=mock_team
        )

        expected = "⬇️ Test Player: WV (ML) → WV (MiL)"
        assert move.description == expected


class TestRosterValidationResult:
    """Test RosterValidationResult functionality."""
    
    def test_major_league_status_over_limit(self):
        """Test status when over major league limit."""
        result = RosterValidationResult(
            is_legal=False,
            major_league_count=27,
            minor_league_count=6,
            warnings=[],
            errors=[],
            suggestions=[]
        )

        expected = "❌ Major League: 27/26 (Over limit!)"
        assert result.major_league_status == expected
    
    def test_major_league_status_at_limit(self):
        """Test status when at major league limit."""
        result = RosterValidationResult(
            is_legal=True,
            major_league_count=26,
            minor_league_count=6,
            warnings=[],
            errors=[],
            suggestions=[]
        )

        expected = "✅ Major League: 26/26 (Legal)"
        assert result.major_league_status == expected
    
    def test_major_league_status_under_limit(self):
        """Test status when under major league limit."""
        result = RosterValidationResult(
            is_legal=True,
            major_league_count=23,
            minor_league_count=6,
            warnings=[],
            errors=[],
            suggestions=[]
        )

        expected = "✅ Major League: 23/26 (Legal)"
        assert result.major_league_status == expected
    
    def test_minor_league_status(self):
        """Test minor league status with limit."""
        result = RosterValidationResult(
            is_legal=False,
            major_league_count=25,
            minor_league_count=7,
            warnings=[],
            errors=[],
            suggestions=[]
        )

        expected = "❌ Minor League: 7/6 (Over limit!)"
        assert result.minor_league_status == expected


class TestTransactionBuilderGlobalFunctions:
    """Test global transaction builder functions."""
    
    def test_get_transaction_builder_new(self):
        """Test getting new transaction builder."""
        team = Team(id=499, abbrev='WV', sname='Black Bears', lname='West Virginia Black Bears', season=12)
        
        builder = get_transaction_builder(user_id=123, team=team)
        
        assert isinstance(builder, TransactionBuilder)
        assert builder.user_id == 123
        assert builder.team == team
    
    def test_get_transaction_builder_existing(self):
        """Test getting existing transaction builder."""
        team = Team(id=499, abbrev='WV', sname='Black Bears', lname='West Virginia Black Bears', season=12)
        
        builder1 = get_transaction_builder(user_id=123, team=team)
        builder2 = get_transaction_builder(user_id=123, team=team)
        
        assert builder1 is builder2  # Should return same instance
    
    def test_clear_transaction_builder(self):
        """Test clearing transaction builder."""
        team = Team(id=499, abbrev='WV', sname='Black Bears', lname='West Virginia Black Bears', season=12)
        
        builder = get_transaction_builder(user_id=123, team=team)
        assert builder is not None
        
        clear_transaction_builder(user_id=123)
        
        # Getting builder again should create new instance
        new_builder = get_transaction_builder(user_id=123, team=team)
        assert new_builder is not builder
    
    def test_clear_nonexistent_builder(self):
        """Test clearing non-existent builder doesn't error."""
        # Should not raise any exception
        clear_transaction_builder(user_id=99999)


class TestPendingTransactionValidation:
    """
    Test pending transaction validation in add_move.

    This validates that players who are already in a pending transaction
    for the next week cannot be added to another transaction.
    """

    @pytest.fixture
    def mock_team(self):
        """Create a mock team for testing."""
        return Team(
            id=499,
            abbrev='WV',
            sname='Black Bears',
            lname='West Virginia Black Bears',
            season=12
        )

    @pytest.fixture
    def mock_player(self):
        """Create a mock player for testing."""
        return Player(
            id=12472,
            name='Test Player',
            wara=2.5,
            season=12,
            pos_1='OF'
        )

    @pytest.fixture
    def builder(self, mock_team):
        """Create a TransactionBuilder for testing."""
        return TransactionBuilder(mock_team, user_id=123, season=12)

    @pytest.mark.asyncio
    async def test_add_move_player_in_pending_transaction_fails(self, builder, mock_player):
        """
        Test that adding a player who is already in a pending transaction fails.

        When a player is claimed by another team in a pending (unfrozen) transaction
        for the next week, they should not be able to be added to another transaction.
        """
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            to_team=builder.team
        )

        with patch('services.transaction_builder.transaction_service') as mock_tx_service:
            with patch('services.transaction_builder.league_service') as mock_league_service:
                # Mock that player IS in a pending transaction (claimed by LAA)
                mock_tx_service.is_player_in_pending_transaction = AsyncMock(
                    return_value=(True, "LAA")
                )
                # Mock current state to provide next week
                mock_league_service.get_current_state = AsyncMock(
                    return_value=MagicMock(week=10)
                )

                success, error_message = await builder.add_move(move)

                assert success is False
                assert "already in a pending transaction" in error_message
                assert "week 11" in error_message
                assert "LAA" in error_message
                assert builder.move_count == 0

    @pytest.mark.asyncio
    async def test_add_move_player_not_in_pending_transaction_succeeds(self, builder, mock_player):
        """
        Test that adding a player who is NOT in a pending transaction succeeds.

        When a player is available (not claimed in any pending transaction),
        they should be able to be added to the transaction builder.
        """
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            to_team=builder.team
        )

        with patch('services.transaction_builder.transaction_service') as mock_tx_service:
            with patch('services.transaction_builder.league_service') as mock_league_service:
                # Mock that player is NOT in a pending transaction
                mock_tx_service.is_player_in_pending_transaction = AsyncMock(
                    return_value=(False, None)
                )
                # Mock current state to provide next week
                mock_league_service.get_current_state = AsyncMock(
                    return_value=MagicMock(week=10)
                )

                success, error_message = await builder.add_move(move)

                assert success is True
                assert error_message == ""
                assert builder.move_count == 1

    @pytest.mark.asyncio
    async def test_add_move_skip_pending_check_with_flag(self, builder, mock_player):
        """
        Test that check_pending_transactions=False skips the validation.

        This is used for IL moves and trade moves where the pending transaction
        check should not apply.
        """
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            to_team=builder.team
        )

        # Even if the service would return True, the check should be skipped
        with patch('services.transaction_builder.transaction_service') as mock_tx_service:
            # This mock should NOT be called when check_pending_transactions=False
            mock_tx_service.is_player_in_pending_transaction = AsyncMock(
                return_value=(True, "LAA")
            )

            success, error_message = await builder.add_move(
                move, check_pending_transactions=False
            )

            assert success is True
            assert error_message == ""
            assert builder.move_count == 1
            # Verify the service method was NOT called
            mock_tx_service.is_player_in_pending_transaction.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_move_with_explicit_next_week(self, builder, mock_player):
        """
        Test that providing next_week parameter uses that value.

        The next_week parameter allows the caller to specify which week
        to check for pending transactions.
        """
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            to_team=builder.team
        )

        with patch('services.transaction_builder.transaction_service') as mock_tx_service:
            mock_tx_service.is_player_in_pending_transaction = AsyncMock(
                return_value=(False, None)
            )

            success, error_message = await builder.add_move(move, next_week=15)

            assert success is True
            # Verify the check was called with the explicit week
            mock_tx_service.is_player_in_pending_transaction.assert_called_once()
            call_args = mock_tx_service.is_player_in_pending_transaction.call_args
            assert call_args.kwargs['week'] == 15