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
    
    def test_add_move_success(self, builder, mock_player):
        """Test successfully adding a move."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            to_team=builder.team
        )

        success, error_message = builder.add_move(move)

        assert success is True
        assert error_message == ""
        assert builder.move_count == 1
        assert builder.is_empty is False
        assert move in builder.moves
    
    def test_add_duplicate_move_fails(self, builder, mock_player):
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

        success1, error_message1 = builder.add_move(move1)
        success2, error_message2 = builder.add_move(move2)

        assert success1 is True
        assert error_message1 == ""
        assert success2 is False  # Should fail due to duplicate player
        assert "already has a move" in error_message2
        assert builder.move_count == 1

    def test_add_move_same_team_same_roster_fails(self, builder, mock_player):
        """Test that adding a move where from_team, to_team, from_roster, and to_roster are all the same fails."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.MAJOR_LEAGUE,  # Same roster
            from_team=builder.team,
            to_team=builder.team  # Same team - should fail when roster is also same
        )

        success, error_message = builder.add_move(move)

        assert success is False
        assert "already in that location" in error_message
        assert builder.move_count == 0
        assert builder.is_empty is True

    def test_add_move_same_team_different_roster_succeeds(self, builder, mock_player):
        """Test that adding a move where teams are same but rosters are different succeeds."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.MINOR_LEAGUE,  # Different roster
            from_team=builder.team,
            to_team=builder.team  # Same team - should succeed when rosters differ
        )

        success, error_message = builder.add_move(move)

        assert success is True
        assert error_message == ""
        assert builder.move_count == 1
        assert builder.is_empty is False

    def test_add_move_different_teams_succeeds(self, builder, mock_player):
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

        success, error_message = builder.add_move(move)

        assert success is True
        assert error_message == ""
        assert builder.move_count == 1
        assert builder.is_empty is False

    def test_add_move_none_teams_succeeds(self, builder, mock_player):
        """Test that adding a move where one or both teams are None succeeds."""
        # From FA to team (from_team=None)
        move1 = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            from_team=None,
            to_team=builder.team
        )

        success1, error_message1 = builder.add_move(move1)
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

        success2, error_message2 = builder.add_move(move2)
        assert success2 is True
        assert error_message2 == ""
    
    def test_remove_move_success(self, builder, mock_player):
        """Test successfully removing a move."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            to_team=builder.team
        )

        success, _ = builder.add_move(move)
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
    
    def test_get_move_for_player(self, builder, mock_player):
        """Test getting move for a specific player."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            to_team=builder.team
        )

        builder.add_move(move)

        found_move = builder.get_move_for_player(mock_player.id)
        not_found = builder.get_move_for_player(99999)

        assert found_move == move
        assert not_found is None
    
    def test_clear_moves(self, builder, mock_player):
        """Test clearing all moves."""
        move = TransactionMove(
            player=mock_player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            to_team=builder.team
        )

        success, _ = builder.add_move(move)
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
                success, _ = builder.add_move(move)
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
                    success, _ = builder.add_move(move)
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
                    success, _ = builder.add_move(move)
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
                success, _ = builder.add_move(move)
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
                
                success1, _ = builder.add_move(add_move)
                success2, _ = builder.add_move(drop_move)
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