"""
Roster models for SBA team roster management

Represents team rosters and roster-related data.
"""
from typing import Optional, List, Dict, Any
from pydantic import Field

from models.base import SBABaseModel
from models.player import Player


class RosterPlayer(SBABaseModel):
    """Represents a player on a team roster."""
    
    player_id: int = Field(..., description="Player ID from database")
    player_name: str = Field(..., description="Player name")
    position: str = Field(..., description="Primary position")
    wara: float = Field(..., description="Player WARA value")
    status: str = Field(default="active", description="Player status (active, il, minor)")
    
    # Optional player details
    injury_status: Optional[str] = Field(None, description="Injury status if applicable")
    contract_info: Optional[Dict[str, Any]] = Field(None, description="Contract information")
    
    @property
    def is_active(self) -> bool:
        """Check if player is on active roster."""
        return self.status == "active"
    
    @property
    def is_injured(self) -> bool:
        """Check if player is on injured list."""
        return self.status == "il"
    
    @property
    def is_minor_league(self) -> bool:
        """Check if player is in minor leagues."""
        return self.status == "minor"
    
    @property
    def status_emoji(self) -> str:
        """Emoji representation of player status."""
        status_emojis = {
            "active": "⚾",
            "il": "🏥",
            "minor": "🏗️",
            "suspended": "⛔"
        }
        return status_emojis.get(self.status, "❓")


class TeamRoster(SBABaseModel):
    """Represents a complete team roster for a specific week."""
    
    team_id: int = Field(..., description="Team ID from database")
    team_abbrev: str = Field(..., description="Team abbreviation")
    season: int = Field(..., description="Season number")
    week: int = Field(..., description="Week number")
    
    # Roster sections
    active_players: List[RosterPlayer] = Field(default_factory=list, description="Active roster players")
    il_players: List[RosterPlayer] = Field(default_factory=list, description="Injured list players")
    minor_league_players: List[RosterPlayer] = Field(default_factory=list, description="Minor league players")
    
    # Roster statistics
    total_wara: float = Field(default=0.0, description="Total active roster WARA")
    salary_total: Optional[float] = Field(None, description="Total salary if applicable")
    
    @property
    def all_players(self) -> List[RosterPlayer]:
        """All players on the roster regardless of status."""
        return self.active_players + self.il_players + self.minor_league_players
    
    @property
    def total_players(self) -> int:
        """Total number of players on roster."""
        return len(self.all_players)
    
    @property
    def active_count(self) -> int:
        """Number of active players."""
        return len(self.active_players)
    
    @property
    def il_count(self) -> int:
        """Number of players on IL."""
        return len(self.il_players)
    
    @property
    def minor_league_count(self) -> int:
        """Number of minor league players."""
        return len(self.minor_league_players)
    
    def get_players_by_position(self, position: str) -> List[RosterPlayer]:
        """Get all active players at a specific position."""
        return [p for p in self.active_players if p.position == position]
    
    def find_player(self, player_name: str) -> Optional[RosterPlayer]:
        """Find a player by name on the roster."""
        for player in self.all_players:
            if player.player_name.lower() == player_name.lower():
                return player
        return None
    
    @classmethod
    def from_api_data(cls, data: dict) -> 'TeamRoster':
        """
        Create TeamRoster instance from API data.
        
        Expected format from API:
        {
            'team_id': 123,
            'team_abbrev': 'NYY', 
            'season': 12,
            'week': 5,
            'active': {'players': [...], 'WARa': 45.2},
            'il': {'players': [...], 'WARa': 2.1},
            'minor': {'players': [...], 'WARa': 12.5}
        }
        """
        roster_data = data.copy()
        
        # Convert player sections
        for section, status in [('active', 'active'), ('il', 'il'), ('minor', 'minor')]:
            if section in data and isinstance(data[section], dict):
                players_data = data[section].get('players', [])
                players = []
                for player_data in players_data:
                    player = RosterPlayer(
                        player_id=player_data.get('id', 0),
                        player_name=player_data.get('name', ''),
                        position=player_data.get('pos_1', 'UNKNOWN'),
                        wara=player_data.get('wara', 0.0),
                        status=status
                    )
                    players.append(player)
                roster_data[f'{section}_players'] = players
                
                # Remove original section
                if section in roster_data:
                    del roster_data[section]
        
        # Handle WARA totals
        if 'active' in data and isinstance(data['active'], dict):
            roster_data['total_wara'] = data['active'].get('WARa', 0.0)
        
        return super().from_api_data(roster_data)