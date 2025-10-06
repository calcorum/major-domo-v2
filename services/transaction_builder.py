"""
Transaction Builder Service

Handles the complex logic for building multi-move transactions interactively.
"""
import logging
from typing import Dict, List, Optional, Tuple, Set
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone

from models.transaction import Transaction
from models.team import Team
from models.player import Player
from models.roster import TeamRoster
from services.player_service import player_service
from services.team_service import team_service
from services.roster_service import roster_service
from services.transaction_service import transaction_service
from services.league_service import league_service
from models.team import RosterType
from constants import SBA_CURRENT_SEASON

logger = logging.getLogger(f'{__name__}.TransactionBuilder')


# Removed MoveAction enum - using simple from/to roster locations instead


@dataclass
class TransactionMove:
    """Individual move within a transaction."""
    player: Player
    from_roster: RosterType
    to_roster: RosterType
    from_team: Optional[Team] = None
    to_team: Optional[Team] = None
    
    @property
    def description(self) -> str:
        """Human readable move description."""
        # Determine emoji and format based on from/to locations
        if self.from_roster == RosterType.FREE_AGENCY and self.to_roster != RosterType.FREE_AGENCY:
            # Add from Free Agency
            emoji = "➕"
            return f"{emoji} {self.player.name}: FA → {self.to_team.abbrev} ({self.to_roster.value.upper()})"
        elif self.from_roster != RosterType.FREE_AGENCY and self.to_roster == RosterType.FREE_AGENCY:
            # Drop to Free Agency
            emoji = "➖"
            return f"{emoji} {self.player.name}: {self.from_team.abbrev} ({self.from_roster.value.upper()}) → FA"
        elif self.from_roster == RosterType.MINOR_LEAGUE and self.to_roster == RosterType.MAJOR_LEAGUE:
            # Recall from MiL to ML
            emoji = "⬆️"
            return f"{emoji} {self.player.name}: {self.from_team.abbrev} (MiL) → {self.to_team.abbrev} (ML)"
        elif self.from_roster == RosterType.MAJOR_LEAGUE and self.to_roster == RosterType.MINOR_LEAGUE:
            # Demote from ML to MiL
            emoji = "⬇️"
            return f"{emoji} {self.player.name}: {self.from_team.abbrev} (ML) → {self.to_team.abbrev} (MiL)"
        elif self.to_roster == RosterType.INJURED_LIST:
            # Move to Injured List
            emoji = "🏥"
            from_desc = "FA" if self.from_roster == RosterType.FREE_AGENCY else f"{self.from_team.abbrev} ({self.from_roster.value.upper()})"
            return f"{emoji} {self.player.name}: {from_desc} → {self.to_team.abbrev} (IL)"
        elif self.from_roster == RosterType.INJURED_LIST:
            # Return from Injured List
            emoji = "💊"
            to_desc = "FA" if self.to_roster == RosterType.FREE_AGENCY else f"{self.to_team.abbrev} ({self.to_roster.value.upper()})"
            return f"{emoji} {self.player.name}: {self.from_team.abbrev} (IL) → {to_desc}"
        else:
            # Generic move
            emoji = "🔄"
            from_desc = "FA" if self.from_roster == RosterType.FREE_AGENCY else f"{self.from_team.abbrev} ({self.from_roster.value.upper()})"
            to_desc = "FA" if self.to_roster == RosterType.FREE_AGENCY else f"{self.to_team.abbrev} ({self.to_roster.value.upper()})"
            return f"{emoji} {self.player.name}: {from_desc} → {to_desc}"


@dataclass
class RosterValidationResult:
    """Results of roster validation."""
    is_legal: bool
    major_league_count: int
    minor_league_count: int
    warnings: List[str]
    errors: List[str]
    suggestions: List[str]
    major_league_limit: int = 26
    minor_league_limit: int = 6
    major_league_swar: float = 0.0
    minor_league_swar: float = 0.0
    pre_existing_ml_swar_change: float = 0.0
    pre_existing_mil_swar_change: float = 0.0
    pre_existing_transaction_count: int = 0
    
    @property
    def major_league_status(self) -> str:
        """Status string for major league roster."""
        if self.major_league_count > self.major_league_limit:
            return f"❌ Major League: {self.major_league_count}/{self.major_league_limit} (Over limit!)"
        else:
            return f"✅ Major League: {self.major_league_count}/{self.major_league_limit} (Legal)"
    
    @property
    def minor_league_status(self) -> str:
        """Status string for minor league roster."""
        if self.minor_league_count > self.minor_league_limit:
            return f"❌ Minor League: {self.minor_league_count}/{self.minor_league_limit} (Over limit!)"
        else:
            return f"✅ Minor League: {self.minor_league_count}/{self.minor_league_limit} (Legal)"

    @property
    def major_league_swar_status(self) -> str:
        """Status string for major league sWAR."""
        return f"📊 Major League sWAR: {self.major_league_swar:.2f}"

    @property
    def minor_league_swar_status(self) -> str:
        """Status string for minor league sWAR."""
        return f"📊 Minor League sWAR: {self.minor_league_swar:.2f}"

    @property
    def pre_existing_transactions_note(self) -> str:
        """Note about pre-existing transactions affecting calculations."""
        if self.pre_existing_transaction_count == 0:
            return ""

        total_swar_change = self.pre_existing_ml_swar_change + self.pre_existing_mil_swar_change

        if total_swar_change == 0:
            return f"ℹ️ **Pre-existing Moves**: {self.pre_existing_transaction_count} scheduled moves (no sWAR impact)"
        elif total_swar_change > 0:
            return f"ℹ️ **Pre-existing Moves**: {self.pre_existing_transaction_count} scheduled moves (+{total_swar_change:.2f} sWAR)"
        else:
            return f"ℹ️ **Pre-existing Moves**: {self.pre_existing_transaction_count} scheduled moves ({total_swar_change:.2f} sWAR)"


class TransactionBuilder:
    """Interactive transaction builder for complex multi-move transactions."""
    
    def __init__(self, team: Team, user_id: int, season: int = SBA_CURRENT_SEASON):
        """
        Initialize transaction builder.
        
        Args:
            team: Team making the transaction
            user_id: Discord user ID of the GM
            season: Season number
        """
        self.team = team
        self.user_id = user_id
        self.season = season
        self.moves: List[TransactionMove] = []
        self.created_at = datetime.now(timezone.utc)
        
        # Cache for roster data
        self._current_roster: Optional[TeamRoster] = None
        self._roster_loaded = False

        # Cache for pre-existing transactions
        self._existing_transactions: Optional[List[Transaction]] = None
        self._existing_transactions_loaded = False

        logger.info(f"TransactionBuilder initialized for {team.abbrev} by user {user_id}")
    
    async def load_roster_data(self) -> None:
        """Load current roster data for the team."""
        if self._roster_loaded:
            return

        try:
            self._current_roster = await roster_service.get_current_roster(self.team.id)
            self._roster_loaded = True
            logger.debug(f"Loaded roster data for team {self.team.abbrev}")
        except Exception as e:
            logger.error(f"Failed to load roster data: {e}")
            self._current_roster = None
            self._roster_loaded = True

    async def load_existing_transactions(self, next_week: int) -> None:
        """Load pre-existing transactions for next week."""
        if self._existing_transactions_loaded:
            return

        try:
            self._existing_transactions = await transaction_service.get_team_transactions(
                team_abbrev=self.team.abbrev,
                season=self.season,
                cancelled=False,
                week_start=next_week
            )
            self._existing_transactions_loaded = True
            logger.debug(f"Loaded {len(self._existing_transactions or [])} existing transactions for {self.team.abbrev} week {next_week}")
        except Exception as e:
            logger.error(f"Failed to load existing transactions: {e}")
            self._existing_transactions = []
            self._existing_transactions_loaded = True
    
    def add_move(self, move: TransactionMove) -> tuple[bool, str]:
        """
        Add a move to the transaction.

        Args:
            move: TransactionMove to add

        Returns:
            Tuple of (success: bool, error_message: str). If success is True, error_message is empty.
        """
        # Check if player is already in a move
        existing_move = self.get_move_for_player(move.player.id)
        if existing_move:
            error_msg = f"Player {move.player.name} already has a move in this transaction"
            logger.warning(error_msg)
            return False, error_msg

        # Check if from_team and to_team are the same AND from_roster and to_roster are the same
        # (when both teams are not None) - this would be a meaningless move
        if (move.from_team is not None and move.to_team is not None and
            move.from_team.id == move.to_team.id and move.from_roster == move.to_roster):
            error_msg = f"Cannot move {move.player.name} from {move.from_team.abbrev} ({move.from_roster.value.upper()}) to {move.to_team.abbrev} ({move.to_roster.value.upper()}) - player is already in that location"
            logger.warning(error_msg)
            return False, error_msg

        self.moves.append(move)
        logger.info(f"Added move: {move.description}")
        return True, ""
    
    def remove_move(self, player_id: int) -> bool:
        """
        Remove a move for a specific player.
        
        Args:
            player_id: ID of player to remove move for
            
        Returns:
            True if move was removed
        """
        original_count = len(self.moves)
        self.moves = [move for move in self.moves if move.player.id != player_id]
        
        removed = len(self.moves) < original_count
        if removed:
            logger.info(f"Removed move for player {player_id}")
        
        return removed
    
    def get_move_for_player(self, player_id: int) -> Optional[TransactionMove]:
        """Get the move for a specific player if it exists."""
        for move in self.moves:
            if move.player.id == player_id:
                return move
        return None
    
    async def validate_transaction(self, next_week: Optional[int] = None) -> RosterValidationResult:
        """
        Validate the current transaction and return detailed results.

        Args:
            next_week: Week to check for existing transactions (optional)

        Returns:
            RosterValidationResult with validation details
        """
        await self.load_roster_data()

        # Load existing transactions if next_week is provided
        if next_week is not None:
            await self.load_existing_transactions(next_week)
        
        if not self._current_roster:
            return RosterValidationResult(
                is_legal=False,
                major_league_count=0,
                minor_league_count=0, 
                warnings=[],
                errors=["Could not load current roster data"],
                suggestions=[]
            )
        
        # Calculate roster changes from moves
        ml_changes = 0
        mil_changes = 0
        errors = []
        warnings = []
        suggestions = []

        # Calculate current sWAR for each roster
        current_ml_swar = sum(player.wara for player in self._current_roster.active_players)
        current_mil_swar = sum(player.wara for player in self._current_roster.minor_league_players)

        # Track sWAR changes from moves
        ml_swar_changes = 0.0
        mil_swar_changes = 0.0

        # Track pre-existing transaction changes separately
        pre_existing_ml_swar_change = 0.0
        pre_existing_mil_swar_change = 0.0
        pre_existing_count = 0

        # Process existing transactions first
        if self._existing_transactions:
            for transaction in self._existing_transactions:
                # Skip if this transaction was already processed or cancelled
                if transaction.cancelled:
                    continue

                pre_existing_count += 1

                # Determine roster changes from existing transaction
                # Use Team.is_same_organization() to check if transaction affects our organization

                # Leaving our organization (from any roster)
                if transaction.oldteam.is_same_organization(self.team):
                    # Player leaving our organization - determine which roster they're leaving from
                    from_roster_type = transaction.oldteam.roster_type()

                    if from_roster_type == RosterType.MAJOR_LEAGUE:
                        ml_changes -= 1
                        ml_swar_changes -= transaction.player.wara
                        pre_existing_ml_swar_change -= transaction.player.wara
                    elif from_roster_type == RosterType.MINOR_LEAGUE:
                        mil_changes -= 1
                        mil_swar_changes -= transaction.player.wara
                        pre_existing_mil_swar_change -= transaction.player.wara
                    # Note: IL players don't count toward roster limits, so no changes needed

                # Joining our organization (to any roster)
                if transaction.newteam.is_same_organization(self.team):
                    # Player joining our organization - determine which roster they're joining
                    to_roster_type = transaction.newteam.roster_type()

                    if to_roster_type == RosterType.MAJOR_LEAGUE:
                        ml_changes += 1
                        ml_swar_changes += transaction.player.wara
                        pre_existing_ml_swar_change += transaction.player.wara
                    elif to_roster_type == RosterType.MINOR_LEAGUE:
                        mil_changes += 1
                        mil_swar_changes += transaction.player.wara
                        pre_existing_mil_swar_change += transaction.player.wara
                    # Note: IL players don't count toward roster limits, so no changes needed

        for move in self.moves:
            # Calculate roster changes based on from/to locations
            if move.from_roster == RosterType.MAJOR_LEAGUE:
                ml_changes -= 1
                ml_swar_changes -= move.player.wara
            elif move.from_roster == RosterType.MINOR_LEAGUE:
                mil_changes -= 1
                mil_swar_changes -= move.player.wara
            # Note: INJURED_LIST and FREE_AGENCY don't count toward ML roster limit

            if move.to_roster == RosterType.MAJOR_LEAGUE:
                ml_changes += 1
                ml_swar_changes += move.player.wara
            elif move.to_roster == RosterType.MINOR_LEAGUE:
                mil_changes += 1
                mil_swar_changes += move.player.wara
            # Note: INJURED_LIST and FREE_AGENCY don't count toward ML roster limit
        
        # Calculate projected roster sizes and sWAR
        # Only Major League players count toward ML roster limit (IL and MiL are separate)
        current_ml_size = len(self._current_roster.active_players)
        current_mil_size = len(self._current_roster.minor_league_players)

        projected_ml_size = current_ml_size + ml_changes
        projected_mil_size = current_mil_size + mil_changes
        projected_ml_swar = current_ml_swar + ml_swar_changes
        projected_mil_swar = current_mil_swar + mil_swar_changes
        
        # Get current week to determine roster limits
        try:
            current_state = await league_service.get_current_state()
            current_week = current_state.week if current_state else 1
        except Exception as e:
            logger.warning(f"Could not get current week, using default limits: {e}")
            current_week = 1
        
        # Determine roster limits based on week
        # Major league: <=26 if week<=14, <=25 if week>14  
        # Minor league: <=6 if week<=14, <=14 if week>14
        if current_week <= 14:
            ml_limit = 26
            mil_limit = 6
        else:
            ml_limit = 25
            mil_limit = 14
        
        # Validate roster limits
        is_legal = True
        if projected_ml_size > ml_limit:
            is_legal = False
            errors.append(f"Major League roster would have {projected_ml_size} players (limit: {ml_limit})")
            suggestions.append(f"Drop {projected_ml_size - ml_limit} ML player(s) to make roster legal")
        elif projected_ml_size < 0:
            is_legal = False
            errors.append("Cannot have negative players on Major League roster")
        
        if projected_mil_size > mil_limit:
            is_legal = False
            errors.append(f"Minor League roster would have {projected_mil_size} players (limit: {mil_limit})")
            suggestions.append(f"Drop {projected_mil_size - mil_limit} MiL player(s) to make roster legal")
        elif projected_mil_size < 0:
            is_legal = False  
            errors.append("Cannot have negative players on Minor League roster")
        
        # Add suggestions for empty transaction
        if not self.moves:
            suggestions.append("Add player moves to build your transaction")
        
        return RosterValidationResult(
            is_legal=is_legal,
            major_league_count=projected_ml_size,
            minor_league_count=projected_mil_size,
            warnings=warnings,
            errors=errors,
            suggestions=suggestions,
            major_league_limit=ml_limit,
            minor_league_limit=mil_limit,
            major_league_swar=projected_ml_swar,
            minor_league_swar=projected_mil_swar,
            pre_existing_ml_swar_change=pre_existing_ml_swar_change,
            pre_existing_mil_swar_change=pre_existing_mil_swar_change,
            pre_existing_transaction_count=pre_existing_count
        )
    
    async def submit_transaction(self, week: int) -> List[Transaction]:
        """
        Submit the transaction by creating individual Transaction models.
        
        Args:
            week: Week the transaction is effective for
            
        Returns:
            List of created Transaction objects
        """
        if not self.moves:
            raise ValueError("Cannot submit empty transaction")
        
        validation = await self.validate_transaction(next_week=week)
        if not validation.is_legal:
            raise ValueError(f"Cannot submit illegal transaction: {', '.join(validation.errors)}")
        
        transactions = []
        move_id = f"Season-{self.season:03d}-Week-{week:02d}-{int(self.created_at.timestamp())}"
        
        # Create FA team for drops
        fa_team = Team(
            id=503,  # Standard FA team ID
            abbrev="FA",
            sname="Free Agents", 
            lname="Free Agency",
            season=self.season
        ) # type: ignore
        
        for move in self.moves:
            # Determine old and new teams based on roster locations
            if move.from_roster == RosterType.FREE_AGENCY:
                old_team = fa_team
            else:
                old_team = move.from_team or self.team
                
            if move.to_roster == RosterType.FREE_AGENCY:
                new_team = fa_team
            else:
                new_team = move.to_team or self.team
            
            # For cases where we don't have specific teams, fall back to defaults
            if not old_team:
                continue
            
            # Create transaction
            transaction = Transaction(
                id=0,  # Will be set by API
                week=week,
                season=self.season,
                moveid=move_id,
                player=move.player,
                oldteam=old_team,
                newteam=new_team,
                cancelled=False,
                frozen=False
            )
            
            transactions.append(transaction)
        
        logger.info(f"Created {len(transactions)} transactions for submission with move_id {move_id}")
        return transactions
    
    def clear_moves(self) -> None:
        """Clear all moves from the transaction builder."""
        self.moves.clear()
        logger.info("Cleared all moves from transaction builder")
    
    @property
    def is_empty(self) -> bool:
        """Check if transaction builder has no moves."""
        return len(self.moves) == 0
    
    @property
    def move_count(self) -> int:
        """Get total number of moves in transaction."""
        return len(self.moves)


# Global cache for active transaction builders
_active_builders: Dict[int, TransactionBuilder] = {}


def get_transaction_builder(user_id: int, team: Team) -> TransactionBuilder:
    """
    Get or create a transaction builder for a user.
    
    Args:
        user_id: Discord user ID
        team: Team object
        
    Returns:
        TransactionBuilder instance
    """
    if user_id not in _active_builders:
        _active_builders[user_id] = TransactionBuilder(team, user_id)
    
    return _active_builders[user_id]


def clear_transaction_builder(user_id: int) -> None:
    """Clear transaction builder for a user."""
    if user_id in _active_builders:
        del _active_builders[user_id]
        logger.info(f"Cleared transaction builder for user {user_id}")