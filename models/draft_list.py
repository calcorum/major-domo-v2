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
    rank: int = Field(..., description="Ranking of player on team's draft board")

    # API returns nested objects (not just IDs)
    team: Team = Field(..., description="Team object")
    player: Player = Field(..., description="Player object")

    @property
    def team_id(self) -> int:
        """Extract team ID from nested team object."""
        return self.team.id

    @property
    def player_id(self) -> int:
        """Extract player ID from nested player object."""
        return self.player.id

    @property
    def is_top_ranked(self) -> bool:
        """Check if this is the team's top-ranked available player."""
        return self.rank == 1

    def __str__(self):
        return f"{self.team.abbrev} Draft Board #{self.rank}: {self.player.name}"