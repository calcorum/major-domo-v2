"""
Team service for Discord Bot v2.0

Handles team-related operations with roster management and league queries.
"""
import logging
from typing import Optional, List, Dict, Any

from config import get_config
from services.base_service import BaseService
from models.team import Team, RosterType
from exceptions import APIException
from utils.decorators import cached_single_item

logger = logging.getLogger(f'{__name__}.TeamService')


class TeamService(BaseService[Team]):
    """
    Service for team-related operations.
    
    Features:
    - Team retrieval by ID, abbreviation, and season
    - Manager-based team queries
    - Division and league organization
    - Roster management with position counts and player lists
    - Season-specific team data
    - Standings integration
    """
    
    def __init__(self):
        """Initialize team service."""
        super().__init__(Team, 'teams')
        logger.debug("TeamService initialized")
    
    @cached_single_item(ttl=1800)  # 30-minute cache
    async def get_team(self, team_id: int) -> Optional[Team]:
        """
        Get team by ID with error handling.

        Cached for 30 minutes since team details rarely change.
        Uses @cached_single_item because returns Optional[Team].

        Cache key: team:id:{team_id}

        Args:
            team_id: Unique team identifier

        Returns:
            Team instance or None if not found
        """
        try:
            return await self.get_by_id(team_id)
        except APIException:
            logger.error(f"Failed to get team {team_id}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting team {team_id}: {e}")
            return None
    
    async def get_teams_by_owner(
        self,
        owner_id: int,
        season: Optional[int] = None,
        roster_type: Optional[str] = None
    ) -> List[Team]:
        """
        Get teams owned by a specific Discord user.

        Args:
            owner_id: Discord user ID
            season: Season number (defaults to current season)
            roster_type: Filter by roster type ('ml', 'mil', 'il') - optional

        Returns:
            List of Team instances owned by the user, optionally filtered by type

        Raises:
            Exception: If there's an error communicating with the API
                       Allows caller to distinguish between "no teams" vs "error occurred"
        """
        season = season or get_config().sba_current_season
        params = [
            ('owner_id', str(owner_id)),
            ('season', str(season))
        ]

        teams = await self.get_all_items(params=params)

        # Filter by roster type if specified
        if roster_type and teams:
            try:
                target_type = RosterType(roster_type)
                teams = [team for team in teams if team.roster_type() == target_type]
                logger.debug(f"Filtered to {len(teams)} {roster_type} teams for owner {owner_id}")
            except ValueError:
                logger.warning(f"Invalid roster_type '{roster_type}' - returning all teams")

        if teams:
            logger.debug(f"Found {len(teams)} teams for owner {owner_id} in season {season}")
            return teams

        logger.debug(f"No teams found for owner {owner_id} in season {season}")
        return []

    @cached_single_item(ttl=1800)  # 30-minute cache
    async def get_team_by_owner(self, owner_id: int, season: Optional[int] = None) -> Optional[Team]:
        """
        Get the primary (Major League) team owned by a Discord user.

        This is a convenience method for GM validation - returns the first team
        found for the owner (typically their ML team). For multiple teams or
        roster type filtering, use get_teams_by_owner() instead.

        Cached for 30 minutes since GM assignments rarely change.
        Uses @cached_single_item because returns Optional[Team].

        Cache key: team:owner:{season}:{owner_id}

        Args:
            owner_id: Discord user ID
            season: Season number (defaults to current season)

        Returns:
            Team instance or None if not found
        """
        teams = await self.get_teams_by_owner(owner_id, season, roster_type='ml')
        return teams[0] if teams else None

    async def get_team_by_abbrev(self, abbrev: str, season: Optional[int] = None) -> Optional[Team]:
        """
        Get team by abbreviation for a specific season.
        
        Args:
            abbrev: Team abbreviation (e.g., 'NYY', 'BOS')
            season: Season number (defaults to current season)
            
        Returns:
            Team instance or None if not found
        """
        try:
            season = season or get_config().sba_current_season
            params = [
                ('team_abbrev', abbrev.upper()),
                ('season', str(season))
            ]
            
            teams = await self.get_all_items(params=params)
            
            if teams:
                team = teams[0]  # Should be unique per season
                logger.debug(f"Found team {abbrev} for season {season}: {team.lname}")
                return team
            
            logger.debug(f"No team found for abbreviation '{abbrev}' in season {season}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting team by abbreviation '{abbrev}': {e}")
            return None
    
    async def get_teams_by_season(self, season: int) -> List[Team]:
        """
        Get all teams for a specific season.
        
        Args:
            season: Season number
            
        Returns:
            List of teams in the season
        """
        try:
            params = [('season', str(season))]
            
            teams = await self.get_all_items(params=params)
            logger.debug(f"Retrieved {len(teams)} teams for season {season}")
            return teams
            
        except Exception as e:
            logger.error(f"Failed to get teams for season {season}: {e}")
            return []
    
    async def get_teams_by_manager(self, manager_id: int, season: Optional[int] = None) -> List[Team]:
        """
        Get teams managed by a specific manager.
        
        Uses 'manager_id' query parameter which supports multiple manager matching.
        
        Args:
            manager_id: Manager identifier
            season: Season number (optional)
            
        Returns:
            List of teams managed by the manager
        """
        try:
            params = [('manager_id', str(manager_id))]
            
            if season:
                params.append(('season', str(season)))
            
            teams = await self.get_all_items(params=params)
            logger.debug(f"Found {len(teams)} teams for manager {manager_id}")
            return teams
            
        except Exception as e:
            logger.error(f"Failed to get teams for manager {manager_id}: {e}")
            return []
    
    async def get_teams_by_division(self, division_id: int, season: int) -> List[Team]:
        """
        Get teams in a specific division for a season.
        
        Args:
            division_id: Division identifier
            season: Season number
            
        Returns:
            List of teams in the division
        """
        try:
            params = [
                ('division_id', str(division_id)),
                ('season', str(season))
            ]
            
            teams = await self.get_all_items(params=params)
            logger.debug(f"Retrieved {len(teams)} teams for division {division_id} in season {season}")
            return teams
            
        except Exception as e:
            logger.error(f"Failed to get teams for division {division_id}: {e}")
            return []
    
    async def get_team_roster(self, team_id: int, roster_type: str = 'current') -> Optional[Dict[str, Any]]:
        """
        Get the roster for a team with position counts and player lists.
        
        Returns roster data with active, shortil (minor league), and longil (injured list)
        rosters. Each roster contains position counts and players sorted by descending WARa.
        
        Args:
            team_id: Team identifier
            roster_type: 'current' or 'next' roster
            
        Returns:
            Dictionary with roster structure:
            {
                'active': {
                    'C': 0, '1B': 0, '2B': 0, '3B': 0, 'SS': 0, 'LF': 0, 'CF': 0, 'RF': 0, 'DH': 0,
                    'SP': 0, 'RP': 0, 'CP': 0, 'WARa': 0,
                    'players': [<Player objects>]
                },
                'shortil': { ... },
                'longil': { ... }
            }
        """
        try:
            client = await self.get_client()
            data = await client.get(f'teams/{team_id}/roster/{roster_type}')
            
            if data:
                logger.debug(f"Retrieved {roster_type} roster for team {team_id}")
                return data
            
            logger.debug(f"No roster data found for team {team_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get roster for team {team_id}: {e}")
            return None
    
    async def update_team(self, team_id: int, updates: dict) -> Optional[Team]:
        """
        Update team information.
        
        Args:
            team_id: Team ID to update
            updates: Dictionary of fields to update
            
        Returns:
            Updated team instance or None
        """
        try:
            return await self.update(team_id, updates)
        except Exception as e:
            logger.error(f"Failed to update team {team_id}: {e}")
            return None
    
    async def get_team_standings_position(self, team_id: int, season: int) -> Optional[dict]:
        """
        Get team's standings information.
        
        Calls /standings/team/{team_id} endpoint which returns a Standings object.
        
        Args:
            team_id: Team identifier
            season: Season number
            
        Returns:
            Standings object data for the team
        """
        try:
            client = await self.get_client()
            data = await client.get(f'standings/team/{team_id}', params=[('season', str(season))])
            
            if data:
                logger.debug(f"Retrieved standings for team {team_id}")
                return data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get standings for team {team_id}: {e}")
            return None
    
    async def is_valid_team_abbrev(self, abbrev: str, season: Optional[int] = None) -> bool:
        """
        Check if a team abbreviation is valid for a season.
        
        Args:
            abbrev: Team abbreviation to validate
            season: Season number (defaults to current)
            
        Returns:
            True if the abbreviation is valid
        """
        team = await self.get_team_by_abbrev(abbrev, season)
        return team is not None
    
    async def get_current_season_teams(self) -> List[Team]:
        """
        Get all teams for the current season.
        
        Returns:
            List of teams in current season
        """
        return await self.get_teams_by_season(get_config().sba_current_season)


# Global service instance
team_service = TeamService()