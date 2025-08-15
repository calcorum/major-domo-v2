"""
Player service for Discord Bot v2.0

Handles player-related operations with team population and search functionality.
"""
import logging
from typing import Optional, List, TYPE_CHECKING

from services.base_service import BaseService
from models.player import Player
from models.team import Team
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
    
    async def get_player_with_team(self, player_id: int) -> Optional[Player]:
        """
        Get player with team information populated.
        
        Args:
            player_id: Unique player identifier
            
        Returns:
            Player instance with team data or None if not found
        """
        try:
            player = await self.get_player(player_id)
            if not player:
                return None
            
            # Populate team information if team_id exists and TeamService is available
            if player.team_id and self._team_service:
                team = await self._team_service.get_team(player.team_id)
                if team:
                    player.team = team
                    logger.debug(f"Populated team data via TeamService for player {player_id}: {team.sname}")
            # Fallback to direct API call
            elif player.team_id:
                client = await self.get_client()
                team_data = await client.get('teams', object_id=player.team_id)
                if team_data:
                    player.team = Team.from_api_data(team_data)
                    logger.debug(f"Populated team data via API for player {player_id}: {player.team.sname}")
            
            return player
            
        except Exception as e:
            logger.error(f"Error getting player with team {player_id}: {e}")
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
    
    async def search_players_fuzzy(self, query: str, limit: int = 10) -> List[Player]:
        """
        Fuzzy search for players by name with limit.
        
        Args:
            query: Search query
            limit: Maximum results to return
            
        Returns:
            List of matching players (up to limit)
        """
        try:
            players = await self.search(query)
            
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