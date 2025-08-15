"""
League service for Discord Bot v2.0

Handles league-wide operations including current state, standings, and season information.
"""
import logging
from typing import Optional, List, Dict, Any

from services.base_service import BaseService
from models.current import Current
from constants import SBA_CURRENT_SEASON
from exceptions import APIException

logger = logging.getLogger(f'{__name__}.LeagueService')


class LeagueService(BaseService[Current]):
    """
    Service for league-wide operations.
    
    Features:
    - Current league state retrieval
    - Season standings
    - League-wide statistics
    """
    
    def __init__(self):
        """Initialize league service."""
        super().__init__(Current, 'current')
        logger.debug("LeagueService initialized")
    
    async def get_current_state(self) -> Optional[Current]:
        """
        Get the current league state including week, season, and settings.
        
        Returns:
            Current league state or None if not available
        """
        try:
            client = await self.get_client()
            data = await client.get('current')
            
            if data:
                current = Current.from_api_data(data)
                logger.debug(f"Retrieved current state: Week {current.week}, Season {current.season}")
                return current
            
            logger.debug("No current state data found")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get current league state: {e}")
            return None
    
    async def get_standings(self, season: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Get league standings for a season.
        
        Args:
            season: Season number (defaults to current season)
            
        Returns:
            List of standings data or None if not available
        """
        try:
            season = season or SBA_CURRENT_SEASON
            client = await self.get_client()
            data = await client.get('standings', params=[('season', str(season))])
            
            if data and isinstance(data, list):
                logger.debug(f"Retrieved standings for season {season}: {len(data)} teams")
                return data
            elif data and isinstance(data, dict):
                # Handle case where API returns a dict with standings array
                standings_data = data.get('standings', data.get('items', []))
                if standings_data:
                    logger.debug(f"Retrieved standings for season {season}: {len(standings_data)} teams")
                    return standings_data
            
            logger.debug(f"No standings data found for season {season}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get standings for season {season}: {e}")
            return None
    
    async def get_division_standings(self, division_id: int, season: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Get standings for a specific division.
        
        Args:
            division_id: Division identifier
            season: Season number (defaults to current season)
            
        Returns:
            List of division standings or None if not available
        """
        try:
            season = season or SBA_CURRENT_SEASON
            client = await self.get_client()
            data = await client.get(f'standings/division/{division_id}', params=[('season', str(season))])
            
            if data and isinstance(data, list):
                logger.debug(f"Retrieved division {division_id} standings for season {season}: {len(data)} teams")
                return data
            
            logger.debug(f"No division standings found for division {division_id}, season {season}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get division {division_id} standings: {e}")
            return None
    
    async def get_league_leaders(self, stat_type: str = 'batting', season: Optional[int] = None, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        Get league leaders for a specific statistic category.
        
        Args:
            stat_type: Type of stats ('batting', 'pitching', 'fielding')
            season: Season number (defaults to current season)
            limit: Number of leaders to return
            
        Returns:
            List of league leaders or None if not available
        """
        try:
            season = season or SBA_CURRENT_SEASON
            client = await self.get_client()
            
            params = [
                ('season', str(season)),
                ('limit', str(limit))
            ]
            
            data = await client.get(f'leaders/{stat_type}', params=params)
            
            if data:
                # Handle different response formats
                if isinstance(data, list):
                    leaders = data
                elif isinstance(data, dict):
                    leaders = data.get('leaders', data.get('items', data.get('results', [])))
                else:
                    leaders = []
                
                logger.debug(f"Retrieved {stat_type} leaders for season {season}: {len(leaders)} players")
                return leaders[:limit]  # Ensure we don't exceed limit
            
            logger.debug(f"No {stat_type} leaders found for season {season}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get {stat_type} leaders for season {season}: {e}")
            return None


# Global service instance
league_service = LeagueService()