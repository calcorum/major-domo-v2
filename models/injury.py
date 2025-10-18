"""
Injury model for tracking player injuries

Represents an injury record with game timeline and status information.
"""
from typing import Optional, Any, Dict
from pydantic import Field, model_validator

from models.base import SBABaseModel


class Injury(SBABaseModel):
    """Injury model representing a player injury."""

    # Override base model to make id required for database entities
    id: int = Field(..., description="Injury ID from database")

    season: int = Field(..., description="Season number")
    player_id: int = Field(..., description="Player ID who is injured")
    total_games: int = Field(..., description="Total games player will be out")

    @model_validator(mode='before')
    @classmethod
    def extract_player_id(cls, data: Any) -> Any:
        """
        Extract player_id from nested player object if present.

        The API returns injuries with a nested 'player' object:
        {'id': 123, 'player': {'id': 456, ...}, ...}

        This validator extracts the player ID before validation:
        {'id': 123, 'player_id': 456, ...}
        """
        if isinstance(data, dict):
            # If player_id is missing but player object exists, extract it
            if 'player_id' not in data and 'player' in data:
                if isinstance(data['player'], dict) and 'id' in data['player']:
                    data['player_id'] = data['player']['id']

        return data

    # Injury timeline
    start_week: int = Field(..., description="Week injury started")
    start_game: int = Field(..., description="Game number injury started (1-4)")
    end_week: int = Field(..., description="Week player returns")
    end_game: int = Field(..., description="Game number player returns (1-4)")

    # Status
    is_active: bool = Field(True, description="Whether injury is currently active")

    @property
    def return_date(self) -> str:
        """Format return date as 'w##g#' string."""
        return f'w{self.end_week:02d}g{self.end_game}'

    @property
    def start_date(self) -> str:
        """Format start date as 'w##g#' string."""
        return f'w{self.start_week:02d}g{self.start_game}'

    @property
    def duration_display(self) -> str:
        """Return a human-readable duration string."""
        if self.total_games == 1:
            return "1 game"
        return f"{self.total_games} games"

    def __str__(self):
        status = "Active" if self.is_active else "Cleared"
        return f"Injury (Season {self.season}, {self.duration_display}, {status})"
