"""
Statistics service for Discord Bot v2.0

Handles batting and pitching statistics retrieval and processing.
"""
import logging
from typing import Optional, List

from services.base_service import BaseService
from models.batting_stats import BattingStats
from models.pitching_stats import PitchingStats
from exceptions import APIException

logger = logging.getLogger(f'{__name__}.StatsService')


class StatsService:
    """
    Service for player statistics operations.
    
    Features:
    - Batting statistics retrieval
    - Pitching statistics retrieval
    - Season-specific filtering
    - Error handling and logging
    """
    
    def __init__(self):
        """Initialize stats service."""
        # We don't inherit from BaseService since we need custom endpoints
        from api.client import get_global_client
        self._get_client = get_global_client
        logger.debug("StatsService initialized")
    
    async def get_client(self):
        """Get the API client."""
        return await self._get_client()
    
    async def get_batting_stats(self, player_id: int, season: int) -> Optional[BattingStats]:
        """
        Get batting statistics for a player in a specific season.
        
        Args:
            player_id: Player ID
            season: Season number
            
        Returns:
            BattingStats instance or None if not found
        """
        try:
            client = await self.get_client()
            
            # Call the batting stats view endpoint
            params = [
                ('player_id', str(player_id)),
                ('season', str(season))
            ]
            
            response = await client.get('views/season-stats/batting', params=params)
            
            if not response or 'stats' not in response:
                logger.debug(f"No batting stats found for player {player_id}, season {season}")
                return None
            
            stats_list = response['stats']
            if not stats_list:
                logger.debug(f"Empty batting stats for player {player_id}, season {season}")
                return None
            
            # Take the first (should be only) result
            stats_data = stats_list[0]
            
            batting_stats = BattingStats.from_api_data(stats_data)
            logger.debug(f"Retrieved batting stats for player {player_id}: {batting_stats.avg:.3f} AVG")
            return batting_stats
            
        except Exception as e:
            logger.error(f"Error getting batting stats for player {player_id}: {e}")
            return None
    
    async def get_pitching_stats(self, player_id: int, season: int) -> Optional[PitchingStats]:
        """
        Get pitching statistics for a player in a specific season.
        
        Args:
            player_id: Player ID
            season: Season number
            
        Returns:
            PitchingStats instance or None if not found
        """
        try:
            client = await self.get_client()
            
            # Call the pitching stats view endpoint
            params = [
                ('player_id', str(player_id)),
                ('season', str(season))
            ]
            
            response = await client.get('views/season-stats/pitching', params=params)
            
            if not response or 'stats' not in response:
                logger.debug(f"No pitching stats found for player {player_id}, season {season}")
                return None
            
            stats_list = response['stats']
            if not stats_list:
                logger.debug(f"Empty pitching stats for player {player_id}, season {season}")
                return None
            
            # Take the first (should be only) result
            stats_data = stats_list[0]
            
            pitching_stats = PitchingStats.from_api_data(stats_data)
            logger.debug(f"Retrieved pitching stats for player {player_id}: {pitching_stats.era:.2f} ERA")
            return pitching_stats
            
        except Exception as e:
            logger.error(f"Error getting pitching stats for player {player_id}: {e}")
            return None
    
    async def get_player_stats(self, player_id: int, season: int) -> tuple[Optional[BattingStats], Optional[PitchingStats]]:
        """
        Get both batting and pitching statistics for a player.
        
        Args:
            player_id: Player ID
            season: Season number
            
        Returns:
            Tuple of (batting_stats, pitching_stats) - either can be None
        """
        try:
            # Get both types of stats concurrently
            batting_task = self.get_batting_stats(player_id, season)
            pitching_task = self.get_pitching_stats(player_id, season)
            
            batting_stats = await batting_task
            pitching_stats = await pitching_task
            
            logger.debug(f"Retrieved stats for player {player_id}: "
                        f"batting={'yes' if batting_stats else 'no'}, "
                        f"pitching={'yes' if pitching_stats else 'no'}")
            
            return batting_stats, pitching_stats
            
        except Exception as e:
            logger.error(f"Error getting player stats for {player_id}: {e}")
            return None, None


# Global service instance
stats_service = StatsService()