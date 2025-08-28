"""
Current league state model

Represents the current state of the league including week, season, and settings.
"""
from pydantic import Field, field_validator

from models.base import SBABaseModel


class Current(SBABaseModel):
    """Model representing current league state and settings."""
    
    week: int = Field(69, description="Current week number")
    season: int = Field(69, description="Current season number")
    freeze: bool = Field(True, description="Whether league is frozen")
    bet_week: str = Field('sheets', description="Betting week identifier")
    trade_deadline: int = Field(1, description="Trade deadline week")
    pick_trade_start: int = Field(69, description="Draft pick trading start week")
    pick_trade_end: int = Field(420, description="Draft pick trading end week")
    playoffs_begin: int = Field(420, description="Week when playoffs begin")
    
    @field_validator("bet_week", mode="before")
    @classmethod
    def cast_bet_week_to_string(cls, v):
        """Ensure bet_week is always a string."""
        return str(v) if v is not None else 'sheets'
    
    @property
    def is_offseason(self) -> bool:
        """Check if league is currently in offseason."""
        return self.week > 18
    
    @property
    def is_playoffs(self) -> bool:
        """Check if league is currently in playoffs."""
        return self.week >= self.playoffs_begin
    
    @property
    def can_trade_picks(self) -> bool:
        """Check if draft pick trading is currently allowed."""
        return self.pick_trade_start <= self.week <= self.pick_trade_end
    
    @property
    def ever_trade_picks(self) -> bool:
        """Check if draft pick trading is allowed this season at all"""
        return self.pick_trade_start <= self.playoffs_begin + 4