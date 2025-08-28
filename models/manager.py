from typing import Optional
from pydantic import Field

from models.base import SBABaseModel


class Manager(SBABaseModel):
    """Manager model representing an SBA manager."""
    
    # Override base model to make id required for database entities
    id: int = Field(..., description="Manager ID from database")
    
    name: str = Field(..., description="Manager name")
    image: Optional[str] = Field(None, description="Manager image URL")
    headline: Optional[str] = Field(None, description="Manager headline")
    bio: Optional[str] = Field(None, description="Manager biography")
    
    def __str__(self):
        return self.name