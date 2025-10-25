"""
Draft configuration and state model

Represents the current draft settings and timer state.
"""
from typing import Optional
from datetime import datetime
from pydantic import Field, field_validator

from models.base import SBABaseModel


class DraftData(SBABaseModel):
    """Draft configuration and state model."""

    currentpick: int = Field(0, description="Current pick number in progress")
    timer: bool = Field(False, description="Whether draft timer is active")
    pick_deadline: Optional[datetime] = Field(None, description="Deadline for current pick")
    result_channel: Optional[int] = Field(None, description="Discord channel ID for draft results")
    ping_channel: Optional[int] = Field(None, description="Discord channel ID for draft pings")
    pick_minutes: int = Field(1, description="Minutes allowed per pick")

    @field_validator("result_channel", "ping_channel", mode="before")
    @classmethod
    def cast_channel_ids_to_int(cls, v):
        """Ensure channel IDs are integers (database stores as string)."""
        if v is None:
            return None
        if isinstance(v, str):
            return int(v)
        return v
    
    @property
    def is_draft_active(self) -> bool:
        """Check if the draft is currently active."""
        return self.timer
    
    @property
    def is_pick_expired(self) -> bool:
        """Check if the current pick deadline has passed."""
        if not self.pick_deadline:
            return False
        return datetime.now() > self.pick_deadline
    
    def __str__(self):
        status = "Active" if self.is_draft_active else "Inactive"
        return f"Draft {status}: Pick {self.currentpick} ({self.pick_minutes}min timer)"