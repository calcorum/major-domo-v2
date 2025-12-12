"""
Draft preference list model

Represents team draft board rankings and preferences.
"""
from typing import Optional, Dict, Any
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

    @classmethod
    def from_api_data(cls, data: Dict[str, Any]) -> 'DraftList':
        """
        Create DraftList instance from API data, ensuring nested objects are properly handled.

        The API returns nested team and player objects. We need to ensure Player.from_api_data()
        is called so that player.team_id is properly extracted from the nested team object.
        Without this, Pydantic's default construction doesn't call from_api_data() on nested
        objects, leaving player.team_id as None.
        """
        if not data:
            raise ValueError("Cannot create DraftList from empty data")

        # Make a copy to avoid modifying original
        draft_list_data = data.copy()

        # Handle nested team object
        if 'team' in draft_list_data and isinstance(draft_list_data['team'], dict):
            draft_list_data['team'] = Team.from_api_data(draft_list_data['team'])

        # Handle nested player object - CRITICAL for team_id extraction
        if 'player' in draft_list_data and isinstance(draft_list_data['player'], dict):
            draft_list_data['player'] = Player.from_api_data(draft_list_data['player'])

        return cls(**draft_list_data)

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