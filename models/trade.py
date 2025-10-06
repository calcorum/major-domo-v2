"""
Trade-specific data models for multi-team transactions.

Extends the base transaction system to support trades between multiple teams.
"""
from typing import List, Optional, Dict, Set
from dataclasses import dataclass
from enum import Enum

from models.player import Player
from models.team import Team, RosterType
from services.transaction_builder import TransactionMove


class TradeStatus(Enum):
    """Status of a trade negotiation."""
    DRAFT = "draft"
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class TradeMove(TransactionMove):
    """Trade-specific move with team ownership tracking."""

    # The team that is "giving up" this player (source team)
    source_team: Optional[Team] = None

    # The team that is "receiving" this player (destination team)
    destination_team: Optional[Team] = None

    @property
    def description(self) -> str:
        """Enhanced description showing team-to-team movement."""
        if self.from_roster == RosterType.FREE_AGENCY:
            # Add from Free Agency to a team
            emoji = "➕"
            dest_team_name = self.destination_team.abbrev if self.destination_team else "Unknown"
            return f"{emoji} {self.player.name}: FA → {dest_team_name} ({self.to_roster.value.upper()})"
        elif self.to_roster == RosterType.FREE_AGENCY:
            # Drop to Free Agency from a team
            emoji = "➖"
            source_team_name = self.source_team.abbrev if self.source_team else "Unknown"
            return f"{emoji} {self.player.name}: {source_team_name} ({self.from_roster.value.upper()}) → FA"
        else:
            # Team-to-team trade
            emoji = "🔄"
            source_team_name = self.source_team.abbrev if self.source_team else "Unknown"
            dest_team_name = self.destination_team.abbrev if self.destination_team else "Unknown"
            source_desc = f"{source_team_name} ({self.from_roster.value.upper()})"
            dest_desc = f"{dest_team_name} ({self.to_roster.value.upper()})"
            return f"{emoji} {self.player.name}: {source_desc} → {dest_desc}"

    @property
    def is_cross_team_move(self) -> bool:
        """Check if this move is between different teams."""
        if not self.source_team or not self.destination_team:
            return False
        return self.source_team.id != self.destination_team.id

    @property
    def is_internal_move(self) -> bool:
        """Check if this move is within the same organization."""
        if not self.source_team or not self.destination_team:
            return False
        return self.source_team.is_same_organization(self.destination_team)


@dataclass
class TradeParticipant:
    """Represents a team participating in a trade."""

    team: Team
    moves_giving: List[TradeMove]  # Players this team is giving away
    moves_receiving: List[TradeMove]  # Players this team is receiving
    supplementary_moves: List[TradeMove]  # Internal org moves for roster legality

    def __post_init__(self):
        """Initialize empty lists if not provided."""
        if not hasattr(self, 'moves_giving'):
            self.moves_giving = []
        if not hasattr(self, 'moves_receiving'):
            self.moves_receiving = []
        if not hasattr(self, 'supplementary_moves'):
            self.supplementary_moves = []

    @property
    def all_moves(self) -> List[TradeMove]:
        """Get all moves for this participant."""
        return self.moves_giving + self.moves_receiving + self.supplementary_moves

    @property
    def net_player_change(self) -> int:
        """Calculate net change in player count (positive = gaining players)."""
        return len(self.moves_receiving) - len(self.moves_giving)

    @property
    def is_net_buyer(self) -> bool:
        """Check if team is gaining more players than giving up."""
        return self.net_player_change > 0

    @property
    def is_net_seller(self) -> bool:
        """Check if team is giving up more players than receiving."""
        return self.net_player_change < 0

    @property
    def is_balanced(self) -> bool:
        """Check if team is exchanging equal numbers of players."""
        return self.net_player_change == 0


@dataclass
class Trade:
    """
    Represents a complete trade between multiple teams.

    A trade consists of multiple moves where teams exchange players.
    """

    trade_id: str
    participants: List[TradeParticipant]
    status: TradeStatus
    initiated_by: int  # Discord user ID
    created_at: Optional[str] = None  # ISO datetime string
    season: int = 12  # Default to current season

    def __post_init__(self):
        """Initialize participants list if not provided."""
        if not hasattr(self, 'participants'):
            self.participants = []

    @property
    def participating_teams(self) -> List[Team]:
        """Get all teams participating in this trade."""
        return [participant.team for participant in self.participants]

    @property
    def team_count(self) -> int:
        """Get number of teams in this trade."""
        return len(self.participants)

    @property
    def is_multi_team_trade(self) -> bool:
        """Check if this involves more than 2 teams."""
        return self.team_count > 2

    @property
    def total_moves(self) -> int:
        """Get total number of moves across all participants."""
        return sum(len(p.all_moves) for p in self.participants)

    @property
    def cross_team_moves(self) -> List[TradeMove]:
        """Get all moves that cross team boundaries (deduplicated)."""
        moves = []
        for participant in self.participants:
            # Only include moves_giving to avoid duplication (each move appears in both giving and receiving)
            moves.extend([move for move in participant.moves_giving if move.is_cross_team_move])
        return moves

    @property
    def supplementary_moves(self) -> List[TradeMove]:
        """Get all supplementary (internal) moves."""
        moves = []
        for participant in self.participants:
            moves.extend(participant.supplementary_moves)
        return moves

    def get_participant_by_team_id(self, team_id: int) -> Optional[TradeParticipant]:
        """Find participant by team ID."""
        for participant in self.participants:
            if participant.team.id == team_id:
                return participant
        return None

    def get_participant_by_team_abbrev(self, team_abbrev: str) -> Optional[TradeParticipant]:
        """Find participant by team abbreviation."""
        for participant in self.participants:
            if participant.team.abbrev.upper() == team_abbrev.upper():
                return participant
        return None

    def get_participant_by_organization(self, team: Team) -> Optional[TradeParticipant]:
        """
        Find participant by organization affiliation.

        Major League team owners control their entire organization (ML/MiL/IL),
        so if a ML team is participating, their MiL and IL teams are also valid.

        Args:
            team: Team to find participant for (can be ML, MiL, or IL)

        Returns:
            TradeParticipant if the team's organization is participating, None otherwise
        """
        for participant in self.participants:
            if participant.team.is_same_organization(team):
                return participant
        return None

    def add_participant(self, team: Team) -> TradeParticipant:
        """Add a new team to the trade."""
        existing = self.get_participant_by_team_id(team.id)
        if existing:
            return existing

        participant = TradeParticipant(
            team=team,
            moves_giving=[],
            moves_receiving=[],
            supplementary_moves=[]
        )
        self.participants.append(participant)
        return participant

    def remove_participant(self, team_id: int) -> bool:
        """Remove a team from the trade."""
        original_count = len(self.participants)
        self.participants = [p for p in self.participants if p.team.id != team_id]
        return len(self.participants) < original_count

    def validate_trade_balance(self) -> tuple[bool, List[str]]:
        """
        Validate that the trade is properly balanced.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check that we have at least 2 teams
        if self.team_count < 2:
            errors.append("Trade must involve at least 2 teams")

        # Check that there are actual cross-team moves
        if not self.cross_team_moves:
            errors.append("Trade must include at least one player exchange between teams")

        # Verify each player appears in exactly one giving move and one receiving move
        # (This check will be done by the consistency check below)

        # Check that moves are consistent (player given by one team = received by another)
        given_players = {}  # player_id -> giving_team_id
        received_players = {}  # player_id -> receiving_team_id

        for participant in self.participants:
            for move in participant.moves_giving:
                given_players[move.player.id] = participant.team.id
            for move in participant.moves_receiving:
                received_players[move.player.id] = participant.team.id

        # Every given player should be received by someone else
        for player_id, giving_team_id in given_players.items():
            if player_id not in received_players:
                errors.append(f"Player {player_id} is given up but not received by any team")
            elif received_players[player_id] == giving_team_id:
                errors.append(f"Player {player_id} cannot be given and received by the same team")

        # Every received player should be given by someone else
        for player_id, receiving_team_id in received_players.items():
            if player_id not in given_players:
                errors.append(f"Player {player_id} is received but not given up by any team")
            elif given_players[player_id] == receiving_team_id:
                errors.append(f"Player {player_id} cannot be given and received by the same team")

        return len(errors) == 0, errors

    def get_trade_summary(self) -> str:
        """Get a human-readable summary of the trade."""
        if self.team_count == 0:
            return "Empty trade"

        team_names = [p.team.abbrev for p in self.participants]

        if self.team_count == 2:
            return f"Trade between {team_names[0]} and {team_names[1]}"
        else:
            return f"{self.team_count}-team trade: {', '.join(team_names)}"