"""
Player service for Discord Bot v2.0

Handles player-related operations with team population and search functionality.
"""
import logging
from typing import Optional, List, TYPE_CHECKING

from services.base_service import BaseService
from models.player import Player
from constants import FREE_AGENT_TEAM_ID, SBA_CURRENT_SEASON
from exceptions import APIException

if TYPE_CHECKING:
    from services.team_service import TeamService

logger = logging.getLogger(f'{__name__}.PlayerService')


class PlayerService(BaseService[Player]):
    """
    Service for player-related operations.
    
    Features:
    - Player retrieval with team population
    - Team roster queries
    - Name-based search with exact matching
    - Season-specific filtering
    - Free agent handling via constants
    """
    
    def __init__(self, team_service: Optional['TeamService'] = None):
        """Initialize player service."""
        super().__init__(Player, 'players')
        self._team_service = team_service
        logger.debug("PlayerService initialized")
    
    async def get_player(self, player_id: int) -> Optional[Player]:
        """
        Get player by ID with error handling.
        
        Args:
            player_id: Unique player identifier
            
        Returns:
            Player instance or None if not found
        """
        try:
            return await self.get_by_id(player_id)
        except APIException:
            logger.error(f"Failed to get player {player_id}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting player {player_id}: {e}")
            return None
    
    
    async def get_players_by_team(self, team_id: int, season: int) -> List[Player]:
        """
        Get all players for a specific team.
        
        Args:
            team_id: Team identifier
            season: Season number (required)
            
        Returns:
            List of players on the team
        """
        try:
            params = [
                ('season', str(season)),
                ('team_id', str(team_id))
            ]
            
            players = await self.get_all_items(params=params)
            logger.debug(f"Retrieved {len(players)} players for team {team_id} in season {season}")
            return players
            
        except Exception as e:
            logger.error(f"Failed to get players for team {team_id}: {e}")
            return []
    
    async def get_players_by_name(self, name: str, season: int) -> List[Player]:
        """
        Search for players by name (partial match).
        
        Args:
            name: Player name or partial name
            season: Season number (required)
            
        Returns:
            List of matching players
        """
        try:
            params = [
                ('season', str(season)),
                ('name', name)
            ]
            
            players = await self.get_all_items(params=params)
            logger.debug(f"Found {len(players)} players matching '{name}' in season {season}")
            return players
            
        except Exception as e:
            logger.error(f"Failed to search players by name '{name}': {e}")
            return []
    
    async def get_player_by_name_exact(self, name: str, season: int) -> Optional[Player]:
        """
        Get player by exact name match (case-insensitive).
        
        Args:
            name: Exact player name
            season: Season number (required)
            
        Returns:
            Player instance or None if not found
        """
        try:
            players = await self.get_players_by_name(name, season)
            
            # Look for exact case-insensitive match
            name_lower = name.lower()
            for player in players:
                if player.name.lower() == name_lower:
                    logger.debug(f"Found exact match for '{name}': {player.name}")
                    return player
            
            logger.debug(f"No exact match found for '{name}'")
            return None
            
        except Exception as e:
            logger.error(f"Error finding exact player match for '{name}': {e}")
            return None
    
    async def search_players(self, query: str, limit: int = 10, season: Optional[int] = None) -> List[Player]:
        """
        Search for players using the dedicated /v3/players/search endpoint.

        Args:
            query: Search query for player name
            limit: Maximum number of results to return (1-50)
            season: Season to search in (defaults to current season)

        Returns:
            List of matching players (up to limit)
        """
        try:
            params = [('q', query), ('limit', str(limit))]
            if season is not None:
                params.append(('season', str(season)))

            client = await self.get_client()
            data = await client.get('players/search', params=params)

            if not data:
                logger.debug(f"No players found for search query '{query}'")
                return []

            # Handle API response format: {'count': int, 'players': [...]}
            items, count = self._extract_items_and_count_from_response(data)
            players = [self.model_class.from_api_data(item) for item in items]

            logger.debug(f"Search '{query}' returned {len(players)} of {count} matches")
            return players

        except Exception as e:
            logger.error(f"Error in player search for '{query}': {e}")
            return []

    async def search_players_fuzzy(self, query: str, limit: int = 10, season: Optional[int] = None) -> List[Player]:
        """
        Fuzzy search for players by name with limit using existing name search functionality.

        Args:
            query: Search query
            limit: Maximum results to return
            season: Season to search in (defaults to current season)

        Returns:
            List of matching players (up to limit)
        """
        try:
            if season is None:
                from constants import SBA_CURRENT_SEASON
                season = SBA_CURRENT_SEASON

            # Use the existing name-based search that actually works
            players = await self.get_players_by_name(query, season)

            # Sort by relevance (exact matches first, then partial)
            query_lower = query.lower()
            exact_matches = []
            partial_matches = []

            for player in players:
                name_lower = player.name.lower()
                if name_lower == query_lower:
                    exact_matches.append(player)
                elif query_lower in name_lower:
                    partial_matches.append(player)

            # Combine and limit results
            results = exact_matches + partial_matches
            limited_results = results[:limit]

            logger.debug(f"Fuzzy search '{query}' returned {len(limited_results)} of {len(results)} matches")
            return limited_results

        except Exception as e:
            logger.error(f"Error in fuzzy search for '{query}': {e}")
            return []
    
    
    async def get_free_agents(self, season: int) -> List[Player]:
        """
        Get all free agent players.
        
        Args:
            season: Season number (required)
            
        Returns:
            List of free agent players
        """
        try:
            params = [('team_id', FREE_AGENT_TEAM_ID), ('season', str(season))]
            
            players = await self.get_all_items(params=params)
            logger.debug(f"Retrieved {len(players)} free agents")
            return players
            
        except Exception as e:
            logger.error(f"Failed to get free agents: {e}")
            return []
    
    async def is_free_agent(self, player: Player) -> bool:
        """
        Check if a player is a free agent.
        
        Args:
            player: Player instance to check
            
        Returns:
            True if player is a free agent
        """
        return player.team_id == FREE_AGENT_TEAM_ID
    
    async def get_players_by_position(self, position: str, season: int) -> List[Player]:
        """
        Get players by position.
        
        Args:
            position: Player position (e.g., 'C', '1B', 'OF')
            season: Season number (required)
            
        Returns:
            List of players at the position
        """
        try:
            params = [('position', position), ('season', str(season))]
            
            players = await self.get_all_items(params=params)
            logger.debug(f"Retrieved {len(players)} players at position {position}")
            return players
            
        except Exception as e:
            logger.error(f"Failed to get players by position {position}: {e}")
            return []
    
    
    async def update_player(self, player_id: int, updates: dict) -> Optional[Player]:
        """
        Update player information.
        
        Args:
            player_id: Player ID to update
            updates: Dictionary of fields to update
            
        Returns:
            Updated player instance or None
        """
        try:
            return await self.update(player_id, updates)
        except Exception as e:
            logger.error(f"Failed to update player {player_id}: {e}")
            return None


# Global service instance - will be properly initialized in __init__.py
player_service = PlayerService()