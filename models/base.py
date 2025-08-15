"""
Base model for all SBA entities

Provides common functionality for data validation, serialization, and API interaction.
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class SBABaseModel(BaseModel):
    """Base model for all SBA entities with common functionality."""
    
    model_config = {
        "validate_assignment": True,
        "use_enum_values": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        }
    }
    
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __repr__(self):
        fields = ', '.join(f'{k}={v}' for k, v in self.model_dump(exclude_none=True).items())
        return f"{self.__class__.__name__}({fields})"
    
    def to_dict(self, exclude_none: bool = True) -> Dict[str, Any]:
        """Convert model to dictionary, optionally excluding None values."""
        return self.model_dump(exclude_none=exclude_none)
    
    @classmethod
    def from_api_data(cls, data: Dict[str, Any]):
        """Create model instance from API response data."""
        if not data:
            raise ValueError(f"Cannot create {cls.__name__} from empty data")
        return cls(**data)