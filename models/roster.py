"""
Roster models for SBA team roster management

Represents team rosters and roster-related data.
"""
from typing import Optional, List
from pydantic import Field

from models.base import SBABaseModel
from models.player import Player


class TeamRoster(SBABaseModel):
    """Represents a complete team roster for a specific week."""

    team_id: int = Field(..., description="Team ID from database")
    team_abbrev: str = Field(..., description="Team abbreviation")
    season: int = Field(..., description="Season number")
    week: int = Field(..., description="Week number")

    # Roster sections
    active_players: List[Player] = Field(default_factory=list, description="Active roster players")
    il_players: List[Player] = Field(default_factory=list, description="Injured list players")
    minor_league_players: List[Player] = Field(default_factory=list, description="Minor league players")

    # Roster statistics
    total_wara: float = Field(default=0.0, description="Total active roster WARA")
    salary_total: Optional[float] = Field(None, description="Total salary if applicable")

    @property
    def all_players(self) -> List[Player]:
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

    def get_players_by_position(self, position: str) -> List[Player]:
        """Get all active players at a specific position."""
        return [p for p in self.active_players if p.primary_position == position]

    def find_player(self, player_name: str) -> Optional[Player]:
        """Find a player by name on the roster."""
        for player in self.all_players:
            if player.name.lower() == player_name.lower():
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
            'shortil': {'players': [...], 'WARa': 2.1},
            'longil': {'players': [...], 'WARa': 12.5}
        }
        """
        # Create a new dict with the required fields
        roster_data = {
            'team_id': data.get('team_id'),
            'team_abbrev': data.get('team_abbrev', ''),
            'season': data.get('season', 12),
            'week': data.get('week', 0),
            'active_players': [],
            'il_players': [],
            'minor_league_players': [],
            'total_wara': 0.0
        }

        # Convert player sections - handle API structure
        section_mapping = {
            'active': 'active_players',
            'longil': 'minor_league_players',  # Long IL = Minor League
            'shortil': 'il_players'  # Short IL = Injured List
        }

        for api_section, model_field in section_mapping.items():
            if api_section in data and isinstance(data[api_section], dict):
                players_data = data[api_section].get('players', [])
                players = []
                for player_data in players_data:
                    # Enhance player data with required fields if missing
                    enhanced_player_data = player_data.copy()
                    enhanced_player_data.setdefault('season', data.get('season', 12))
                    enhanced_player_data.setdefault('team_id', data.get('team_id'))
                    enhanced_player_data.setdefault('wara', enhanced_player_data.get('WARa', 0.0))

                    # Use Player.from_api_data to handle proper parsing
                    player = Player.from_api_data(enhanced_player_data)
                    players.append(player)
                roster_data[model_field] = players

        # Handle WARA totals
        if 'active' in data and isinstance(data['active'], dict):
            roster_data['total_wara'] = data['active'].get('WARa', 0.0)

        return cls(**roster_data)