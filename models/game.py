"""
Game model for SBA games

Represents individual games with scores, teams, and metadata.
"""
from typing import Optional
from pydantic import Field

from models.base import SBABaseModel
from models.team import Team


class Game(SBABaseModel):
    """Game model representing an SBA game."""
    
    # Override base model to make id required for database entities
    id: int = Field(..., description="Game ID from database")
    
    # Game metadata
    season: int = Field(..., description="Season number")
    week: int = Field(..., description="Week number")
    game_num: Optional[int] = Field(None, description="Game number within series")
    season_type: str = Field(..., description="Season type (regular/playoff)")
    
    # Teams
    away_team: Team = Field(..., description="Away team object")
    home_team: Team = Field(..., description="Home team object")
    
    # Scores (optional for future games)
    away_score: Optional[int] = Field(None, description="Away team score")
    home_score: Optional[int] = Field(None, description="Home team score")
    
    # Managers (who managed this specific game)
    away_manager: Optional[dict] = Field(None, description="Away team manager for this game")
    home_manager: Optional[dict] = Field(None, description="Home team manager for this game")
    
    # Links
    scorecard_url: Optional[str] = Field(None, description="Google Sheets scorecard URL")
    
    @property
    def is_completed(self) -> bool:
        """Check if the game has been played (has scores)."""
        return self.away_score is not None and self.home_score is not None
    
    @property
    def winner(self) -> Optional[Team]:
        """Get the winning team (if game is completed)."""
        if not self.is_completed:
            return None
        return self.home_team if self.home_score > self.away_score else self.away_team
    
    @property
    def loser(self) -> Optional[Team]:
        """Get the losing team (if game is completed)."""
        if not self.is_completed:
            return None
        return self.away_team if self.home_score > self.away_score else self.home_team
    
    @property
    def score_display(self) -> str:
        """Display score as string."""
        if not self.is_completed:
            return "vs"
        return f"{self.away_score}-{self.home_score}"
    
    @property
    def matchup_display(self) -> str:
        """Display matchup with score/@."""
        if self.is_completed:
            return f"{self.away_team.abbrev} {self.score_display} {self.home_team.abbrev}"
        else:
            return f"{self.away_team.abbrev} @ {self.home_team.abbrev}"
    
    @property
    def series_game_display(self) -> Optional[str]:
        """Display series game number if available."""
        if self.game_num:
            return f"Game {self.game_num}"
        return None
    
    def __str__(self):
        return f"Week {self.week}: {self.matchup_display}"