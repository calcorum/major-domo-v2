"""
Custom Command models for Discord Bot v2.0

Modern Pydantic models for the custom command system with full type safety.
"""
from datetime import datetime
from typing import Optional, Dict, Any
import re

from pydantic import BaseModel, Field, field_validator
from models.base import SBABaseModel


class CustomCommandCreator(SBABaseModel):
    """Creator of custom commands."""
    id: int = Field(..., description="Database ID") # type: ignore
    discord_id: int = Field(..., description="Discord user ID")
    username: str = Field(..., description="Discord username")
    display_name: Optional[str] = Field(None, description="Discord display name")
    created_at: datetime = Field(..., description="When creator was first recorded") # type: ignore
    total_commands: int = Field(0, description="Total commands created by this user")
    active_commands: int = Field(0, description="Currently active commands")


class CustomCommand(SBABaseModel):
    """A custom command created by a user."""
    id: int = Field(..., description="Database ID") # type: ignore
    name: str = Field(..., description="Command name (unique)")
    content: str = Field(..., description="Command response content")
    creator_id: Optional[int] = Field(None, description="ID of the creator (may be missing from execute endpoint)")
    creator: Optional[CustomCommandCreator] = Field(None, description="Creator details")
    
    # Timestamps
    created_at: datetime = Field(..., description="When command was created") # type: ignore
    updated_at: Optional[datetime] = Field(None, description="When command was last updated") # type: ignore
    last_used: Optional[datetime] = Field(None, description="When command was last executed")
    
    # Usage tracking
    use_count: int = Field(0, description="Total times command has been used")
    warning_sent: bool = Field(False, description="Whether cleanup warning was sent")
    
    # Metadata
    is_active: bool = Field(True, description="Whether command is currently active")
    tags: Optional[list[str]] = Field(None, description="Optional tags for categorization")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate command name."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Command name cannot be empty")
        
        name = v.strip().lower()
        
        # Length validation
        if len(name) < 2:
            raise ValueError("Command name must be at least 2 characters")
        if len(name) > 32:
            raise ValueError("Command name cannot exceed 32 characters")
        
        # Character validation - only allow alphanumeric, dashes, underscores
        if not re.match(r'^[a-z0-9_-]+$', name):
            raise ValueError("Command name can only contain letters, numbers, dashes, and underscores")
        
        # Reserved names
        reserved = {
            'help', 'ping', 'info', 'list', 'create', 'delete', 'edit', 
            'admin', 'mod', 'owner', 'bot', 'system', 'config'
        }
        if name in reserved:
            raise ValueError(f"'{name}' is a reserved command name")
        
        return name.lower()
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        """Validate command content."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Command content cannot be empty")
        
        content = v.strip()
        
        # Length validation
        if len(content) > 2000:
            raise ValueError("Command content cannot exceed 2000 characters")
        
        # Basic content filtering
        prohibited = ['@everyone', '@here']
        content_lower = content.lower()
        for term in prohibited:
            if term in content_lower:
                raise ValueError(f"Command content cannot contain '{term}'")
        
        return content
    
    @property
    def days_since_last_use(self) -> Optional[int]:
        """Calculate days since last use."""
        if not self.last_used:
            return None
        return (datetime.now() - self.last_used).days
    
    @property
    def is_eligible_for_warning(self) -> bool:
        """Check if command is eligible for deletion warning."""
        if not self.last_used or self.warning_sent:
            return False
        return self.days_since_last_use >= 60 # type: ignore
    
    @property
    def is_eligible_for_deletion(self) -> bool:
        """Check if command is eligible for deletion."""
        if not self.last_used:
            return False
        return self.days_since_last_use >= 90 # type: ignore
    
    @property
    def popularity_score(self) -> float:
        """Calculate popularity score based on usage and recency."""
        if self.use_count == 0:
            return 0.0
        
        # Base score from usage
        base_score = min(self.use_count / 10.0, 10.0)  # Max 10 points from usage
        
        # Recency modifier
        if self.last_used:
            days_ago = self.days_since_last_use
            if days_ago <= 7: # type: ignore
                recency_modifier = 1.5  # Recent use bonus
            elif days_ago <= 30: # type: ignore
                recency_modifier = 1.0  # No modifier
            elif days_ago <= 60: # type: ignore
                recency_modifier = 0.7  # Slight penalty
            else:
                recency_modifier = 0.3  # Old command penalty
        else:
            recency_modifier = 0.1  # Never used
        
        return base_score * recency_modifier


class CustomCommandSearchFilters(BaseModel):
    """Filters for searching custom commands."""
    name_contains: Optional[str] = None
    creator_id: Optional[int] = None
    creator_name: Optional[str] = None
    min_uses: Optional[int] = None
    max_days_unused: Optional[int] = None
    has_tags: Optional[list[str]] = None
    is_active: bool = True
    
    # Sorting options
    sort_by: str = Field('name', description="Sort field: name, created_at, last_used, use_count, popularity")
    sort_desc: bool = Field(False, description="Sort in descending order")
    
    # Pagination
    page: int = Field(1, description="Page number (1-based)")
    page_size: int = Field(25, description="Items per page")
    
    @field_validator('sort_by')
    @classmethod
    def validate_sort_by(cls, v):
        """Validate sort field."""
        valid_sorts = {'name', 'created_at', 'last_used', 'use_count', 'popularity', 'creator'}
        if v not in valid_sorts:
            raise ValueError(f"sort_by must be one of: {', '.join(valid_sorts)}")
        return v
    
    @field_validator('page')
    @classmethod
    def validate_page(cls, v):
        """Validate page number."""
        if v < 1:
            raise ValueError("Page number must be >= 1")
        return v
    
    @field_validator('page_size')
    @classmethod
    def validate_page_size(cls, v):
        """Validate page size."""
        if v < 1 or v > 100:
            raise ValueError("Page size must be between 1 and 100")
        return v


class CustomCommandSearchResult(BaseModel):
    """Result of a custom command search."""
    commands: list[CustomCommand]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_more: bool
    
    @property
    def start_index(self) -> int:
        """Get the starting index for this page."""
        return (self.page - 1) * self.page_size + 1
    
    @property
    def end_index(self) -> int:
        """Get the ending index for this page."""
        return min(self.page * self.page_size, self.total_count)


class CustomCommandStats(BaseModel):
    """Statistics about custom commands."""
    total_commands: int
    active_commands: int
    total_creators: int
    total_uses: int
    
    # Usage statistics
    most_popular_command: Optional[CustomCommand] = None
    most_active_creator: Optional[CustomCommandCreator] = None
    recent_commands_count: int = 0  # Commands created in last 7 days
    
    # Cleanup statistics
    commands_needing_warning: int = 0
    commands_eligible_for_deletion: int = 0
    
    @property
    def average_uses_per_command(self) -> float:
        """Calculate average uses per command."""
        if self.active_commands == 0:
            return 0.0
        return self.total_uses / self.active_commands
    
    @property
    def average_commands_per_creator(self) -> float:
        """Calculate average commands per creator."""
        if self.total_creators == 0:
            return 0.0
        return self.active_commands / self.total_creators