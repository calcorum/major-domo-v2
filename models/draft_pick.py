"""
Draft pick model

Represents individual draft picks with team and player relationships.

API FIELD MAPPING:
The API returns fields without _id suffix (origowner, owner, player).
When the API short_output=false, these fields contain full Team/Player objects.
When short_output=true (or default), they contain integer IDs.
We use Pydantic aliases to handle both cases.
"""
from typing import Optional, Any, Dict, Union
from pydantic import Field, field_validator, model_validator

from models.base import SBABaseModel
from models.team import Team
from models.player import Player


class DraftPick(SBABaseModel):
    """Draft pick model representing a single draft selection."""

    season: int = Field(..., description="Draft season")
    overall: int = Field(..., description="Overall pick number")
    round: int = Field(..., description="Draft round")

    # Team relationships - IDs extracted from API response
    # API returns "origowner" which can be int or Team object
    origowner_id: int = Field(..., description="Original owning team ID")
    origowner: Optional[Team] = Field(None, description="Original owning team (populated when needed)")

    # API returns "owner" which can be int or Team object
    owner_id: Optional[int] = Field(None, description="Current owning team ID")
    owner: Optional[Team] = Field(None, description="Current owning team (populated when needed)")

    # Player selection - API returns "player" which can be int or Player object
    player_id: Optional[int] = Field(None, description="Selected player ID")
    player: Optional[Player] = Field(None, description="Selected player (populated when needed)")

    @classmethod
    def from_api_data(cls, data: Dict[str, Any]) -> 'DraftPick':
        """
        Create DraftPick from API response data.

        Handles API field mapping:
        - API returns 'origowner', 'owner', 'player' (without _id suffix)
        - These can be integer IDs or full objects depending on short_output setting
        """
        if not data:
            raise ValueError("Cannot create DraftPick from empty data")

        # Make a copy to avoid modifying the original
        parsed = dict(data)

        # Handle origowner: can be int ID or Team object
        if 'origowner' in parsed:
            origowner = parsed.pop('origowner')
            if isinstance(origowner, dict):
                # Full Team object from API
                parsed['origowner'] = Team.from_api_data(origowner)
                parsed['origowner_id'] = origowner.get('id', origowner)
            elif isinstance(origowner, int):
                # Just the ID
                parsed['origowner_id'] = origowner
            elif origowner is not None:
                parsed['origowner_id'] = int(origowner)

        # Handle owner: can be int ID or Team object
        if 'owner' in parsed:
            owner = parsed.pop('owner')
            if isinstance(owner, dict):
                # Full Team object from API
                parsed['owner'] = Team.from_api_data(owner)
                parsed['owner_id'] = owner.get('id', owner)
            elif isinstance(owner, int):
                # Just the ID
                parsed['owner_id'] = owner
            elif owner is not None:
                parsed['owner_id'] = int(owner)

        # Handle player: can be int ID or Player object (or None)
        if 'player' in parsed:
            player = parsed.pop('player')
            if isinstance(player, dict):
                # Full Player object from API
                parsed['player'] = Player.from_api_data(player)
                parsed['player_id'] = player.get('id', player)
            elif isinstance(player, int):
                # Just the ID
                parsed['player_id'] = player
            elif player is not None:
                parsed['player_id'] = int(player)

        return cls(**parsed)
    
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