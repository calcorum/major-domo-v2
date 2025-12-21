"""
Trade Builder Service

Extends the TransactionBuilder to support multi-team trades and player exchanges.
"""
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone
import uuid

from config import get_config
from models.trade import Trade, TradeParticipant, TradeMove, TradeStatus
from models.team import Team, RosterType
from models.player import Player
from services.transaction_builder import TransactionBuilder, RosterValidationResult, TransactionMove
from services.team_service import team_service
from services.roster_service import roster_service
from services.league_service import league_service

logger = logging.getLogger(f'{__name__}.TradeBuilder')


class TradeValidationResult:
    """Results of trade validation across all participating teams."""

    def __init__(self):
        self.is_legal: bool = True
        self.participant_validations: Dict[int, RosterValidationResult] = {}
        self.trade_errors: List[str] = []
        self.trade_warnings: List[str] = []
        self.trade_suggestions: List[str] = []

    @property
    def all_errors(self) -> List[str]:
        """Get all errors including trade-level and roster-level errors."""
        errors = self.trade_errors.copy()
        for validation in self.participant_validations.values():
            errors.extend(validation.errors)
        return errors

    @property
    def all_warnings(self) -> List[str]:
        """Get all warnings across trade and roster levels."""
        warnings = self.trade_warnings.copy()
        for validation in self.participant_validations.values():
            warnings.extend(validation.warnings)
        return warnings

    @property
    def all_suggestions(self) -> List[str]:
        """Get all suggestions across trade and roster levels."""
        suggestions = self.trade_suggestions.copy()
        for validation in self.participant_validations.values():
            suggestions.extend(validation.suggestions)
        return suggestions

    def get_participant_validation(self, team_id: int) -> Optional[RosterValidationResult]:
        """Get validation result for a specific team."""
        return self.participant_validations.get(team_id)


class TradeBuilder:
    """
    Interactive trade builder for multi-team player exchanges.

    Extends the functionality of TransactionBuilder to support trades between teams.
    """

    def __init__(self, initiated_by: int, initiating_team: Team, season: int = get_config().sba_season):
        """
        Initialize trade builder.

        Args:
            initiated_by: Discord user ID who initiated the trade
            initiating_team: Team that initiated the trade
            season: Season number
        """
        self.trade = Trade(
            trade_id=str(uuid.uuid4())[:8],  # Short trade ID
            participants=[],
            status=TradeStatus.DRAFT,
            initiated_by=initiated_by,
            created_at=datetime.now(timezone.utc).isoformat(),
            season=season
        )

        # Add the initiating team as first participant
        self.trade.add_participant(initiating_team)

        # Cache transaction builders for each participating team
        self._team_builders: Dict[int, TransactionBuilder] = {}

        # Track which teams have accepted the trade (team_id -> True)
        self.accepted_teams: Set[int] = set()

        logger.info(f"TradeBuilder initialized: {self.trade.trade_id} by user {initiated_by} for {initiating_team.abbrev}")

    @property
    def trade_id(self) -> str:
        """Get the trade ID."""
        return self.trade.trade_id

    @property
    def participating_teams(self) -> List[Team]:
        """Get all participating teams."""
        return self.trade.participating_teams

    @property
    def team_count(self) -> int:
        """Get number of participating teams."""
        return self.trade.team_count

    @property
    def is_empty(self) -> bool:
        """Check if trade has no moves."""
        return self.trade.total_moves == 0

    @property
    def move_count(self) -> int:
        """Get total number of moves in trade."""
        return self.trade.total_moves

    @property
    def all_teams_accepted(self) -> bool:
        """Check if all participating teams have accepted the trade."""
        participating_ids = {team.id for team in self.participating_teams}
        return participating_ids == self.accepted_teams

    @property
    def pending_teams(self) -> List[Team]:
        """Get list of teams that haven't accepted yet."""
        return [team for team in self.participating_teams if team.id not in self.accepted_teams]

    def accept_trade(self, team_id: int) -> bool:
        """
        Record a team's acceptance of the trade.

        Args:
            team_id: ID of the team accepting

        Returns:
            True if all teams have now accepted, False otherwise
        """
        self.accepted_teams.add(team_id)
        logger.info(f"Team {team_id} accepted trade {self.trade_id}. Accepted: {len(self.accepted_teams)}/{self.team_count}")
        return self.all_teams_accepted

    def reject_trade(self) -> None:
        """
        Reject the trade, moving it back to DRAFT status.

        Clears all acceptances so teams can renegotiate.
        """
        self.accepted_teams.clear()
        self.trade.status = TradeStatus.DRAFT
        logger.info(f"Trade {self.trade_id} rejected and moved back to DRAFT")

    def get_acceptance_status(self) -> Dict[int, bool]:
        """
        Get acceptance status for each participating team.

        Returns:
            Dict mapping team_id to acceptance status (True/False)
        """
        return {team.id: team.id in self.accepted_teams for team in self.participating_teams}

    def has_team_accepted(self, team_id: int) -> bool:
        """Check if a specific team has accepted."""
        return team_id in self.accepted_teams

    async def add_team(self, team: Team) -> tuple[bool, str]:
        """
        Add a team to the trade.

        Args:
            team: Team to add

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        # Check if team is already participating
        if self.trade.get_participant_by_team_id(team.id):
            return False, f"{team.abbrev} is already participating in this trade"

        # Add team to trade
        participant = self.trade.add_participant(team)

        # Create transaction builder for this team
        self._team_builders[team.id] = TransactionBuilder(team, self.trade.initiated_by, self.trade.season)

        # Register team in secondary index for multi-GM access
        trade_key = f"{self.trade.initiated_by}:trade"
        _team_to_trade_key[team.id] = trade_key

        logger.info(f"Added team {team.abbrev} to trade {self.trade_id}")
        return True, ""

    async def remove_team(self, team_id: int) -> tuple[bool, str]:
        """
        Remove a team from the trade.

        Args:
            team_id: ID of team to remove

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        participant = self.trade.get_participant_by_team_id(team_id)
        if not participant:
            return False, "Team is not participating in this trade"

        # Check if team has moves - prevent removal if they do
        if participant.all_moves:
            return False, f"{participant.team.abbrev} has moves in this trade and cannot be removed"

        # Remove team
        removed = self.trade.remove_participant(team_id)
        if removed:
            if team_id in self._team_builders:
                del self._team_builders[team_id]
            # Remove from secondary index
            if team_id in _team_to_trade_key:
                del _team_to_trade_key[team_id]
            logger.info(f"Removed team {team_id} from trade {self.trade_id}")

        return removed, "" if removed else "Failed to remove team"

    async def add_player_move(
        self,
        player: Player,
        from_team: Team,
        to_team: Team,
        from_roster: RosterType,
        to_roster: RosterType
    ) -> tuple[bool, str]:
        """
        Add a player move to the trade.

        Args:
            player: Player being moved
            from_team: Team giving up the player
            to_team: Team receiving the player
            from_roster: Source roster type
            to_roster: Destination roster type

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        # Validate player is not from Free Agency
        if player.team_id == get_config().free_agent_team_id:
            return False, f"Cannot add {player.name} from Free Agency. Players must be traded from teams within the organizations involved in the trade."

        # Validate player has a valid team assignment
        if not player.team_id:
            return False, f"{player.name} does not have a valid team assignment"

        # Validate that from_team matches the player's actual team organization
        player_team = await team_service.get_team(player.team_id)
        if not player_team:
            return False, f"Could not find team for {player.name}"

        # Check if player's team is in the same organization as from_team
        if not player_team.is_same_organization(from_team):
            return False, f"{player.name} is on {player_team.abbrev}, they are not eligible to be added to the trade."

        # Ensure both teams are participating (check by organization for ML authority)
        from_participant = self.trade.get_participant_by_organization(from_team)
        to_participant = self.trade.get_participant_by_organization(to_team)

        if not from_participant:
            return False, f"{from_team.abbrev} is not participating in this trade"
        if not to_participant:
            return False, f"{to_team.abbrev} is not participating in this trade"

        # Check if player is already involved in a move
        for participant in self.trade.participants:
            for existing_move in participant.all_moves:
                if existing_move.player.id == player.id:
                    return False, f"{player.name} is already involved in a move in this trade"

        # Create trade move
        trade_move = TradeMove(
            player=player,
            from_roster=from_roster,
            to_roster=to_roster,
            from_team=from_team,
            to_team=to_team,
            source_team=from_team,
            destination_team=to_team
        )

        # Add to giving team's moves
        from_participant.moves_giving.append(trade_move)

        # Add to receiving team's moves
        to_participant.moves_receiving.append(trade_move)

        # Create corresponding transaction moves for each team's builder
        from_builder = self._get_or_create_builder(from_team)
        to_builder = self._get_or_create_builder(to_team)

        # Move for giving team (player leaving)
        from_move = TransactionMove(
            player=player,
            from_roster=from_roster,
            to_roster=RosterType.FREE_AGENCY,  # Conceptually leaving the org
            from_team=from_team,
            to_team=None
        )

        # Move for receiving team (player joining)
        to_move = TransactionMove(
            player=player,
            from_roster=RosterType.FREE_AGENCY,  # Conceptually joining from outside
            to_roster=to_roster,
            from_team=None,
            to_team=to_team
        )

        # Add moves to respective builders
        # Skip pending transaction check for trades - they have their own validation workflow
        from_success, from_error = await from_builder.add_move(from_move, check_pending_transactions=False)
        if not from_success:
            # Remove from trade if builder failed
            from_participant.moves_giving.remove(trade_move)
            to_participant.moves_receiving.remove(trade_move)
            return False, f"Error adding move to {from_team.abbrev}: {from_error}"

        to_success, to_error = await to_builder.add_move(to_move, check_pending_transactions=False)
        if not to_success:
            # Rollback both if second failed
            from_builder.remove_move(player.id)
            from_participant.moves_giving.remove(trade_move)
            to_participant.moves_receiving.remove(trade_move)
            return False, f"Error adding move to {to_team.abbrev}: {to_error}"

        logger.info(f"Added player move to trade {self.trade_id}: {trade_move.description}")
        return True, ""

    async def add_supplementary_move(
        self,
        team: Team,
        player: Player,
        from_roster: RosterType,
        to_roster: RosterType
    ) -> tuple[bool, str]:
        """
        Add a supplementary move (internal organizational move) for roster legality.

        Args:
            team: Team making the internal move
            player: Player being moved
            from_roster: Source roster type
            to_roster: Destination roster type

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        participant = self.trade.get_participant_by_organization(team)
        if not participant:
            return False, f"{team.abbrev} is not participating in this trade"

        # Create supplementary move (internal to organization)
        supp_move = TradeMove(
            player=player,
            from_roster=from_roster,
            to_roster=to_roster,
            from_team=team,
            to_team=team,
            source_team=team,
            destination_team=team
        )

        # Add to participant's supplementary moves
        participant.supplementary_moves.append(supp_move)

        # Add to team's transaction builder
        builder = self._get_or_create_builder(team)
        trans_move = TransactionMove(
            player=player,
            from_roster=from_roster,
            to_roster=to_roster,
            from_team=team,
            to_team=team
        )

        # Skip pending transaction check for trade supplementary moves
        success, error = await builder.add_move(trans_move, check_pending_transactions=False)
        if not success:
            participant.supplementary_moves.remove(supp_move)
            return False, error

        logger.info(f"Added supplementary move for {team.abbrev}: {supp_move.description}")
        return True, ""

    async def remove_move(self, player_id: int) -> tuple[bool, str]:
        """
        Remove a move from the trade.

        Args:
            player_id: ID of player whose move to remove

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        # Find and remove the move from all participants
        removed_move = None
        for participant in self.trade.participants:
            # Check moves_giving
            for move in participant.moves_giving[:]:
                if move.player.id == player_id:
                    participant.moves_giving.remove(move)
                    removed_move = move
                    break

            # Check moves_receiving
            for move in participant.moves_receiving[:]:
                if move.player.id == player_id:
                    participant.moves_receiving.remove(move)
                    # Don't set removed_move again, we already got it from giving
                    break

            # Check supplementary_moves
            for move in participant.supplementary_moves[:]:
                if move.player.id == player_id:
                    participant.supplementary_moves.remove(move)
                    removed_move = move
                    break

        if not removed_move:
            return False, "No move found for that player"

        # Remove from transaction builders
        for builder in self._team_builders.values():
            builder.remove_move(player_id)

        logger.info(f"Removed move from trade {self.trade_id}: {removed_move.description}")
        return True, ""

    async def validate_trade(self, next_week: Optional[int] = None) -> TradeValidationResult:
        """
        Validate the entire trade including all teams' roster legality.

        Args:
            next_week: Week to validate for (optional)

        Returns:
            TradeValidationResult with comprehensive validation
        """
        result = TradeValidationResult()

        # Validate trade structure
        is_balanced, balance_errors = self.trade.validate_trade_balance()
        if not is_balanced:
            result.is_legal = False
            result.trade_errors.extend(balance_errors)

        # Validate each team's roster after the trade
        for participant in self.trade.participants:
            team_id = participant.team.id
            if team_id in self._team_builders:
                builder = self._team_builders[team_id]
                roster_validation = await builder.validate_transaction(next_week)

                result.participant_validations[team_id] = roster_validation

                if not roster_validation.is_legal:
                    result.is_legal = False

        # Add trade-level suggestions
        if self.is_empty:
            result.trade_suggestions.append("Add player moves to build your trade")

        if self.team_count < 2:
            result.trade_suggestions.append("Add another team to create a trade")

        logger.debug(f"Trade validation for {self.trade_id}: Legal={result.is_legal}, Errors={len(result.all_errors)}")
        return result

    def _get_or_create_builder(self, team: Team) -> TransactionBuilder:
        """Get or create a transaction builder for a team."""
        if team.id not in self._team_builders:
            self._team_builders[team.id] = TransactionBuilder(team, self.trade.initiated_by, self.trade.season)
        return self._team_builders[team.id]

    def clear_trade(self) -> None:
        """Clear all moves from the trade."""
        for participant in self.trade.participants:
            participant.moves_giving.clear()
            participant.moves_receiving.clear()
            participant.supplementary_moves.clear()

        for builder in self._team_builders.values():
            builder.clear_moves()

        logger.info(f"Cleared all moves from trade {self.trade_id}")

    def get_trade_summary(self) -> str:
        """Get human-readable trade summary."""
        return self.trade.get_trade_summary()


# Global cache for active trade builders
_active_trade_builders: Dict[str, TradeBuilder] = {}

# Secondary index: maps team_id -> trade_key for multi-GM access
_team_to_trade_key: Dict[int, str] = {}


def get_trade_builder(user_id: int, initiating_team: Team) -> TradeBuilder:
    """
    Get or create a trade builder for a user.

    Args:
        user_id: Discord user ID
        initiating_team: Team initiating the trade

    Returns:
        TradeBuilder instance
    """
    trade_key = f"{user_id}:trade"

    if trade_key not in _active_trade_builders:
        builder = TradeBuilder(user_id, initiating_team)
        _active_trade_builders[trade_key] = builder
        # Register initiating team in secondary index for multi-GM access
        _team_to_trade_key[initiating_team.id] = trade_key

    return _active_trade_builders[trade_key]


def get_trade_builder_by_team(team_id: int) -> Optional[TradeBuilder]:
    """
    Get trade builder that includes a specific team.

    This allows any GM whose team is participating in a trade to access
    the trade builder, not just the initiator.

    Args:
        team_id: Team ID to look up

    Returns:
        TradeBuilder if team is in an active trade, None otherwise
    """
    trade_key = _team_to_trade_key.get(team_id)
    if trade_key:
        return _active_trade_builders.get(trade_key)
    return None


def clear_trade_builder(user_id: int) -> None:
    """Clear trade builder for a user and remove all team mappings."""
    trade_key = f"{user_id}:trade"
    if trade_key in _active_trade_builders:
        # Remove all team mappings for this trade
        builder = _active_trade_builders[trade_key]
        for team in builder.participating_teams:
            if team.id in _team_to_trade_key:
                del _team_to_trade_key[team.id]

        del _active_trade_builders[trade_key]
        logger.info(f"Cleared trade builder for user {user_id}")


def clear_trade_builder_by_team(team_id: int) -> bool:
    """
    Clear trade builder that includes a specific team.

    This allows any GM in a trade to clear it, not just the initiator.

    Args:
        team_id: Team ID whose trade should be cleared

    Returns:
        True if a trade was cleared, False if no trade found
    """
    trade_key = _team_to_trade_key.get(team_id)
    if not trade_key:
        return False

    if trade_key in _active_trade_builders:
        builder = _active_trade_builders[trade_key]
        # Remove all team mappings
        for team in builder.participating_teams:
            if team.id in _team_to_trade_key:
                del _team_to_trade_key[team.id]

        del _active_trade_builders[trade_key]
        logger.info(f"Cleared trade builder via team {team_id}")
        return True

    return False


def get_active_trades() -> Dict[str, TradeBuilder]:
    """Get all active trade builders (for debugging/admin purposes)."""
    return _active_trade_builders.copy()