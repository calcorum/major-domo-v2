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
        """Determine the roster type based on team abbreviation and name."""
        if len(self.abbrev) <= 3:
            return RosterType.MAJOR_LEAGUE

        # Use sname as the definitive source of truth for IL teams
        # If "IL" is in sname and abbrev ends in "IL" → Injured List
        if self.abbrev.upper().endswith('IL') and 'IL' in self.sname:
            return RosterType.INJURED_LIST

        # If abbrev ends with "MiL" (exact case) and "IL" not in sname → Minor League
        if self.abbrev.endswith('MiL') and 'IL' not in self.sname:
            return RosterType.MINOR_LEAGUE

        # Handle other patterns
        abbrev_lower = self.abbrev.lower()
        if abbrev_lower.endswith('mil'):
            return RosterType.MINOR_LEAGUE
        elif abbrev_lower.endswith('il'):
            return RosterType.INJURED_LIST
        else:
            return RosterType.MAJOR_LEAGUE

    def _get_base_abbrev(self) -> str:
        """
        Extract the base team abbreviation from potentially extended abbreviation.

        Returns:
            Base team abbreviation (typically 3 characters)
        """
        abbrev_lower = self.abbrev.lower()

        # If 3 chars or less, it's already the base team
        if len(self.abbrev) <= 3:
            return self.abbrev

        # Handle teams ending in 'mil' - use sname to determine if IL or MiL
        if abbrev_lower.endswith('mil'):
            # If "IL" is in sname and abbrev ends in "IL" → It's [Team]IL
            if self.abbrev.upper().endswith('IL') and 'IL' in self.sname:
                return self.abbrev[:-2]  # Remove 'IL'
            # Otherwise it's minor league → remove 'MIL'
            return self.abbrev[:-3]

        # Handle injured list: ends with 'il' but not 'mil'
        if abbrev_lower.endswith('il'):
            return self.abbrev[:-2]  # Remove 'IL'

        # Unknown pattern, return as-is
        return self.abbrev

    async def major_league_affiliate(self) -> 'Team':
        """
        Get the major league team for this organization via API call.

        Returns:
            Team instance representing the major league affiliate

        Raises:
            APIException: If the affiliate team cannot be found
        """
        from services.team_service import team_service

        base_abbrev = self._get_base_abbrev()
        if base_abbrev == self.abbrev:
            return self  # Already the major league team

        team = await team_service.get_team_by_abbrev(base_abbrev, self.season)
        if team is None:
            raise ValueError(f"Major league affiliate not found for team {self.abbrev} (looking for {base_abbrev})")
        return team

    async def minor_league_affiliate(self) -> 'Team':
        """
        Get the minor league team for this organization via API call.

        Returns:
            Team instance representing the minor league affiliate

        Raises:
            APIException: If the affiliate team cannot be found
        """
        from services.team_service import team_service

        base_abbrev = self._get_base_abbrev()
        mil_abbrev = f"{base_abbrev}MIL"

        if mil_abbrev == self.abbrev:
            return self  # Already the minor league team

        team = await team_service.get_team_by_abbrev(mil_abbrev, self.season)
        if team is None:
            raise ValueError(f"Minor league affiliate not found for team {self.abbrev} (looking for {mil_abbrev})")
        return team

    async def injured_list_affiliate(self) -> 'Team':
        """
        Get the injured list team for this organization via API call.

        Returns:
            Team instance representing the injured list affiliate

        Raises:
            APIException: If the affiliate team cannot be found
        """
        from services.team_service import team_service

        base_abbrev = self._get_base_abbrev()
        il_abbrev = f"{base_abbrev}IL"

        if il_abbrev == self.abbrev:
            return self  # Already the injured list team

        team = await team_service.get_team_by_abbrev(il_abbrev, self.season)
        if team is None:
            raise ValueError(f"Injured list affiliate not found for team {self.abbrev} (looking for {il_abbrev})")
        return team

    def is_same_organization(self, other_team: 'Team') -> bool:
        """
        Check if this team and another team are from the same organization.

        Args:
            other_team: Another team to compare

        Returns:
            True if both teams are from the same organization
        """
        return self._get_base_abbrev() == other_team._get_base_abbrev()

    def __str__(self):
        return f"{self.abbrev} - {self.lname}"