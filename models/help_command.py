"""
Help Command models for Discord Bot v2.0

Modern Pydantic models for the custom help system with full type safety.
Allows admins and help editors to create custom help topics for league documentation,
resources, FAQs, links, and guides.
"""
from datetime import datetime
from typing import Optional
import re

from pydantic import BaseModel, Field, field_validator
from models.base import SBABaseModel


class HelpCommand(SBABaseModel):
    """A help topic created by an admin or help editor."""
    id: int = Field(..., description="Database ID")  # type: ignore
    name: str = Field(..., description="Help topic name (unique)")
    title: str = Field(..., description="Display title")
    content: str = Field(..., description="Help content (markdown supported)")
    category: Optional[str] = Field(None, description="Category for organization")

    # Audit fields
    created_by_discord_id: str = Field(..., description="Creator Discord ID (stored as text)")
    created_at: datetime = Field(..., description="When help topic was created")  # type: ignore
    updated_at: Optional[datetime] = Field(None, description="When help topic was last updated")  # type: ignore
    last_modified_by: Optional[str] = Field(None, description="Discord ID of last editor (stored as text)")

    # Status and metrics
    is_active: bool = Field(True, description="Whether help topic is active (soft delete)")
    view_count: int = Field(0, description="Number of times viewed")
    display_order: int = Field(0, description="Sort order for display")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate help topic name."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Help topic name cannot be empty")

        name = v.strip().lower()

        # Length validation
        if len(name) < 2:
            raise ValueError("Help topic name must be at least 2 characters")
        if len(name) > 32:
            raise ValueError("Help topic name cannot exceed 32 characters")

        # Character validation - only allow alphanumeric, dashes, underscores
        if not re.match(r'^[a-z0-9_-]+$', name):
            raise ValueError("Help topic name can only contain letters, numbers, dashes, and underscores")

        return name.lower()

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        """Validate help topic title."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Help topic title cannot be empty")

        title = v.strip()

        # Length validation
        if len(title) > 200:
            raise ValueError("Help topic title cannot exceed 200 characters")

        return title

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        """Validate help topic content."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Help topic content cannot be empty")

        content = v.strip()

        # Length validation
        if len(content) > 4000:
            raise ValueError("Help topic content cannot exceed 4000 characters")

        # Basic content filtering (still allow @mentions in help content)
        # We allow @everyone and @here in help content since it's admin-controlled

        return content

    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        """Validate category if provided."""
        if v is None:
            return v

        category = v.strip().lower()

        if len(category) == 0:
            return None  # Empty string becomes None

        # Length validation
        if len(category) > 50:
            raise ValueError("Category cannot exceed 50 characters")

        # Character validation
        if not re.match(r'^[a-z0-9_-]+$', category):
            raise ValueError("Category can only contain letters, numbers, dashes, and underscores")

        return category

    @property
    def is_deleted(self) -> bool:
        """Check if help topic is soft deleted."""
        return not self.is_active

    @property
    def days_since_update(self) -> Optional[int]:
        """Calculate days since last update."""
        if not self.updated_at:
            return None
        return (datetime.now() - self.updated_at).days

    @property
    def days_since_creation(self) -> int:
        """Calculate days since creation."""
        return (datetime.now() - self.created_at).days

    @property
    def popularity_score(self) -> float:
        """
        Calculate popularity score based on view count and recency.
        Higher score = more popular topic.
        """
        if self.view_count == 0:
            return 0.0

        # Base score from views
        base_score = min(self.view_count / 10.0, 10.0)  # Max 10 points from views

        # Recency modifier based on creation date
        days_old = self.days_since_creation
        if days_old <= 7:
            recency_modifier = 1.5  # New topic bonus
        elif days_old <= 30:
            recency_modifier = 1.2  # Recent bonus
        elif days_old <= 90:
            recency_modifier = 1.0  # No modifier
        else:
            recency_modifier = 0.8  # Older topic slight penalty

        return base_score * recency_modifier


class HelpCommandSearchFilters(BaseModel):
    """Filters for searching help commands."""
    name_contains: Optional[str] = None
    category: Optional[str] = None
    is_active: bool = True

    # Sorting
    sort_by: str = Field('name', description="Sort field: name, category, created_at, view_count, display_order")
    sort_desc: bool = Field(False, description="Sort in descending order")

    # Pagination
    page: int = Field(1, description="Page number (1-based)")
    page_size: int = Field(25, description="Items per page")

    @field_validator('sort_by')
    @classmethod
    def validate_sort_by(cls, v):
        """Validate sort field."""
        valid_sorts = {'name', 'title', 'category', 'created_at', 'updated_at', 'view_count', 'display_order'}
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


class HelpCommandSearchResult(BaseModel):
    """Result of a help command search."""
    help_commands: list[HelpCommand]
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


class HelpCommandStats(BaseModel):
    """Statistics about help commands."""
    total_commands: int
    active_commands: int
    total_views: int
    most_viewed_command: Optional[HelpCommand] = None
    recent_commands_count: int = 0  # Commands created in last 7 days

    @property
    def average_views_per_command(self) -> float:
        """Calculate average views per command."""
        if self.active_commands == 0:
            return 0.0
        return self.total_views / self.active_commands
