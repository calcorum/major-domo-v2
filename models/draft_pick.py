"""
Draft pick model

Represents individual draft picks with team and player relationships.
"""
from typing import Optional
from pydantic import Field

from models.base import SBABaseModel
from models.team import Team
from models.player import Player


class DraftPick(SBABaseModel):
    """Draft pick model representing a single draft selection."""
    
    season: int = Field(..., description="Draft season")
    overall: int = Field(..., description="Overall pick number")
    round: int = Field(..., description="Draft round")
    
    # Team relationships - IDs are required, objects are optional
    origowner_id: int = Field(..., description="Original owning team ID")
    origowner: Optional[Team] = Field(None, description="Original owning team (populated when needed)")
    
    owner_id: Optional[int] = Field(None, description="Current owning team ID")
    owner: Optional[Team] = Field(None, description="Current owning team (populated when needed)")
    
    # Player selection
    player_id: Optional[int] = Field(None, description="Selected player ID")
    player: Optional[Player] = Field(None, description="Selected player (populated when needed)")
    
    @property
    def is_traded(self) -> bool:
        """Check if this pick has been traded."""
        return self.origowner_id != self.owner_id
    
    @property
    def is_selected(self) -> bool:
        """Check if a player has been selected with this pick."""
        return self.player_id is not None
    
    def __str__(self):
        team_str = f"({self.owner.abbrev})" if self.owner else f"(Team {self.owner_id})"
        if self.is_selected and self.player:
            return f"Pick {self.overall}: {self.player.name} {team_str}"
        else:
            return f"Pick {self.overall}: Available {team_str}"