"""
Team model for SBA teams

Represents a team in the league with all associated metadata.
"""
from typing import Optional
from pydantic import Field

from models.base import SBABaseModel
from models.division import Division


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
    
    def __str__(self):
        return f"{self.abbrev} - {self.lname}"