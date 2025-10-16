"""
Play-by-Play Data Model

Represents a single play in a baseball game with complete statistics and game state information.
This model matches the database schema at /database/app/routers_v3/stratplay.py.

NOTE: ID fields have corresponding optional model object fields for API-populated nested data.
Future enhancement could add validators to ensure consistency between ID and model fields.
"""
from typing import Optional, Literal
from pydantic import Field, field_validator
from models.base import SBABaseModel
from models.game import Game
from models.player import Player
from models.team import Team


class Play(SBABaseModel):
    """
    Play-by-play data model for SBA games.

    Represents a single play in a baseball game with complete
    statistics and game state information.
    """

    # Core fields (game_id/pitcher_id optional when nested objects provided)
    game_id: Optional[int] = Field(None, description="Game ID this play belongs to")
    game: Optional[Game] = Field(None, description="Game object (API-populated)")
    play_num: int = Field(..., description="Sequential play number in game")
    pitcher_id: Optional[int] = Field(None, description="Pitcher ID")
    pitcher: Optional[Player] = Field(None, description="Pitcher object (API-populated)")
    on_base_code: str = Field(..., description="Base runners code (e.g., '100', '011')")
    inning_half: Literal['top', 'bot'] = Field(..., description="Inning half")
    inning_num: int = Field(..., description="Inning number")
    batting_order: int = Field(..., description="Batting order position")
    starting_outs: int = Field(..., description="Outs at start of play")
    away_score: int = Field(..., description="Away team score before play")
    home_score: int = Field(..., description="Home team score before play")

    # Optional player IDs
    batter_id: Optional[int] = Field(None, description="Batter ID")
    batter: Optional[Player] = Field(None, description="Batter object (API-populated)")
    batter_team_id: Optional[int] = Field(None, description="Batter's team ID")
    batter_team: Optional[Team] = Field(None, description="Batter's team object (API-populated)")
    pitcher_team_id: Optional[int] = Field(None, description="Pitcher's team ID")
    pitcher_team: Optional[Team] = Field(None, description="Pitcher's team object (API-populated)")
    batter_pos: Optional[str] = Field(None, description="Batter's position")

    # Base runner information
    on_first_id: Optional[int] = Field(None, description="Runner on first ID")
    on_first: Optional[Player] = Field(None, description="Runner on first object (API-populated)")
    on_first_final: Optional[int] = Field(None, description="Runner on first final base")
    on_second_id: Optional[int] = Field(None, description="Runner on second ID")
    on_second: Optional[Player] = Field(None, description="Runner on second object (API-populated)")
    on_second_final: Optional[int] = Field(None, description="Runner on second final base")
    on_third_id: Optional[int] = Field(None, description="Runner on third ID")
    on_third: Optional[Player] = Field(None, description="Runner on third object (API-populated)")
    on_third_final: Optional[int] = Field(None, description="Runner on third final base")
    batter_final: Optional[int] = Field(None, description="Batter's final base")

    # Statistical fields (all default to 0)
    pa: int = Field(0, description="Plate appearance")
    ab: int = Field(0, description="At bat")
    run: int = Field(0, description="Runs scored")
    e_run: int = Field(0, description="Earned runs")
    hit: int = Field(0, description="Hits")
    rbi: int = Field(0, description="RBIs")
    double: int = Field(0, description="Doubles")
    triple: int = Field(0, description="Triples")
    homerun: int = Field(0, description="Home runs")
    bb: int = Field(0, description="Walks")
    so: int = Field(0, description="Strikeouts")
    hbp: int = Field(0, description="Hit by pitch")
    sac: int = Field(0, description="Sacrifice flies")
    ibb: int = Field(0, description="Intentional walks")
    gidp: int = Field(0, description="Grounded into double play")
    bphr: int = Field(0, description="Ballpark home runs")
    bpfo: int = Field(0, description="Ballpark flyouts")
    bp1b: int = Field(0, description="Ballpark singles")
    bplo: int = Field(0, description="Ballpark lineouts")
    sb: int = Field(0, description="Stolen bases")
    cs: int = Field(0, description="Caught stealing")
    outs: int = Field(0, description="Outs recorded")

    # Pitching rest/workload fields
    pitcher_rest_outs: Optional[int] = Field(None, description="Pitcher rest in outs")
    inherited_runners: int = Field(0, description="Inherited runners")
    inherited_scored: int = Field(0, description="Inherited runners scored")
    on_hook_for_loss: int = Field(0, description="On hook for loss")

    # Advanced metrics
    wpa: float = Field(0.0, description="Win probability added")
    re24_primary: Optional[float] = Field(None, description="RE24 primary")
    re24_running: Optional[float] = Field(None, description="RE24 running")
    run_differential: Optional[int] = Field(None, description="Run differential")

    # Defensive players
    catcher_id: Optional[int] = Field(None, description="Catcher ID")
    catcher: Optional[Player] = Field(None, description="Catcher object (API-populated)")
    catcher_team_id: Optional[int] = Field(None, description="Catcher's team ID")
    catcher_team: Optional[Team] = Field(None, description="Catcher's team object (API-populated)")
    defender_id: Optional[int] = Field(None, description="Defender ID")
    defender: Optional[Player] = Field(None, description="Defender object (API-populated)")
    defender_team_id: Optional[int] = Field(None, description="Defender's team ID")
    defender_team: Optional[Team] = Field(None, description="Defender's team object (API-populated)")
    runner_id: Optional[int] = Field(None, description="Runner ID")
    runner: Optional[Player] = Field(None, description="Runner object (API-populated)")
    runner_team_id: Optional[int] = Field(None, description="Runner's team ID")
    runner_team: Optional[Team] = Field(None, description="Runner's team object (API-populated)")

    # Defensive plays
    check_pos: Optional[str] = Field(None, description="Position checked")
    error: int = Field(0, description="Errors")
    wild_pitch: int = Field(0, description="Wild pitches")
    passed_ball: int = Field(0, description="Passed balls")
    pick_off: int = Field(0, description="Pick offs")
    balk: int = Field(0, description="Balks")

    # Game situation
    is_go_ahead: bool = Field(False, description="Go-ahead play")
    is_tied: bool = Field(False, description="Tied game")
    is_new_inning: bool = Field(False, description="New inning")

    # Player handedness
    hand_batting: Optional[str] = Field(None, description="Batter handedness (L/R/S)")
    hand_pitching: Optional[str] = Field(None, description="Pitcher handedness (L/R)")

    # Validators from database model
    @field_validator('on_first_final')
    @classmethod
    def no_final_if_no_runner_one(cls, v, info):
        """Validate on_first_final is None if no runner on first."""
        if info.data.get('on_first_id') is None:
            return None
        return v

    @field_validator('on_second_final')
    @classmethod
    def no_final_if_no_runner_two(cls, v, info):
        """Validate on_second_final is None if no runner on second."""
        if info.data.get('on_second_id') is None:
            return None
        return v

    @field_validator('on_third_final')
    @classmethod
    def no_final_if_no_runner_three(cls, v, info):
        """Validate on_third_final is None if no runner on third."""
        if info.data.get('on_third_id') is None:
            return None
        return v

    @field_validator('batter_final')
    @classmethod
    def no_final_if_no_batter(cls, v, info):
        """Validate batter_final is None if no batter."""
        if info.data.get('batter_id') is None:
            return None
        return v

    def descriptive_text(self, away_team: Team, home_team: Team) -> str:
        """
        Generate human-readable description of this play for key plays display.

        Args:
            away_team: Away team object (for team abbreviations)
            home_team: Home team object (for team abbreviations)

        Returns:
            Formatted string like: "Top 3: Player Name (NYY) homers in 2 runs"
        """
        # Determine inning text
        inning_text = f"{'Top' if self.inning_half == 'top' else 'Bot'} {self.inning_num}"

        # Determine team abbreviation based on inning half
        away_score = self.away_score
        home_score = self.home_score
        if self.inning_half == 'top':
            away_score += self.rbi
        else:
            home_score += self.rbi
        
        score_text = f'tied at {home_score}'
        if home_score > away_score:
            score_text = f'{home_team.abbrev} up {home_score}-{away_score}'
        else:
            score_text = f'{away_team.abbrev} up {away_score}-{home_score}'

        # Build play description based on play type
        description_parts = []
        which_player = 'batter'

        # Offensive plays
        if self.homerun > 0:
            if self.rbi == 1:
                description_parts.append("homers")
            else:
                description_parts.append(f"homers in {self.rbi} runs")
        elif self.triple > 0:
            description_parts.append("triples")
            if self.rbi > 0:
                description_parts.append(f"scoring {self.rbi} run{'s' if self.rbi > 1 else ''}")
        elif self.double > 0:
            description_parts.append("doubles")
            if self.rbi > 0:
                description_parts.append(f"scoring {self.rbi} run{'s' if self.rbi > 1 else ''}")
        elif self.hit > 0:
            description_parts.append("singles")
            if self.rbi > 0:
                description_parts.append(f"scoring {self.rbi} run{'s' if self.rbi > 1 else ''}")
        elif self.bb > 0:
            if self.ibb > 0:
                description_parts.append("intentionally walked")
            else:
                description_parts.append("walks")
            if self.rbi > 0:
                description_parts.append(f"scoring {self.rbi} run{'s' if self.rbi > 1 else ''}")
        elif self.hbp > 0:
            description_parts.append("hit by pitch")
            if self.rbi > 0:
                description_parts.append(f"scoring {self.rbi} run{'s' if self.rbi > 1 else ''}")
        elif self.sac > 0:
            description_parts.append("sacrifice fly")
            if self.rbi > 0:
                description_parts.append(f"scoring {self.rbi} run{'s' if self.rbi > 1 else ''}")
        elif self.sb > 0:
            description_parts.append("steals a base")
        elif self.cs > 0:
            which_player = 'catcher'
            description_parts.append("guns down a baserunner")
        elif self.gidp > 0:
            description_parts.append("grounds into double play")
        elif self.so > 0:
            which_player = 'pitcher'
            description_parts.append(f"gets a strikeout")
        # Defensive plays
        elif self.error > 0:
            which_player = 'defender'
            description_parts.append("commits an error")
            if self.rbi > 0:
                description_parts.append(f"allowing {self.rbi} run{'s' if self.rbi > 1 else ''}")
        elif self.wild_pitch > 0:
            which_player = 'pitcher'
            description_parts.append("uncorks a wild pitch")
        elif self.passed_ball > 0:
            which_player = 'catcher'
            description_parts.append("passed ball")
        elif self.pick_off > 0:
            which_player = 'runner'
            description_parts.append("picked off")
        elif self.balk > 0:
            which_player = 'pitcher'
            description_parts.append("balk")
        else:
            # Generic out
            if self.outs > 0:
                which_player = 'pitcher'
                description_parts.append(f'records out number {self.starting_outs + self.outs}')

        # Combine parts
        if description_parts:
            play_desc = " ".join(description_parts)
        else:
            play_desc = "makes a play"

        player_dict = {
            'batter': self.batter,
            'pitcher': self.pitcher,
            'catcher': self.catcher,
            'runner': self.runner,
            'defender': self.defender
        }
        team_dict = {
            'batter': self.batter_team,
            'pitcher': self.pitcher_team,
            'catcher': self.catcher_team,
            'runner': self.runner_team,
            'defender': self.defender_team
        }

        # Format: "Top 3: Derek Jeter (NYY) homers in 2 runs, NYY up 2-0"
        return f"{inning_text}: {player_dict.get(which_player).name} ({team_dict.get(which_player).abbrev}) {play_desc}, {score_text}"
