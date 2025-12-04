"""
Tests for trade builder service.

Tests the TradeBuilder service functionality including multi-team management,
move validation, and trade validation logic.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from config import get_config
from services.trade_builder import (
    TradeBuilder,
    TradeValidationResult,
    get_trade_builder,
    get_trade_builder_by_team,
    clear_trade_builder,
    clear_trade_builder_by_team,
    _active_trade_builders,
    _team_to_trade_key,
)
from models.trade import TradeStatus
from models.team import RosterType, Team
from tests.factories import PlayerFactory, TeamFactory


class TestTradeBuilder:
    """Test TradeBuilder functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.user_id = 12345
        self.team1 = TeamFactory.west_virginia()
        self.team2 = TeamFactory.new_york()
        self.team3 = TeamFactory.create(id=3, abbrev="BOS", sname="Red Sox")

        self.player1 = PlayerFactory.mike_trout()
        self.player2 = PlayerFactory.mookie_betts()

        # Clear any existing trade builders
        _active_trade_builders.clear()

    def test_trade_builder_initialization(self):
        """Test TradeBuilder initialization."""
        builder = TradeBuilder(self.user_id, self.team1, season=12)

        assert builder.trade.initiated_by == self.user_id
        assert builder.trade.season == 12
        assert builder.trade.status == TradeStatus.DRAFT
        assert builder.team_count == 1  # Initiating team is added automatically
        assert builder.is_empty  # No moves yet
        assert builder.move_count == 0

        # Check that initiating team is in participants
        initiating_participant = builder.trade.get_participant_by_team_id(self.team1.id)
        assert initiating_participant is not None
        assert initiating_participant.team == self.team1

    @pytest.mark.asyncio
    async def test_add_team(self):
        """Test adding teams to a trade."""
        builder = TradeBuilder(self.user_id, self.team1, season=12)

        # Add second team
        success, error = await builder.add_team(self.team2)
        assert success
        assert error == ""
        assert builder.team_count == 2

        # Add third team
        success, error = await builder.add_team(self.team3)
        assert success
        assert error == ""
        assert builder.team_count == 3
        assert builder.trade.is_multi_team_trade

        # Try to add same team again
        success, error = await builder.add_team(self.team2)
        assert not success
        assert "already participating" in error
        assert builder.team_count == 3  # No change

    @pytest.mark.asyncio
    async def test_remove_team(self):
        """Test removing teams from a trade."""
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)
        await builder.add_team(self.team3)

        assert builder.team_count == 3

        # Remove team3 (no moves)
        success, error = await builder.remove_team(self.team3.id)
        assert success
        assert error == ""
        assert builder.team_count == 2

        # Try to remove non-existent team
        success, error = await builder.remove_team(999)
        assert not success
        assert "not participating" in error

    @pytest.mark.asyncio
    async def test_add_player_move(self):
        """Test adding player moves to a trade."""
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Set player's team_id to team1
        self.player1.team_id = self.team1.id

        # Mock team_service to return team1 for this player
        with patch('services.trade_builder.team_service') as mock_team_service:
            mock_team_service.get_team = AsyncMock(return_value=self.team1)

            # Don't mock is_same_organization - let the real method work
            # Add player move from team1 to team2
            success, error = await builder.add_player_move(
                player=self.player1,
                from_team=self.team1,
                to_team=self.team2,
                from_roster=RosterType.MAJOR_LEAGUE,
                to_roster=RosterType.MAJOR_LEAGUE
            )

            assert success
            assert error == ""
            assert not builder.is_empty
            assert builder.move_count > 0

            # Check that move appears in both teams' lists
            team1_participant = builder.trade.get_participant_by_team_id(self.team1.id)
            team2_participant = builder.trade.get_participant_by_team_id(self.team2.id)

            assert len(team1_participant.moves_giving) == 1
            assert len(team2_participant.moves_receiving) == 1

            # Try to add same player again (should fail - either because already involved
            # or because team mismatch)
            success, error = await builder.add_player_move(
                player=self.player1,
                from_team=self.team2,
                to_team=self.team1,
                from_roster=RosterType.MAJOR_LEAGUE,
                to_roster=RosterType.MAJOR_LEAGUE
            )

            assert not success
            # Could fail for either reason - player already in trade or team mismatch
            assert ("already involved" in error) or ("not eligible" in error.lower())

    @pytest.mark.asyncio
    async def test_add_player_move_from_free_agency_fails(self):
        """Test that adding a player from Free Agency fails."""
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Create a player on Free Agency
        fa_player = PlayerFactory.create(
            id=100,
            name="FA Player",
            team_id=get_config().free_agent_team_id
        )

        # Try to add player from FA (should fail)
        success, error = await builder.add_player_move(
            player=fa_player,
            from_team=self.team1,
            to_team=self.team2,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.MAJOR_LEAGUE
        )

        assert not success
        assert "Free Agency" in error
        assert builder.is_empty  # No moves should be added

    @pytest.mark.asyncio
    async def test_add_player_move_no_team_fails(self):
        """Test that adding a player without a team assignment fails."""
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Create a player without a team
        no_team_player = PlayerFactory.create(
            id=101,
            name="No Team Player",
            team_id=None
        )

        # Try to add player without team (should fail)
        success, error = await builder.add_player_move(
            player=no_team_player,
            from_team=self.team1,
            to_team=self.team2,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.MAJOR_LEAGUE
        )

        assert not success
        assert "does not have a valid team assignment" in error
        assert builder.is_empty

    @pytest.mark.asyncio
    async def test_add_player_move_wrong_organization_fails(self):
        """Test that adding a player from wrong organization fails."""
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Create a player on team3 (not in trade)
        player_on_team3 = PlayerFactory.create(
            id=102,
            name="Team3 Player",
            team_id=self.team3.id
        )

        # Mock team_service to return team3 for this player
        with patch('services.trade_builder.team_service') as mock_team_service:
            mock_team_service.get_team = AsyncMock(return_value=self.team3)

            # Mock is_same_organization to return False (different organization, sync method)
            with patch('models.team.Team.is_same_organization', return_value=False):
                # Try to add player from team3 claiming it's from team1 (should fail)
                success, error = await builder.add_player_move(
                    player=player_on_team3,
                    from_team=self.team1,
                    to_team=self.team2,
                    from_roster=RosterType.MAJOR_LEAGUE,
                    to_roster=RosterType.MAJOR_LEAGUE
                )

                assert not success
                assert "BOS" in error  # Team3's abbreviation
                assert "not eligible" in error.lower()
                assert builder.is_empty

    @pytest.mark.asyncio
    async def test_add_player_move_from_same_organization_succeeds(self):
        """Test that adding a player from correct organization succeeds."""
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Create a player on team1's minor league affiliate
        player_on_team1_mil = PlayerFactory.create(
            id=103,
            name="Team1 MiL Player",
            team_id=999  # Some MiL team ID
        )

        # Mock team_service to return the MiL team
        mil_team = TeamFactory.create(id=999, abbrev="WVMiL", sname="West Virginia MiL")

        with patch('services.trade_builder.team_service') as mock_team_service:
            mock_team_service.get_team = AsyncMock(return_value=mil_team)

            # Mock is_same_organization to return True (same organization, sync method)
            with patch('models.team.Team.is_same_organization', return_value=True):
                # Add player from WVMiL (should succeed because it's same organization as WV)
                success, error = await builder.add_player_move(
                    player=player_on_team1_mil,
                    from_team=self.team1,
                    to_team=self.team2,
                    from_roster=RosterType.MINOR_LEAGUE,
                    to_roster=RosterType.MAJOR_LEAGUE
                )

                assert success
                assert error == ""
                assert not builder.is_empty

    @pytest.mark.asyncio
    async def test_add_supplementary_move(self):
        """Test adding supplementary moves to a trade."""
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Add supplementary move within team1
        success, error = await builder.add_supplementary_move(
            team=self.team1,
            player=self.player1,
            from_roster=RosterType.MINOR_LEAGUE,
            to_roster=RosterType.MAJOR_LEAGUE
        )

        assert success
        assert error == ""

        # Check that move appears in team1's supplementary moves
        team1_participant = builder.trade.get_participant_by_team_id(self.team1.id)
        assert len(team1_participant.supplementary_moves) == 1

        # Try to add supplementary move for team not in trade
        success, error = await builder.add_supplementary_move(
            team=self.team3,
            player=self.player2,
            from_roster=RosterType.MINOR_LEAGUE,
            to_roster=RosterType.MAJOR_LEAGUE
        )

        assert not success
        assert "not participating" in error

    @pytest.mark.asyncio
    async def test_remove_move(self):
        """Test removing moves from a trade."""
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Set player's team_id to team1
        self.player1.team_id = self.team1.id

        # Mock team_service for adding the player
        with patch('services.trade_builder.team_service') as mock_team_service:
            mock_team_service.get_team = AsyncMock(return_value=self.team1)

            # Add a player move
            await builder.add_player_move(
                player=self.player1,
                from_team=self.team1,
                to_team=self.team2,
                from_roster=RosterType.MAJOR_LEAGUE,
                to_roster=RosterType.MAJOR_LEAGUE
            )

        assert not builder.is_empty

        # Remove the move
        success, error = await builder.remove_move(self.player1.id)
        assert success
        assert error == ""

        # Check that move is removed from both teams
        team1_participant = builder.trade.get_participant_by_team_id(self.team1.id)
        team2_participant = builder.trade.get_participant_by_team_id(self.team2.id)

        assert len(team1_participant.moves_giving) == 0
        assert len(team2_participant.moves_receiving) == 0

        # Try to remove non-existent move
        success, error = await builder.remove_move(999)
        assert not success
        assert "No move found" in error

    @pytest.mark.asyncio
    async def test_validate_trade_empty(self):
        """Test validation of empty trade."""
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Mock the transaction builders
        with patch.object(builder, '_get_or_create_builder') as mock_get_builder:
            mock_builder1 = MagicMock()
            mock_builder2 = MagicMock()

            # Set up mock validation results
            from services.transaction_builder import RosterValidationResult

            valid_result = RosterValidationResult(
                is_legal=True,
                major_league_count=24,
                minor_league_count=5,
                warnings=[],
                errors=[],
                suggestions=[]
            )

            mock_builder1.validate_transaction = AsyncMock(return_value=valid_result)
            mock_builder2.validate_transaction = AsyncMock(return_value=valid_result)

            def get_builder_side_effect(team):
                if team.id == self.team1.id:
                    return mock_builder1
                elif team.id == self.team2.id:
                    return mock_builder2
                return MagicMock()

            mock_get_builder.side_effect = get_builder_side_effect

            # Add the builders to the internal dict
            builder._team_builders[self.team1.id] = mock_builder1
            builder._team_builders[self.team2.id] = mock_builder2

            # Validate empty trade (should have trade-level errors)
            validation = await builder.validate_trade()
            assert not validation.is_legal  # Empty trade should be invalid
            assert len(validation.trade_errors) > 0

    @pytest.mark.asyncio
    async def test_validate_trade_with_moves(self):
        """Test validation of trade with balanced moves."""
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Mock the transaction builders
        with patch.object(builder, '_get_or_create_builder') as mock_get_builder:
            mock_builder1 = MagicMock()
            mock_builder2 = MagicMock()

            # Set up mock validation results
            from services.transaction_builder import RosterValidationResult

            valid_result = RosterValidationResult(
                is_legal=True,
                major_league_count=24,
                minor_league_count=5,
                warnings=[],
                errors=[],
                suggestions=[]
            )

            mock_builder1.validate_transaction = AsyncMock(return_value=valid_result)
            mock_builder2.validate_transaction = AsyncMock(return_value=valid_result)

            # Configure add_move methods to return expected tuple (success, error_message)
            mock_builder1.add_move.return_value = (True, "")
            mock_builder2.add_move.return_value = (True, "")

            def get_builder_side_effect(team):
                if team.id == self.team1.id:
                    return mock_builder1
                elif team.id == self.team2.id:
                    return mock_builder2
                return MagicMock()

            mock_get_builder.side_effect = get_builder_side_effect

            # Add the builders to the internal dict
            builder._team_builders[self.team1.id] = mock_builder1
            builder._team_builders[self.team2.id] = mock_builder2

            # Set player team_ids
            self.player1.team_id = self.team1.id
            self.player2.team_id = self.team2.id

            # Mock team_service for validation
            async def get_team_side_effect(team_id):
                if team_id == self.team1.id:
                    return self.team1
                elif team_id == self.team2.id:
                    return self.team2
                return None

            with patch('services.trade_builder.team_service') as mock_team_service:
                mock_team_service.get_team = AsyncMock(side_effect=get_team_side_effect)

                # Add balanced moves - no need to mock is_same_organization
                await builder.add_player_move(
                    player=self.player1,
                    from_team=self.team1,
                    to_team=self.team2,
                    from_roster=RosterType.MAJOR_LEAGUE,
                    to_roster=RosterType.MAJOR_LEAGUE
                )

                await builder.add_player_move(
                    player=self.player2,
                    from_team=self.team2,
                    to_team=self.team1,
                    from_roster=RosterType.MAJOR_LEAGUE,
                    to_roster=RosterType.MAJOR_LEAGUE
                )

            # Validate balanced trade
            validation = await builder.validate_trade()

            # Should be valid now (balanced trade with valid rosters)
            assert validation.is_legal
            assert len(validation.participant_validations) == 2

    def test_clear_trade(self):
        """Test clearing a trade."""
        builder = TradeBuilder(self.user_id, self.team1, season=12)

        # Add some data
        builder.trade.add_participant(self.team2)
        team1_participant = builder.trade.get_participant_by_team_id(self.team1.id)
        team1_participant.moves_giving.append(MagicMock())

        assert not builder.is_empty

        # Clear the trade
        builder.clear_trade()

        # Check that all moves are cleared
        assert builder.is_empty
        team1_participant = builder.trade.get_participant_by_team_id(self.team1.id)
        assert len(team1_participant.moves_giving) == 0

    def test_get_trade_summary(self):
        """Test trade summary generation."""
        builder = TradeBuilder(self.user_id, self.team1, season=12)

        # Initially just one team
        summary = builder.get_trade_summary()
        assert "WV" in summary

        # Add second team
        builder.trade.add_participant(self.team2)
        summary = builder.get_trade_summary()
        assert "WV" in summary and "NY" in summary


class TestTradeAcceptance:
    """
    Test trade acceptance tracking functionality.

    The acceptance system allows multi-GM approval of trades before they are finalized.
    Each participating team's GM must accept the trade before it can be converted to
    transactions and posted to the database.
    """

    def setup_method(self):
        """Set up test fixtures."""
        self.user_id = 12345
        self.team1 = TeamFactory.west_virginia()
        self.team2 = TeamFactory.new_york()
        self.team3 = TeamFactory.create(id=3, abbrev="BOS", sname="Red Sox")

        # Clear any existing trade builders
        _active_trade_builders.clear()

    def test_initial_acceptance_state(self):
        """
        Test that a new trade has no acceptances.

        When a trade is first created, no teams should be marked as accepted
        since acceptance happens after the trade is submitted for approval.
        """
        builder = TradeBuilder(self.user_id, self.team1, season=12)

        assert builder.accepted_teams == set()
        assert not builder.all_teams_accepted
        assert builder.pending_teams == [self.team1]
        assert not builder.has_team_accepted(self.team1.id)

    def test_accept_trade_single_team(self):
        """
        Test single team acceptance.

        When only one team is in the trade and accepts, all_teams_accepted
        should return True since all participating teams (just 1) have accepted.
        """
        builder = TradeBuilder(self.user_id, self.team1, season=12)

        # Accept trade as team1
        all_accepted = builder.accept_trade(self.team1.id)

        assert all_accepted  # Only one team, so should be True
        assert builder.has_team_accepted(self.team1.id)
        assert builder.all_teams_accepted
        assert builder.pending_teams == []

    @pytest.mark.asyncio
    async def test_accept_trade_two_teams(self):
        """
        Test acceptance workflow with two teams.

        Both teams must accept before all_teams_accepted returns True.
        This tests the core multi-GM acceptance requirement.
        """
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Team1 accepts first
        all_accepted = builder.accept_trade(self.team1.id)
        assert not all_accepted  # Team2 hasn't accepted yet
        assert builder.has_team_accepted(self.team1.id)
        assert not builder.has_team_accepted(self.team2.id)
        assert builder.pending_teams == [self.team2]

        # Team2 accepts second
        all_accepted = builder.accept_trade(self.team2.id)
        assert all_accepted  # Now all teams have accepted
        assert builder.has_team_accepted(self.team2.id)
        assert builder.all_teams_accepted
        assert builder.pending_teams == []

    @pytest.mark.asyncio
    async def test_accept_trade_three_teams(self):
        """
        Test acceptance workflow with three teams (multi-team trade).

        Multi-team trades require all participating teams to accept.
        This validates proper handling of 3+ team trades.
        """
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)
        await builder.add_team(self.team3)

        # First team accepts
        all_accepted = builder.accept_trade(self.team1.id)
        assert not all_accepted
        assert len(builder.pending_teams) == 2

        # Second team accepts
        all_accepted = builder.accept_trade(self.team2.id)
        assert not all_accepted
        assert len(builder.pending_teams) == 1

        # Third team accepts
        all_accepted = builder.accept_trade(self.team3.id)
        assert all_accepted
        assert len(builder.pending_teams) == 0

    @pytest.mark.asyncio
    async def test_reject_trade_clears_acceptances(self):
        """
        Test that rejecting a trade clears all acceptances.

        When any team rejects, the trade goes back to DRAFT status and
        all previous acceptances are cleared so teams can renegotiate.
        """
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Both teams accept
        builder.accept_trade(self.team1.id)
        builder.accept_trade(self.team2.id)
        assert builder.all_teams_accepted

        # Reject trade
        builder.reject_trade()

        # All acceptances should be cleared
        assert builder.accepted_teams == set()
        assert not builder.all_teams_accepted
        assert not builder.has_team_accepted(self.team1.id)
        assert not builder.has_team_accepted(self.team2.id)
        assert len(builder.pending_teams) == 2

    @pytest.mark.asyncio
    async def test_reject_trade_changes_status_to_draft(self):
        """
        Test that rejecting a trade moves status back to DRAFT.

        DRAFT status allows teams to continue modifying the trade
        before re-submitting for approval.
        """
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Change status to PROPOSED (simulating submission)
        builder.trade.status = TradeStatus.PROPOSED
        assert builder.trade.status == TradeStatus.PROPOSED

        # Reject trade
        builder.reject_trade()

        # Status should be back to DRAFT
        assert builder.trade.status == TradeStatus.DRAFT

    @pytest.mark.asyncio
    async def test_get_acceptance_status(self):
        """
        Test getting acceptance status for all teams.

        The get_acceptance_status method returns a dictionary mapping
        each team's ID to their acceptance status (True/False).
        """
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Initial status - both False
        status = builder.get_acceptance_status()
        assert status == {self.team1.id: False, self.team2.id: False}

        # After team1 accepts
        builder.accept_trade(self.team1.id)
        status = builder.get_acceptance_status()
        assert status == {self.team1.id: True, self.team2.id: False}

        # After both accept
        builder.accept_trade(self.team2.id)
        status = builder.get_acceptance_status()
        assert status == {self.team1.id: True, self.team2.id: True}

    @pytest.mark.asyncio
    async def test_duplicate_acceptance_is_idempotent(self):
        """
        Test that accepting twice has no adverse effects.

        GMs might click the Accept button multiple times. The system should
        handle this gracefully by treating it as idempotent.
        """
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Team1 accepts once
        builder.accept_trade(self.team1.id)
        assert len(builder.accepted_teams) == 1

        # Team1 accepts again (idempotent)
        builder.accept_trade(self.team1.id)
        assert len(builder.accepted_teams) == 1  # Still just 1
        assert builder.has_team_accepted(self.team1.id)

    @pytest.mark.asyncio
    async def test_pending_teams_returns_correct_order(self):
        """
        Test that pending_teams returns teams in participation order.

        The order of pending teams should match the order they were added
        to the trade for consistent display in the UI.
        """
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)
        await builder.add_team(self.team3)

        # All teams pending initially
        pending = builder.pending_teams
        assert len(pending) == 3
        assert pending[0].id == self.team1.id
        assert pending[1].id == self.team2.id
        assert pending[2].id == self.team3.id

        # After middle team accepts, order preserved for remaining
        builder.accept_trade(self.team2.id)
        pending = builder.pending_teams
        assert len(pending) == 2
        assert pending[0].id == self.team1.id
        assert pending[1].id == self.team3.id

    @pytest.mark.asyncio
    async def test_acceptance_survives_trade_modifications(self):
        """
        Test that acceptances are independent of trade move changes.

        Note: In real usage, the UI should prevent modifications after
        submission, but the data model doesn't enforce this coupling.
        """
        builder = TradeBuilder(self.user_id, self.team1, season=12)
        await builder.add_team(self.team2)

        # Team1 accepts
        builder.accept_trade(self.team1.id)
        assert builder.has_team_accepted(self.team1.id)

        # Clear trade moves (would require UI re-submission in real use)
        builder.clear_trade()

        # Acceptance is still recorded (UI should handle re-submission flow)
        assert builder.has_team_accepted(self.team1.id)


class TestTradeBuilderCache:
    """Test trade builder cache functionality."""

    def setup_method(self):
        """Clear cache before each test."""
        _active_trade_builders.clear()
        _team_to_trade_key.clear()

    def test_get_trade_builder(self):
        """Test getting trade builder from cache."""
        user_id = 12345
        team = TeamFactory.west_virginia()

        # First call should create new builder
        builder1 = get_trade_builder(user_id, team)
        assert builder1 is not None
        assert len(_active_trade_builders) == 1

        # Second call should return same builder
        builder2 = get_trade_builder(user_id, team)
        assert builder2 is builder1

    def test_clear_trade_builder(self):
        """Test clearing trade builder from cache."""
        user_id = 12345
        team = TeamFactory.west_virginia()

        # Create builder
        builder = get_trade_builder(user_id, team)
        assert len(_active_trade_builders) == 1

        # Clear builder
        clear_trade_builder(user_id)
        assert len(_active_trade_builders) == 0

        # Next call should create new builder
        new_builder = get_trade_builder(user_id, team)
        assert new_builder is not builder

    def test_get_trade_builder_registers_initiating_team(self):
        """
        Test that get_trade_builder registers the initiating team in the secondary index.

        The secondary index allows any GM in the trade to access the builder by team ID,
        enabling multi-GM participation in trades.
        """
        user_id = 12345
        team = TeamFactory.west_virginia()

        # Create builder
        builder = get_trade_builder(user_id, team)

        # Secondary index should have initiating team mapped
        assert team.id in _team_to_trade_key
        assert _team_to_trade_key[team.id] == f"{user_id}:trade"

    def test_get_trade_builder_by_team_returns_builder(self):
        """
        Test that get_trade_builder_by_team returns the correct builder for a team.

        This is the core function that enables any GM in a trade to access the builder.
        """
        user_id = 12345
        team1 = TeamFactory.west_virginia()
        team2 = TeamFactory.new_york()

        # Create builder and add second team
        builder = get_trade_builder(user_id, team1)
        builder.trade.add_participant(team2)
        # Manually add to secondary index (simulating add_team)
        _team_to_trade_key[team2.id] = f"{user_id}:trade"

        # Both teams should find the same builder
        found_by_team1 = get_trade_builder_by_team(team1.id)
        found_by_team2 = get_trade_builder_by_team(team2.id)

        assert found_by_team1 is builder
        assert found_by_team2 is builder

    def test_get_trade_builder_by_team_returns_none_for_nonparticipant(self):
        """
        Test that get_trade_builder_by_team returns None for a team not in any trade.

        This ensures proper error handling when a GM tries to access a trade they're not part of.
        """
        user_id = 12345
        team1 = TeamFactory.west_virginia()
        team3 = TeamFactory.create(id=999, abbrev="POR", name="Portland")  # Non-participant

        # Create builder with team1
        get_trade_builder(user_id, team1)

        # team3 should not find any builder
        found = get_trade_builder_by_team(team3.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_add_team_registers_in_secondary_index(self):
        """
        Test that add_team registers the new team in the secondary index.

        This ensures that when a new team joins a trade, their GM can immediately
        access the trade builder.
        """
        user_id = 12345
        team1 = TeamFactory.west_virginia()
        team2 = TeamFactory.new_york()

        # Create builder
        builder = get_trade_builder(user_id, team1)

        # Add second team
        success, error = await builder.add_team(team2)
        assert success

        # Both teams should be in secondary index
        assert team1.id in _team_to_trade_key
        assert team2.id in _team_to_trade_key
        assert _team_to_trade_key[team1.id] == _team_to_trade_key[team2.id]

        # Both teams should find the same builder
        assert get_trade_builder_by_team(team1.id) is builder
        assert get_trade_builder_by_team(team2.id) is builder

    @pytest.mark.asyncio
    async def test_remove_team_clears_from_secondary_index(self):
        """
        Test that remove_team clears the team from the secondary index.

        This ensures that when a team is removed from a trade, their GM can no
        longer access the trade builder.
        """
        user_id = 12345
        team1 = TeamFactory.west_virginia()
        team2 = TeamFactory.new_york()

        # Create builder and add team2
        builder = get_trade_builder(user_id, team1)
        await builder.add_team(team2)

        # Both teams should be in index
        assert team1.id in _team_to_trade_key
        assert team2.id in _team_to_trade_key

        # Remove team2
        success, error = await builder.remove_team(team2.id)
        assert success

        # team2 should be removed from index, team1 should remain
        assert team1.id in _team_to_trade_key
        assert team2.id not in _team_to_trade_key

    def test_clear_trade_builder_clears_secondary_index(self):
        """
        Test that clear_trade_builder removes all teams from secondary index.

        This ensures that when a trade is cleared, all participating GMs lose access.
        """
        user_id = 12345
        team1 = TeamFactory.west_virginia()
        team2 = TeamFactory.new_york()

        # Create builder and manually add team2 to secondary index
        builder = get_trade_builder(user_id, team1)
        builder.trade.add_participant(team2)
        _team_to_trade_key[team2.id] = f"{user_id}:trade"

        # Both teams in index
        assert team1.id in _team_to_trade_key
        assert team2.id in _team_to_trade_key

        # Clear trade builder
        clear_trade_builder(user_id)

        # Both teams should be removed from index
        assert team1.id not in _team_to_trade_key
        assert team2.id not in _team_to_trade_key

    def test_clear_trade_builder_by_team_clears_all_participants(self):
        """
        Test that clear_trade_builder_by_team removes all teams from secondary index.

        This allows any GM in the trade to clear it, and ensures all participants
        lose access simultaneously.
        """
        user_id = 12345
        team1 = TeamFactory.west_virginia()
        team2 = TeamFactory.new_york()

        # Create builder and manually add team2 to secondary index
        builder = get_trade_builder(user_id, team1)
        builder.trade.add_participant(team2)
        _team_to_trade_key[team2.id] = f"{user_id}:trade"

        # Both teams in index
        assert team1.id in _team_to_trade_key
        assert team2.id in _team_to_trade_key

        # Clear using team2's ID (non-initiator)
        result = clear_trade_builder_by_team(team2.id)
        assert result is True

        # Both teams should be removed from index
        assert team1.id not in _team_to_trade_key
        assert team2.id not in _team_to_trade_key
        assert len(_active_trade_builders) == 0

    def test_clear_trade_builder_by_team_returns_false_for_nonparticipant(self):
        """
        Test that clear_trade_builder_by_team returns False for non-participating team.

        This ensures proper error handling when a GM not in the trade tries to clear it.
        """
        team3 = TeamFactory.create(id=999, abbrev="POR", name="Portland")  # Non-participant

        result = clear_trade_builder_by_team(team3.id)
        assert result is False


class TestTradeValidationResult:
    """Test TradeValidationResult functionality."""

    def test_validation_result_aggregation(self):
        """Test aggregation of validation results."""
        result = TradeValidationResult()

        # Add trade-level errors
        result.trade_errors = ["Trade error 1", "Trade error 2"]
        result.trade_warnings = ["Trade warning 1"]
        result.trade_suggestions = ["Trade suggestion 1"]

        # Mock participant validations
        from services.transaction_builder import RosterValidationResult

        team1_validation = RosterValidationResult(
            is_legal=False,
            major_league_count=24,
            minor_league_count=5,
            warnings=["Team1 warning"],
            errors=["Team1 error"],
            suggestions=["Team1 suggestion"]
        )

        team2_validation = RosterValidationResult(
            is_legal=True,
            major_league_count=25,
            minor_league_count=4,
            warnings=[],
            errors=[],
            suggestions=[]
        )

        result.participant_validations[1] = team1_validation
        result.participant_validations[2] = team2_validation
        result.is_legal = False  # One team has errors

        # Test aggregated results
        all_errors = result.all_errors
        assert len(all_errors) == 3  # 2 trade + 1 team
        assert "Trade error 1" in all_errors
        assert "Team1 error" in all_errors

        all_warnings = result.all_warnings
        assert len(all_warnings) == 2  # 1 trade + 1 team
        assert "Trade warning 1" in all_warnings
        assert "Team1 warning" in all_warnings

        all_suggestions = result.all_suggestions
        assert len(all_suggestions) == 2  # 1 trade + 1 team
        assert "Trade suggestion 1" in all_suggestions
        assert "Team1 suggestion" in all_suggestions

        # Test participant validation lookup
        team1_val = result.get_participant_validation(1)
        assert team1_val == team1_validation

        non_existent = result.get_participant_validation(999)
        assert non_existent is None

    def test_validation_result_empty_state(self):
        """Test empty validation result."""
        result = TradeValidationResult()

        assert result.is_legal  # Default is True
        assert len(result.all_errors) == 0
        assert len(result.all_warnings) == 0
        assert len(result.all_suggestions) == 0
        assert len(result.participant_validations) == 0