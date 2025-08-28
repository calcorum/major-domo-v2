"""
Division model for SBA divisions

Represents a league division with teams and metadata.
"""
from pydantic import Field

from models.base import SBABaseModel


class Division(SBABaseModel):
    """Division model representing a league division."""
    
    # Override base model to make id required for database entities
    id: int = Field(..., description="Division ID from database")
    
    division_name: str = Field(..., description="Full division name")
    division_abbrev: str = Field(..., description="Division abbreviation")
    league_name: str = Field(..., description="League name")
    league_abbrev: str = Field(..., description="League abbreviation")
    season: int = Field(..., description="Season number")
    
    def __str__(self):
        return f"{self.division_name} ({self.division_abbrev})"