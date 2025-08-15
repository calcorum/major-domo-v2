"""
Draft preference list model

Represents team draft board rankings and preferences.
"""
from typing import Optional
from pydantic import Field

from models.base import SBABaseModel
from models.team import Team
from models.player import Player


class DraftList(SBABaseModel):
    """Draft preference list entry for a team."""
    
    season: int = Field(..., description="Draft season")
    team_id: int = Field(..., description="Team ID that owns this list entry")
    rank: int = Field(..., description="Ranking of player on team's draft board")
    player_id: int = Field(..., description="Player ID on the draft board")
    
    # Related objects (populated when needed)
    team: Optional[Team] = Field(None, description="Team object (populated when needed)")
    player: Optional[Player] = Field(None, description="Player object (populated when needed)")
    
    @property
    def is_top_ranked(self) -> bool:
        """Check if this is the team's top-ranked available player."""
        return self.rank == 1
    
    def __str__(self):
        team_str = self.team.abbrev if self.team else f"Team {self.team_id}"
        player_str = self.player.name if self.player else f"Player {self.player_id}"
        return f"{team_str} Draft Board #{self.rank}: {player_str}"