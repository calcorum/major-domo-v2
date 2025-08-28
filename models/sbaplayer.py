from typing import Optional
from pydantic import Field

from models.base import SBABaseModel


class SBAPlayer(SBABaseModel):
    """SBA Player model representing external player identifiers."""
    
    # Override base model to make id required for database entities
    id: int = Field(..., description="SBAPlayer ID from database")
    
    first_name: str = Field(..., description="Player first name")
    last_name: str = Field(..., description="Player last name")
    key_fangraphs: Optional[int] = Field(None, description="FanGraphs player ID")
    key_bbref: Optional[str] = Field(None, description="Baseball Reference player ID")
    key_retro: Optional[str] = Field(None, description="Retrosheet player ID")
    key_mlbam: Optional[int] = Field(None, description="MLB Advanced Media player ID")
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"