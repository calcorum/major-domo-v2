"""
Transaction models for SBA transaction management

Represents transactions and player moves based on actual API structure.
"""
from typing import Optional, List
from pydantic import Field

from models.base import SBABaseModel
from models.player import Player
from models.team import Team


class Transaction(SBABaseModel):
    """
    Represents a single player transaction (move).
    
    Based on actual API response structure:
    {
        "id": 27787,
        "week": 10,
        "player": { ... },
        "oldteam": { ... },
        "newteam": { ... },
        "season": 12,
        "moveid": "Season-012-Week-10-19-13:04:41",
        "cancelled": false,
        "frozen": false
    }
    """
    
    # Core transaction fields
    id: int = Field(..., description="Transaction ID")
    week: int = Field(..., description="Week this transaction is for")
    season: int = Field(..., description="Season number")
    moveid: str = Field(..., description="Unique move identifier string")
    
    # Player and team information
    player: Player = Field(..., description="Player being moved")
    oldteam: Team = Field(..., description="Team player is leaving")
    newteam: Team = Field(..., description="Team player is joining")
    
    # Transaction status
    cancelled: bool = Field(default=False, description="Whether transaction is cancelled")
    frozen: bool = Field(default=False, description="Whether transaction is frozen")
    
    @property
    def is_cancelled(self) -> bool:
        """Check if transaction is cancelled."""
        return self.cancelled
    
    @property
    def is_frozen(self) -> bool:
        """Check if transaction is frozen (scheduled for processing)."""
        return self.frozen
    
    @property
    def is_pending(self) -> bool:
        """Check if transaction is pending (not frozen, not cancelled)."""
        return not self.frozen and not self.cancelled
    
    @property
    def status_emoji(self) -> str:
        """Emoji representation of transaction status."""
        if self.cancelled:
            return "❌"
        elif self.frozen:
            return "❄️"
        else:
            return "⏳"
    
    @property
    def status_text(self) -> str:
        """Human readable status."""
        if self.cancelled:
            return "Cancelled"
        elif self.frozen:
            return "Frozen"
        else:
            return "Pending"
    
    @property
    def move_description(self) -> str:
        """Human readable description of the move."""
        return f"{self.player.name}: {self.oldteam.abbrev} → {self.newteam.abbrev}"
    
    @property
    def is_major_league_move(self) -> bool:
        """Check if this move involves major league rosters."""
        # Major league if neither team ends with 'MiL' and not FA
        from_is_major = self.oldteam.abbrev != 'FA' and not self.oldteam.abbrev.endswith('MiL')
        to_is_major = self.newteam.abbrev != 'FA' and not self.newteam.abbrev.endswith('MiL')
        return from_is_major or to_is_major
    
    def __str__(self):
        return f"📋 Week {self.week}: {self.move_description} - {self.status_emoji} {self.status_text}"


class RosterValidation(SBABaseModel):
    """Results of roster legality validation."""
    
    is_legal: bool = Field(..., description="Whether the roster is legal")
    errors: List[str] = Field(default_factory=list, description="List of validation errors")
    warnings: List[str] = Field(default_factory=list, description="List of validation warnings")
    
    # Roster statistics
    total_players: int = Field(default=0, description="Total players on roster")
    active_players: int = Field(default=0, description="Active players") 
    il_players: int = Field(default=0, description="Players on IL")
    minor_league_players: int = Field(default=0, description="Minor league players")
    
    total_sWAR: float = Field(default=0.00, description="Total team sWAR")
    
    @property
    def has_issues(self) -> bool:
        """Whether there are any errors or warnings."""
        return len(self.errors) > 0 or len(self.warnings) > 0
    
    @property
    def status_emoji(self) -> str:
        """Emoji representation of validation status."""
        if not self.is_legal:
            return "❌"
        elif self.warnings:
            return "⚠️"
        else:
            return "✅"