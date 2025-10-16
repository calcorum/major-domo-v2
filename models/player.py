"""
Player model for SBA players

Represents a player with team relationships and position information.
"""
from typing import Optional, List
from pydantic import Field

from models.base import SBABaseModel
from models.team import Team
from models.sbaplayer import SBAPlayer


class Player(SBABaseModel):
    """Player model representing an SBA player."""
    
    # Override base model to make id required for database entities
    id: int = Field(..., description="Player ID from database")
    
    name: str = Field(..., description="Player full name")
    wara: float = Field(..., description="Wins Above Replacement Average")
    season: int = Field(..., description="Season number")
    
    # Team relationship (team_id extracted from nested team object)
    team_id: Optional[int] = Field(None, description="Team ID this player belongs to")
    team: Optional[Team] = Field(None, description="Team object (populated from API)")
    
    # Images and media
    image: Optional[str] = Field(None, description="Primary player image URL")
    image2: Optional[str] = Field(None, description="Secondary player image URL")
    vanity_card: Optional[str] = Field(None, description="Custom vanity card URL")
    headshot: Optional[str] = Field(None, description="Player headshot URL")
    
    # Positions (up to 8 positions)
    pos_1: str = Field(..., description="Primary position")
    pos_2: Optional[str] = None
    pos_3: Optional[str] = None
    pos_4: Optional[str] = None
    pos_5: Optional[str] = None
    pos_6: Optional[str] = None
    pos_7: Optional[str] = None
    pos_8: Optional[str] = None
    
    # Injury and status information
    pitcher_injury: Optional[int] = Field(None, description="Pitcher injury rating")
    injury_rating: Optional[str] = Field(None, description="General injury rating")
    il_return: Optional[str] = Field(None, description="Injured list return date")
    demotion_week: Optional[int] = Field(None, description="Week of demotion")
    
    # Game tracking
    last_game: Optional[str] = Field(None, description="Last game played")
    last_game2: Optional[str] = Field(None, description="Second to last game played")
    
    # External identifiers
    strat_code: Optional[str] = Field(None, description="Strat-o-matic code")
    bbref_id: Optional[str] = Field(None, description="Baseball Reference ID")
    sbaplayer: Optional[SBAPlayer] = Field(None, description="SBA player data object")
    
    @property
    def positions(self) -> List[str]:
        """Return list of all positions this player can play."""
        positions = []
        for i in range(1, 9):
            pos = getattr(self, f'pos_{i}', None)
            if pos:
                positions.append(pos)
        return positions
    
    @property
    def primary_position(self) -> str:
        """Return the player's primary position."""
        return self.pos_1
    
    @classmethod
    def from_api_data(cls, data: dict) -> 'Player':
        """
        Create Player instance from API data, handling nested team structure.
        
        The API returns team data as a nested object, but our model expects
        both team_id (int) and team (optional Team object).
        """
        # Make a copy to avoid modifying original data
        player_data = data.copy()
        
        # Handle team structure - can be nested object or just ID
        if 'team' in player_data:
            if isinstance(player_data['team'], dict):
                # Nested team object from regular endpoints
                team_data = player_data['team']
                player_data['team_id'] = team_data.get('id')
                if team_data.get('id'):
                    from models.team import Team
                    player_data['team'] = Team.from_api_data(team_data)
            elif isinstance(player_data['team'], int):
                # Team ID only from search endpoints
                player_data['team_id'] = player_data['team']
                player_data['team'] = None  # No nested team object available

        # Handle sbaplayer structure - can be nested object or just ID
        if 'sbaplayer' in player_data:
            if isinstance(player_data['sbaplayer'], dict):
                # Nested sbaplayer object
                sba_data = player_data['sbaplayer']
                player_data['sbaplayer'] = SBAPlayer.from_api_data(sba_data)
            elif isinstance(player_data['sbaplayer'], int):
                # SBA player ID only from search endpoints
                player_data['sbaplayer'] = None  # No nested object available
        
        return super().from_api_data(player_data)
    
    @property
    def is_pitcher(self) -> bool:
        """Check if player is a pitcher."""
        return self.pos_1 in ['SP', 'RP', 'P']

    @property
    def display_name(self) -> str:
        """Return the player's display name (same as name)."""
        return self.name

    def __str__(self):
        return f"{self.name} ({self.primary_position})"