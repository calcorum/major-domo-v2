"""
Batting statistics model for SBA players

Represents seasonal batting statistics with comprehensive metrics.
"""
from typing import Optional
from pydantic import Field

from models.base import SBABaseModel
from models.player import Player
from models.team import Team
from models.sbaplayer import SBAPlayer


class BattingStats(SBABaseModel):
    """Batting statistics model representing seasonal batting performance."""
    
    # Player information
    player: Player = Field(..., description="Player object with full details")
    sbaplayer: Optional[SBAPlayer] = Field(None, description="SBA player reference")
    team: Optional[Team] = Field(None, description="Team object")
    
    # Basic info
    season: int = Field(..., description="Season number")
    name: str = Field(..., description="Player name")
    player_team_id: int = Field(..., description="Player's team ID")
    player_team_abbrev: str = Field(..., description="Player's team abbreviation")
    
    # Plate appearances and at-bats
    pa: int = Field(..., description="Plate appearances")
    ab: int = Field(..., description="At bats")
    
    # Hitting results
    run: int = Field(..., description="Runs scored")
    hit: int = Field(..., description="Hits")
    double: int = Field(..., description="Doubles")
    triple: int = Field(..., description="Triples")
    homerun: int = Field(..., description="Home runs")
    rbi: int = Field(..., description="Runs batted in")
    
    # Walks and strikeouts
    bb: int = Field(..., description="Walks (bases on balls)")
    so: int = Field(..., description="Strikeouts")
    hbp: int = Field(..., description="Hit by pitch")
    ibb: int = Field(..., description="Intentional walks")
    sac: int = Field(..., description="Sacrifice hits")
    
    # Situational hitting
    bphr: int = Field(..., description="Ballpark home runs")
    bpfo: int = Field(..., description="Ballpark flyouts") 
    bp1b: int = Field(..., description="Ballpark singles")
    bplo: int = Field(..., description="Ballpark lineouts")
    gidp: int = Field(..., description="Grounded into double plays")
    
    # Base running
    sb: int = Field(..., description="Stolen bases")
    cs: int = Field(..., description="Caught stealing")
    
    # Advanced metrics
    avg: float = Field(..., description="Batting average")
    obp: float = Field(..., description="On-base percentage")
    slg: float = Field(..., description="Slugging percentage")
    ops: float = Field(..., description="On-base plus slugging")
    woba: float = Field(..., description="Weighted on-base average")
    k_pct: float = Field(..., description="Strikeout percentage")
    
    @property
    def singles(self) -> int:
        """Calculate singles from hits and extra-base hits."""
        return self.hit - self.double - self.triple - self.homerun
    
    @property
    def total_bases(self) -> int:
        """Calculate total bases."""
        return self.singles + (2 * self.double) + (3 * self.triple) + (4 * self.homerun)
    
    @property
    def iso(self) -> float:
        """Calculate isolated power (SLG - AVG)."""
        return self.slg - self.avg
    
    def __str__(self):
        return f"{self.name} batting stats: {self.avg:.3f}/{self.obp:.3f}/{self.slg:.3f}"