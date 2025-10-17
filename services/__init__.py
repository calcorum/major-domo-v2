"""
Business logic services for Discord Bot v2.0

Service layer providing clean interfaces to data operations.
"""

from .team_service import TeamService, team_service
from .player_service import PlayerService, player_service
from .league_service import LeagueService, league_service
from .schedule_service import ScheduleService, schedule_service
from .giphy_service import GiphyService

# Wire services together for dependency injection
player_service._team_service = team_service

# Create global Giphy service instance
giphy_service = GiphyService()

__all__ = [
    'TeamService', 'team_service',
    'PlayerService', 'player_service',
    'LeagueService', 'league_service',
    'ScheduleService', 'schedule_service',
    'GiphyService', 'giphy_service'
]