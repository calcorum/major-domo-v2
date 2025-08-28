"""
Pitching statistics model for SBA players

Represents seasonal pitching statistics with comprehensive metrics.
"""
from typing import Optional
from pydantic import Field

from models.base import SBABaseModel
from models.player import Player
from models.team import Team
from models.sbaplayer import SBAPlayer


class PitchingStats(SBABaseModel):
    """Pitching statistics model representing seasonal pitching performance."""
    
    # Player information
    player: Player = Field(..., description="Player object with full details")
    sbaplayer: Optional[SBAPlayer] = Field(None, description="SBA player reference")
    team: Optional[Team] = Field(None, description="Team object")
    
    # Basic info
    season: int = Field(..., description="Season number")
    name: str = Field(..., description="Player name")
    player_team_id: int = Field(..., description="Player's team ID")
    player_team_abbrev: str = Field(..., description="Player's team abbreviation")
    
    # Pitching volume
    tbf: int = Field(..., description="Total batters faced")
    outs: int = Field(..., description="Outs recorded")
    games: int = Field(..., description="Games pitched")
    gs: int = Field(..., description="Games started")
    
    # Win/Loss record
    win: int = Field(..., description="Wins")
    loss: int = Field(..., description="Losses")
    hold: int = Field(..., description="Holds")
    saves: int = Field(..., description="Saves")
    bsave: int = Field(..., description="Blown saves")
    
    # Inherited runners
    ir: int = Field(..., description="Inherited runners")
    irs: int = Field(..., description="Inherited runners scored")
    
    # Pitching results
    ab: int = Field(..., description="At bats against")
    run: int = Field(..., description="Runs allowed")
    e_run: int = Field(..., description="Earned runs allowed")
    hits: int = Field(..., description="Hits allowed")
    double: int = Field(..., description="Doubles allowed")
    triple: int = Field(..., description="Triples allowed")
    homerun: int = Field(..., description="Home runs allowed")
    
    # Control
    bb: int = Field(..., description="Walks allowed")
    so: int = Field(..., description="Strikeouts")
    hbp: int = Field(..., description="Hit batters")
    ibb: int = Field(..., description="Intentional walks")
    sac: int = Field(..., description="Sacrifice hits allowed")
    
    # Defensive plays
    gidp: int = Field(..., description="Ground into double play")
    sb: int = Field(..., description="Stolen bases allowed")
    cs: int = Field(..., description="Caught stealing")
    
    # Ballpark factors
    bphr: int = Field(..., description="Ballpark home runs")
    bpfo: int = Field(..., description="Ballpark flyouts")
    bp1b: int = Field(..., description="Ballpark singles")
    bplo: int = Field(..., description="Ballpark lineouts")
    
    # Errors and advanced
    wp: int = Field(..., description="Wild pitches")
    balk: int = Field(..., description="Balks")
    wpa: float = Field(..., description="Win probability added")
    re24: float = Field(..., description="Run expectancy 24-base")
    
    # Rate stats
    era: float = Field(..., description="Earned run average")
    whip: float = Field(..., description="Walks + hits per inning pitched")
    avg: float = Field(..., description="Batting average against")
    obp: float = Field(..., description="On-base percentage against")
    slg: float = Field(..., description="Slugging percentage against")
    ops: float = Field(..., description="OPS against")
    woba: float = Field(..., description="wOBA against")
    
    # Per 9 inning stats
    hper9: float = Field(..., description="Hits per 9 innings")
    kper9: float = Field(..., description="Strikeouts per 9 innings")
    bbper9: float = Field(..., description="Walks per 9 innings")
    kperbb: float = Field(..., description="Strikeout to walk ratio")
    
    # Situational stats
    lob_2outs: float = Field(..., description="Left on base with 2 outs")
    rbipercent: float = Field(..., description="RBI percentage")
    
    @property
    def innings_pitched(self) -> float:
        """Calculate innings pitched from outs."""
        return self.outs / 3.0
    
    @property
    def win_percentage(self) -> float:
        """Calculate winning percentage."""
        total_decisions = self.win + self.loss
        if total_decisions == 0:
            return 0.0
        return self.win / total_decisions
    
    @property
    def babip(self) -> float:
        """Calculate BABIP (Batting Average on Balls In Play)."""
        balls_in_play = self.hits - self.homerun + self.ab - self.so - self.homerun
        if balls_in_play == 0:
            return 0.0
        return (self.hits - self.homerun) / balls_in_play
    
    def __str__(self):
        return f"{self.name} pitching stats: {self.win}-{self.loss}, {self.era:.2f} ERA"