"""
Standings model for SBA teams

Represents team standings with wins, losses, and playoff positioning.
"""
from typing import Optional
from pydantic import Field

from models.base import SBABaseModel
from models.team import Team


class TeamStandings(SBABaseModel):
    """Team standings model representing league position and record."""
    
    # Override base model to make id required for database entities
    id: int = Field(..., description="Standings ID from database")
    
    # Team information
    team: Team = Field(..., description="Team object with full details")
    
    # Win/Loss record
    wins: int = Field(..., description="Total wins")
    losses: int = Field(..., description="Total losses")
    run_diff: int = Field(..., description="Run differential (runs scored - runs allowed)")
    
    # Playoff positioning
    div_gb: Optional[float] = Field(None, description="Games behind division leader")
    div_e_num: Optional[int] = Field(None, description="Division elimination number")
    wc_gb: Optional[float] = Field(None, description="Games behind wild card")
    wc_e_num: Optional[int] = Field(None, description="Wild card elimination number")
    
    # Home/Away splits
    home_wins: int = Field(..., description="Home wins")
    home_losses: int = Field(..., description="Home losses")
    away_wins: int = Field(..., description="Away wins") 
    away_losses: int = Field(..., description="Away losses")
    
    # Recent performance
    last8_wins: int = Field(..., description="Wins in last 8 games")
    last8_losses: int = Field(..., description="Losses in last 8 games")
    streak_wl: str = Field(..., description="Current streak type (w/l)")
    streak_num: int = Field(..., description="Current streak length")
    
    # Close games
    one_run_wins: int = Field(..., description="One-run game wins")
    one_run_losses: int = Field(..., description="One-run game losses")
    
    # Pythagorean record (expected wins/losses based on run differential)
    pythag_wins: int = Field(..., description="Pythagorean wins")
    pythag_losses: int = Field(..., description="Pythagorean losses")
    
    # Divisional records
    div1_wins: int = Field(..., description="Division 1 wins")
    div1_losses: int = Field(..., description="Division 1 losses")
    div2_wins: int = Field(..., description="Division 2 wins")
    div2_losses: int = Field(..., description="Division 2 losses")
    div3_wins: int = Field(..., description="Division 3 wins")
    div3_losses: int = Field(..., description="Division 3 losses")
    div4_wins: int = Field(..., description="Division 4 wins")
    div4_losses: int = Field(..., description="Division 4 losses")
    
    @property
    def games_played(self) -> int:
        """Total games played."""
        return self.wins + self.losses
    
    @property
    def winning_percentage(self) -> float:
        """Winning percentage."""
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played
    
    @property
    def home_record(self) -> str:
        """Home record as string."""
        return f"{self.home_wins}-{self.home_losses}"
    
    @property
    def away_record(self) -> str:
        """Away record as string."""
        return f"{self.away_wins}-{self.away_losses}"
    
    @property
    def last8_record(self) -> str:
        """Last 8 games record as string."""
        return f"{self.last8_wins}-{self.last8_losses}"
    
    @property
    def current_streak(self) -> str:
        """Current streak formatted as string."""
        streak_type = "W" if self.streak_wl.lower() == "w" else "L"
        return f"{streak_type}{self.streak_num}"
    
    @property
    def division_gb_display(self) -> str:
        """Division games behind display."""
        if self.div_gb is None:
            return "-"
        elif self.div_gb == 0.0:
            return "-"
        else:
            return f"{self.div_gb:.1f}"
    
    @property 
    def wild_card_gb_display(self) -> str:
        """Wild card games behind display."""
        if self.wc_gb is None:
            return "-"
        elif self.wc_gb <= 0.0:
            return "-"
        else:
            return f"{self.wc_gb:.1f}"
    
    @property
    def run_diff_display(self) -> str:
        """Run differential with +/- prefix."""
        if self.run_diff > 0:
            return f"+{self.run_diff}"
        else:
            return str(self.run_diff)
    
    def __str__(self):
        return f"{self.team.abbrev} {self.wins}-{self.losses} ({self.winning_percentage:.3f})"