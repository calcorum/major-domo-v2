"""
Pitching Decision Model

Tracks wins, losses, saves, holds, and other pitching decisions for game results.
This model matches the database schema at /database/app/routers_v3/decisions.py.
"""
from pydantic import Field
from models.base import SBABaseModel


class Decision(SBABaseModel):
    """
    Pitching decision model for game results.

    Tracks wins, losses, saves, holds, and other pitching decisions.
    """

    game_id: int = Field(..., description="Game ID")
    season: int = Field(..., description="Season number")
    week: int = Field(..., description="Week number")
    game_num: int = Field(..., description="Game number in series")
    pitcher_id: int = Field(..., description="Pitcher's player ID")
    team_id: int = Field(..., description="Team ID")

    # Decision flags
    win: int = Field(0, description="Win (1 or 0)")
    loss: int = Field(0, description="Loss (1 or 0)")
    hold: int = Field(0, description="Hold (1 or 0)")
    is_save: int = Field(0, description="Save (1 or 0)")
    b_save: int = Field(0, description="Blown save (1 or 0)")

    # Pitcher information
    is_start: bool = Field(False, description="Was this a start?")
    irunners: int = Field(0, description="Inherited runners")
    irunners_scored: int = Field(0, description="Inherited runners scored")
    rest_ip: float = Field(0.0, description="Rest innings pitched")
    rest_required: int = Field(0, description="Rest required")

    def __repr__(self):
        """String representation showing key decision info."""
        decision_type = ""
        if self.win == 1:
            decision_type = "W"
        elif self.loss == 1:
            decision_type = "L"
        elif self.is_save == 1:
            decision_type = "SV"
        elif self.hold == 1:
            decision_type = "HLD"
        elif self.b_save == 1:
            decision_type = "BS"

        return (
            f"Decision(pitcher_id={self.pitcher_id}, "
            f"game_id={self.game_id}, "
            f"type={decision_type or 'NONE'})"
        )
