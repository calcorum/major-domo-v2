"""
Tests for trade-specific models.

Tests the Trade, TradeParticipant, and TradeMove models to ensure proper
validation and behavior for multi-team trades.
"""
import pytest
from unittest.mock import MagicMock

from models.trade import Trade, TradeParticipant, TradeMove, TradeStatus
from models.team import RosterType
from tests.factories import PlayerFactory, TeamFactory


class TestTradeMove:
    """Test TradeMove model functionality."""

    def test_cross_team_move_identification(self):
        """Test identification of cross-team moves."""
        team1 = TeamFactory.create(id=1, abbrev="LAA", sname="Angels")
        team2 = TeamFactory.create(id=2, abbrev="BOS", sname="Red Sox")
        player = PlayerFactory.mike_trout()

        # Cross-team move
        cross_move = TradeMove(
            player=player,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.MAJOR_LEAGUE,
            from_team=team1,
            to_team=team2,
            source_team=team1,
            destination_team=team2
        )

        assert cross_move.is_cross_team_move
        assert not cross_move.is_internal_move

        # Internal move (same team)
        internal_move = TradeMove(
            player=player,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.MINOR_LEAGUE,
            from_team=team1,
            to_team=team1,
            source_team=team1,
            destination_team=team1
        )

        assert not internal_move.is_cross_team_move
        assert internal_move.is_internal_move

    def test_trade_move_descriptions(self):
        """Test various trade move description formats."""
        team1 = TeamFactory.create(id=1, abbrev="LAA", sname="Angels")
        team2 = TeamFactory.create(id=2, abbrev="BOS", sname="Red Sox")
        player = PlayerFactory.mike_trout()

        # Team-to-team trade
        trade_move = TradeMove(
            player=player,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.MAJOR_LEAGUE,
            from_team=team1,
            to_team=team2,
            source_team=team1,
            destination_team=team2
        )

        description = trade_move.description
        assert "Mike Trout" in description
        assert "LAA" in description
        assert "BOS" in description
        assert "🔄" in description

        # Free agency acquisition
        fa_move = TradeMove(
            player=player,
            from_roster=RosterType.FREE_AGENCY,
            to_roster=RosterType.MAJOR_LEAGUE,
            from_team=None,
            to_team=team1,
            source_team=team1,  # This gets set even for FA moves
            destination_team=team1
        )

        fa_description = fa_move.description
        assert "Mike Trout" in fa_description
        assert "FA" in fa_description
        assert "LAA" in fa_description
        assert "➕" in fa_description


class TestTradeParticipant:
    """Test TradeParticipant model functionality."""

    def test_participant_initialization(self):
        """Test TradeParticipant initialization."""
        team = TeamFactory.west_virginia()

        participant = TradeParticipant(
            team=team,
            moves_giving=[],
            moves_receiving=[],
            supplementary_moves=[]
        )

        assert participant.team == team
        assert len(participant.moves_giving) == 0
        assert len(participant.moves_receiving) == 0
        assert len(participant.supplementary_moves) == 0
        assert participant.net_player_change == 0
        assert participant.is_balanced

    def test_net_player_calculations(self):
        """Test net player change calculations."""
        team = TeamFactory.new_york()

        participant = TradeParticipant(
            team=team,
            moves_giving=[MagicMock()],  # Giving 1 player
            moves_receiving=[MagicMock(), MagicMock()],  # Receiving 2 players
            supplementary_moves=[]
        )

        assert participant.net_player_change == 1  # +2 receiving, -1 giving
        assert participant.is_net_buyer
        assert not participant.is_net_seller
        assert not participant.is_balanced

        # Test net seller
        participant.moves_giving = [MagicMock(), MagicMock()]  # Giving 2
        participant.moves_receiving = [MagicMock()]  # Receiving 1

        assert participant.net_player_change == -1  # +1 receiving, -2 giving
        assert not participant.is_net_buyer
        assert participant.is_net_seller
        assert not participant.is_balanced


class TestTrade:
    """Test Trade model functionality."""

    def test_trade_initialization(self):
        """Test Trade initialization."""
        trade = Trade(
            trade_id="test123",
            participants=[],
            status=TradeStatus.DRAFT,
            initiated_by=12345,
            season=12
        )

        assert trade.trade_id == "test123"
        assert trade.status == TradeStatus.DRAFT
        assert trade.initiated_by == 12345
        assert trade.season == 12
        assert trade.team_count == 0
        assert not trade.is_multi_team_trade
        assert trade.total_moves == 0

    def test_add_participants(self):
        """Test adding participants to a trade."""
        team1 = TeamFactory.west_virginia()
        team2 = TeamFactory.new_york()

        trade = Trade(
            trade_id="test123",
            participants=[],
            status=TradeStatus.DRAFT,
            initiated_by=12345,
            season=12
        )

        # Add first team
        participant1 = trade.add_participant(team1)
        assert participant1.team == team1
        assert trade.team_count == 1
        assert not trade.is_multi_team_trade

        # Add second team
        participant2 = trade.add_participant(team2)
        assert participant2.team == team2
        assert trade.team_count == 2
        assert not trade.is_multi_team_trade  # Exactly 2 teams

        # Add third team
        team3 = TeamFactory.create(id=3, abbrev="NYY", sname="Yankees")
        participant3 = trade.add_participant(team3)
        assert trade.team_count == 3
        assert trade.is_multi_team_trade  # More than 2 teams

        # Try to add same team again (should return existing)
        participant1_again = trade.add_participant(team1)
        assert participant1_again == participant1
        assert trade.team_count == 3  # No change

    def test_participant_lookup(self):
        """Test finding participants by team ID and abbreviation."""
        team1 = TeamFactory.west_virginia()
        team2 = TeamFactory.new_york()

        trade = Trade(
            trade_id="test123",
            participants=[],
            status=TradeStatus.DRAFT,
            initiated_by=12345,
            season=12
        )

        trade.add_participant(team1)
        trade.add_participant(team2)

        # Test lookup by ID
        found_by_id = trade.get_participant_by_team_id(team1.id)
        assert found_by_id is not None
        assert found_by_id.team == team1

        # Test lookup by abbreviation
        found_by_abbrev = trade.get_participant_by_team_abbrev("NY")
        assert found_by_abbrev is not None
        assert found_by_abbrev.team == team2

        # Test case insensitive abbreviation lookup
        found_case_insensitive = trade.get_participant_by_team_abbrev("ny")
        assert found_case_insensitive is not None
        assert found_case_insensitive.team == team2

        # Test not found
        not_found_id = trade.get_participant_by_team_id(999)
        assert not_found_id is None

        not_found_abbrev = trade.get_participant_by_team_abbrev("XXX")
        assert not_found_abbrev is None

    def test_remove_participants(self):
        """Test removing participants from a trade."""
        team1 = TeamFactory.west_virginia()
        team2 = TeamFactory.new_york()

        trade = Trade(
            trade_id="test123",
            participants=[],
            status=TradeStatus.DRAFT,
            initiated_by=12345,
            season=12
        )

        trade.add_participant(team1)
        trade.add_participant(team2)
        assert trade.team_count == 2

        # Remove team1
        removed = trade.remove_participant(team1.id)
        assert removed
        assert trade.team_count == 1
        assert trade.get_participant_by_team_id(team1.id) is None
        assert trade.get_participant_by_team_id(team2.id) is not None

        # Try to remove non-existent team
        not_removed = trade.remove_participant(999)
        assert not not_removed
        assert trade.team_count == 1

    def test_trade_balance_validation(self):
        """Test trade balance validation logic."""
        team1 = TeamFactory.west_virginia()
        team2 = TeamFactory.new_york()
        player1 = PlayerFactory.mike_trout()
        player2 = PlayerFactory.mookie_betts()

        trade = Trade(
            trade_id="test123",
            participants=[],
            status=TradeStatus.DRAFT,
            initiated_by=12345,
            season=12
        )

        # Empty trade should fail
        is_valid, errors = trade.validate_trade_balance()
        assert not is_valid
        assert "at least 2 teams" in " ".join(errors)

        # Add teams but no moves
        trade.add_participant(team1)
        trade.add_participant(team2)

        is_valid, errors = trade.validate_trade_balance()
        assert not is_valid
        assert "at least one player exchange" in " ".join(errors)

        # Add moves to make it valid
        participant1 = trade.get_participant_by_team_id(team1.id)
        participant2 = trade.get_participant_by_team_id(team2.id)

        # Team1 gives Player1, Team2 receives Player1
        move1 = TradeMove(
            player=player1,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.MAJOR_LEAGUE,
            from_team=team1,
            to_team=team2,
            source_team=team1,
            destination_team=team2
        )

        participant1.moves_giving.append(move1)
        participant2.moves_receiving.append(move1)

        # Team2 gives Player2, Team1 receives Player2
        move2 = TradeMove(
            player=player2,
            from_roster=RosterType.MAJOR_LEAGUE,
            to_roster=RosterType.MAJOR_LEAGUE,
            from_team=team2,
            to_team=team1,
            source_team=team2,
            destination_team=team1
        )

        participant2.moves_giving.append(move2)
        participant1.moves_receiving.append(move2)

        is_valid, errors = trade.validate_trade_balance()
        assert is_valid
        assert len(errors) == 0

    def test_trade_summary(self):
        """Test trade summary generation."""
        team1 = TeamFactory.west_virginia()
        team2 = TeamFactory.new_york()
        team3 = TeamFactory.create(id=3, abbrev="BOS", sname="Red Sox")

        trade = Trade(
            trade_id="test123",
            participants=[],
            status=TradeStatus.DRAFT,
            initiated_by=12345,
            season=12
        )

        # Empty trade
        summary = trade.get_trade_summary()
        assert summary == "Empty trade"

        # 2-team trade
        trade.add_participant(team1)
        trade.add_participant(team2)
        summary = trade.get_trade_summary()
        assert "Trade between WV and NY" == summary

        # 3-team trade
        trade.add_participant(team3)
        summary = trade.get_trade_summary()
        assert "3-team trade: WV, NY, BOS" == summary

    def test_get_participant_by_organization(self):
        """Test finding participants by organization affiliation."""
        # Create ML, MiL, and IL teams for the same organization
        wv_ml = TeamFactory.create(id=1, abbrev="WV", sname="Black Bears")
        wv_mil = TeamFactory.create(id=2, abbrev="WVMIL", sname="Coal City Miners")
        wv_il = TeamFactory.create(id=3, abbrev="WVIL", sname="Black Bears IL")
        por_ml = TeamFactory.create(id=4, abbrev="POR", sname="Loggers")

        trade = Trade(
            trade_id="test123",
            participants=[],
            status=TradeStatus.DRAFT,
            initiated_by=12345,
            season=12
        )

        # Add only ML teams as participants
        trade.add_participant(wv_ml)
        trade.add_participant(por_ml)

        # Should find WV ML participant when looking for WV MiL or IL
        wv_participant = trade.get_participant_by_organization(wv_mil)
        assert wv_participant is not None
        assert wv_participant.team.abbrev == "WV"

        wv_participant_il = trade.get_participant_by_organization(wv_il)
        assert wv_participant_il is not None
        assert wv_participant_il.team.abbrev == "WV"

        # Should find the same participant object
        assert wv_participant == wv_participant_il

        # Should not find participant for non-participating organization
        laa_mil = TeamFactory.create(id=5, abbrev="LAAMIL", sname="Salt Lake Bees")
        laa_participant = trade.get_participant_by_organization(laa_mil)
        assert laa_participant is None