"""
Schedule service for Discord Bot v2.0

Handles game schedule and results retrieval and processing.
"""
import logging
from typing import Optional, List, Dict, Tuple

from services.base_service import BaseService
from models.game import Game
from exceptions import APIException

logger = logging.getLogger(f'{__name__}.ScheduleService')


class ScheduleService:
    """
    Service for schedule and game operations.
    
    Features:
    - Weekly schedule retrieval
    - Team-specific schedules
    - Game results and upcoming games
    - Series organization
    """
    
    def __init__(self):
        """Initialize schedule service."""
        from api.client import get_global_client
        self._get_client = get_global_client
        logger.debug("ScheduleService initialized")
    
    async def get_client(self):
        """Get the API client."""
        return await self._get_client()
    
    async def get_week_schedule(self, season: int, week: int) -> List[Game]:
        """
        Get all games for a specific week.
        
        Args:
            season: Season number
            week: Week number
            
        Returns:
            List of Game instances for the week
        """
        try:
            client = await self.get_client()
            
            params = [
                ('season', str(season)),
                ('week', str(week))
            ]
            
            response = await client.get('games', params=params)
            
            if not response or 'games' not in response:
                logger.warning(f"No games data found for season {season}, week {week}")
                return []
            
            games_list = response['games']
            if not games_list:
                logger.warning(f"Empty games list for season {season}, week {week}")
                return []
            
            # Convert to Game objects
            games = []
            for game_data in games_list:
                try:
                    game = Game.from_api_data(game_data)
                    games.append(game)
                except Exception as e:
                    logger.error(f"Error parsing game data: {e}")
                    continue
            
            logger.info(f"Retrieved {len(games)} games for season {season}, week {week}")
            return games
            
        except Exception as e:
            logger.error(f"Error getting week schedule for season {season}, week {week}: {e}")
            return []
    
    async def get_team_schedule(self, season: int, team_abbrev: str, weeks: Optional[int] = None) -> List[Game]:
        """
        Get schedule for a specific team.
        
        Args:
            season: Season number
            team_abbrev: Team abbreviation (e.g., 'NYY')
            weeks: Number of weeks to retrieve (None for all weeks)
            
        Returns:
            List of Game instances for the team
        """
        try:
            team_games = []
            team_abbrev_upper = team_abbrev.upper()
            
            # If weeks not specified, try a reasonable range (18 weeks typical)
            week_range = range(1, (weeks + 1) if weeks else 19)
            
            for week in week_range:
                week_games = await self.get_week_schedule(season, week)
                
                # Filter games involving this team
                for game in week_games:
                    if (game.away_team.abbrev.upper() == team_abbrev_upper or 
                        game.home_team.abbrev.upper() == team_abbrev_upper):
                        team_games.append(game)
            
            logger.info(f"Retrieved {len(team_games)} games for team {team_abbrev}")
            return team_games
            
        except Exception as e:
            logger.error(f"Error getting team schedule for {team_abbrev}: {e}")
            return []
    
    async def get_recent_games(self, season: int, weeks_back: int = 2) -> List[Game]:
        """
        Get recently completed games.
        
        Args:
            season: Season number
            weeks_back: Number of weeks back to look
            
        Returns:
            List of completed Game instances
        """
        try:
            recent_games = []
            
            # Get games from recent weeks
            for week_offset in range(weeks_back):
                # This is simplified - in production you'd want to determine current week
                week = 10 - week_offset  # Assuming we're around week 10
                if week <= 0:
                    break
                
                week_games = await self.get_week_schedule(season, week)
                
                # Only include completed games
                completed_games = [game for game in week_games if game.is_completed]
                recent_games.extend(completed_games)
            
            # Sort by week descending (most recent first)
            recent_games.sort(key=lambda x: (x.week, x.game_num or 0), reverse=True)
            
            logger.debug(f"Retrieved {len(recent_games)} recent games")
            return recent_games
            
        except Exception as e:
            logger.error(f"Error getting recent games: {e}")
            return []
    
    async def get_upcoming_games(self, season: int, weeks_ahead: int = 6) -> List[Game]:
        """
        Get upcoming scheduled games by scanning multiple weeks.
        
        Args:
            season: Season number
            weeks_ahead: Number of weeks to scan ahead (default 6)
            
        Returns:
            List of upcoming Game instances
        """
        try:
            upcoming_games = []
            
            # Scan through weeks to find games without scores
            for week in range(1, 19):  # Standard season length
                week_games = await self.get_week_schedule(season, week)
                
                # Find games without scores (not yet played)
                upcoming_games_week = [game for game in week_games if not game.is_completed]
                upcoming_games.extend(upcoming_games_week)
                
                # If we found upcoming games, we can limit how many more weeks to check
                if upcoming_games and len(upcoming_games) >= 20:  # Reasonable limit
                    break
            
            # Sort by week, then game number
            upcoming_games.sort(key=lambda x: (x.week, x.game_num or 0))
            
            logger.debug(f"Retrieved {len(upcoming_games)} upcoming games")
            return upcoming_games
            
        except Exception as e:
            logger.error(f"Error getting upcoming games: {e}")
            return []
    
    async def get_series_by_teams(self, season: int, week: int, team1_abbrev: str, team2_abbrev: str) -> List[Game]:
        """
        Get all games in a series between two teams for a specific week.
        
        Args:
            season: Season number
            week: Week number
            team1_abbrev: First team abbreviation
            team2_abbrev: Second team abbreviation
            
        Returns:
            List of Game instances in the series
        """
        try:
            week_games = await self.get_week_schedule(season, week)
            
            team1_upper = team1_abbrev.upper()
            team2_upper = team2_abbrev.upper()
            
            # Find games between these two teams
            series_games = []
            for game in week_games:
                game_teams = {game.away_team.abbrev.upper(), game.home_team.abbrev.upper()}
                if game_teams == {team1_upper, team2_upper}:
                    series_games.append(game)
            
            # Sort by game number
            series_games.sort(key=lambda x: x.game_num or 0)
            
            logger.debug(f"Retrieved {len(series_games)} games in series between {team1_abbrev} and {team2_abbrev}")
            return series_games
            
        except Exception as e:
            logger.error(f"Error getting series between {team1_abbrev} and {team2_abbrev}: {e}")
            return []
    
    def group_games_by_series(self, games: List[Game]) -> Dict[Tuple[str, str], List[Game]]:
        """
        Group games by matchup (series).
        
        Args:
            games: List of Game instances
            
        Returns:
            Dictionary mapping (team1, team2) tuples to game lists
        """
        series_games = {}
        
        for game in games:
            # Create consistent team pairing (alphabetical order)
            teams = sorted([game.away_team.abbrev, game.home_team.abbrev])
            series_key = (teams[0], teams[1])
            
            if series_key not in series_games:
                series_games[series_key] = []
            series_games[series_key].append(game)
        
        # Sort each series by game number
        for series_key in series_games:
            series_games[series_key].sort(key=lambda x: x.game_num or 0)
        
        return series_games


# Global service instance
schedule_service = ScheduleService()