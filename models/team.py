"""
Team model for SBA teams

Represents a team in the league with all associated metadata.
"""
from typing import Optional
from pydantic import Field

from models.base import SBABaseModel


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
    stadium: Optional[str] = Field(None, description="Home stadium name")
    thumbnail: Optional[str] = Field(None, description="Team thumbnail URL")
    color: Optional[str] = Field(None, description="Primary team color")
    dice_color: Optional[str] = Field(None, description="Dice rolling color")
    
    def __str__(self):
        return f"{self.abbrev} - {self.lname}"