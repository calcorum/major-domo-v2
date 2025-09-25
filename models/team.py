"""
Team model for SBA teams

Represents a team in the league with all associated metadata.
"""
from typing import Optional
from enum import Enum
from pydantic import Field

from models.base import SBABaseModel
from models.division import Division


class RosterType(Enum):
    """Roster designation types."""
    MAJOR_LEAGUE = "ml"
    MINOR_LEAGUE = "mil"
    INJURED_LIST = "il"
    FREE_AGENCY = "fa"


class Team(SBABaseModel):
    """Team model representing an SBA team."""
    
    # Override base model to make id required for database entities
    id: int = Field(..., description="Team ID from database")
    
    abbrev: str = Field(..., description="Team abbreviation (e.g., 'NYY')")
    sname: str = Field(..., description="Short team name")
    lname: str = Field(..., description="Long team name")
    season: int = Field(..., description="Season number")
    
    # Manager information
    gmid: Optional[int] = Field(None, description="Primary general manager ID")
    gmid2: Optional[int] = Field(None, description="Secondary general manager ID")
    manager1_id: Optional[int] = Field(None, description="Primary manager ID")
    manager2_id: Optional[int] = Field(None, description="Secondary manager ID")
    
    # Team metadata
    division_id: Optional[int] = Field(None, description="Division ID")
    division: Optional[Division] = Field(None, description="Division object (populated from API)")
    stadium: Optional[str] = Field(None, description="Home stadium name")
    thumbnail: Optional[str] = Field(None, description="Team thumbnail URL")
    color: Optional[str] = Field(None, description="Primary team color")
    dice_color: Optional[str] = Field(None, description="Dice rolling color")
    
    @classmethod
    def from_api_data(cls, data: dict) -> 'Team':
        """
        Create Team instance from API data, handling nested division structure.
        
        The API returns division data as a nested object, but our model expects
        both division_id (int) and division (optional Division object).
        """
        # Make a copy to avoid modifying original data
        team_data = data.copy()
        
        # Handle nested division structure
        if 'division' in team_data and isinstance(team_data['division'], dict):
            division_data = team_data['division']
            # Extract division_id from nested division object
            team_data['division_id'] = division_data.get('id')
            # Keep division object for optional population
            if division_data.get('id'):
                team_data['division'] = Division.from_api_data(division_data)
        
        return super().from_api_data(team_data)
    
    def roster_type(self) -> RosterType:
        """Determine the roster type based on team abbreviation."""
        if len(self.abbrev) <= 3:
            return RosterType.MAJOR_LEAGUE

        # For teams with extended abbreviations, check suffix patterns
        abbrev_lower = self.abbrev.lower()

        # Pattern analysis:
        # - Minor League: ends with 'mil' (e.g., NYYMIL, BHMMIL)
        # - Injured List: ends with 'il' but not 'mil' (e.g., NYYIL, BOSIL)
        # - Edge case: teams whose base abbrev ends in 'M' + 'IL' = 'MIL'
        #   Only applies if removing 'IL' gives us exactly a 3-char base team

        if abbrev_lower.endswith('mil'):
            # Check if this is actually [BaseTeam]IL where BaseTeam ends in 'M'
            # E.g., BHMIL = BHM + IL (injured list), not minor league
            if len(self.abbrev) == 5:  # Exactly 5 chars: 3-char base + IL
                potential_base = self.abbrev[:-2]  # Remove 'IL'
                if len(potential_base) == 3 and potential_base.upper().endswith('M'):
                    return RosterType.INJURED_LIST
            return RosterType.MINOR_LEAGUE
        elif abbrev_lower.endswith('il'):
            return RosterType.INJURED_LIST
        else:
            return RosterType.MAJOR_LEAGUE

    def get_major_league_affiliate(self) -> Optional[str]:
        """
        Get the Major League affiliate abbreviation for Minor League teams.

        Returns:
            Major League team abbreviation if this is a Minor League team, None otherwise
        """
        if self.roster_type() == RosterType.MINOR_LEAGUE:
            # Minor League teams follow pattern: [MajorTeam]MIL (e.g., NYYMIL -> NYY)
            if self.abbrev.upper().endswith('MIL'):
                return self.abbrev[:-3]  # Remove 'MIL' suffix
        return None
    
    def __str__(self):
        return f"{self.abbrev} - {self.lname}"