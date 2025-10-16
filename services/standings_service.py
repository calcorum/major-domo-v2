"""
Standings service for Discord Bot v2.0

Handles team standings retrieval and processing.
"""
import logging
from typing import Optional, List, Dict

from services.base_service import BaseService
from models.standings import TeamStandings
from exceptions import APIException

logger = logging.getLogger(f'{__name__}.StandingsService')


class StandingsService:
    """
    Service for team standings operations.
    
    Features:
    - League standings retrieval
    - Division-based filtering
    - Season-specific data
    - Playoff positioning
    """
    
    def __init__(self):
        """Initialize standings service."""
        from api.client import get_global_client
        self._get_client = get_global_client
        logger.debug("StandingsService initialized")
    
    async def get_client(self):
        """Get the API client."""
        return await self._get_client()
    
    async def get_league_standings(self, season: int) -> List[TeamStandings]:
        """
        Get complete league standings for a season.
        
        Args:
            season: Season number
            
        Returns:
            List of TeamStandings ordered by record
        """
        try:
            client = await self.get_client()
            
            params = [('season', str(season))]
            response = await client.get('standings', params=params)
            
            if not response or 'standings' not in response:
                logger.warning(f"No standings data found for season {season}")
                return []
            
            standings_list = response['standings']
            if not standings_list:
                logger.warning(f"Empty standings for season {season}")
                return []
            
            # Convert to model objects
            standings = []
            for standings_data in standings_list:
                try:
                    team_standings = TeamStandings.from_api_data(standings_data)
                    standings.append(team_standings)
                except Exception as e:
                    logger.error(f"Error parsing standings data for team: {e}")
                    continue
            
            logger.info(f"Retrieved standings for {len(standings)} teams in season {season}")
            return standings
            
        except Exception as e:
            logger.error(f"Error getting league standings for season {season}: {e}")
            return []
    
    async def get_standings_by_division(self, season: int) -> Dict[str, List[TeamStandings]]:
        """
        Get standings grouped by division.
        
        Args:
            season: Season number
            
        Returns:
            Dictionary mapping division names to team standings
        """
        try:
            all_standings = await self.get_league_standings(season)
            
            if not all_standings:
                return {}
            
            # Group by division
            divisions = {}
            for team_standings in all_standings:
                if hasattr(team_standings.team, 'division') and team_standings.team.division:
                    div_name = team_standings.team.division.division_name
                    if div_name not in divisions:
                        divisions[div_name] = []
                    divisions[div_name].append(team_standings)
                else:
                    # Handle teams without division
                    if "No Division" not in divisions:
                        divisions["No Division"] = []
                    divisions["No Division"].append(team_standings)
            
            # Sort each division by record (wins descending, then by winning percentage)
            for div_name in divisions:
                divisions[div_name].sort(
                    key=lambda x: (x.wins, x.winning_percentage), 
                    reverse=True
                )
            
            logger.debug(f"Grouped standings into {len(divisions)} divisions")
            return divisions
            
        except Exception as e:
            logger.error(f"Error grouping standings by division: {e}")
            return {}
    
    async def get_team_standings(self, team_abbrev: str, season: int) -> Optional[TeamStandings]:
        """
        Get standings for a specific team.
        
        Args:
            team_abbrev: Team abbreviation (e.g., 'NYY')
            season: Season number
            
        Returns:
            TeamStandings instance or None if not found
        """
        try:
            all_standings = await self.get_league_standings(season)
            
            # Find team by abbreviation
            team_abbrev_upper = team_abbrev.upper()
            for team_standings in all_standings:
                if team_standings.team.abbrev.upper() == team_abbrev_upper:
                    logger.debug(f"Found standings for {team_abbrev}: {team_standings}")
                    return team_standings
            
            logger.warning(f"No standings found for team {team_abbrev} in season {season}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting standings for team {team_abbrev}: {e}")
            return None
    
    async def get_playoff_picture(self, season: int) -> Dict[str, List[TeamStandings]]:
        """
        Get playoff picture with division leaders and wild card contenders.
        
        Args:
            season: Season number
            
        Returns:
            Dictionary with 'division_leaders' and 'wild_card' lists
        """
        try:
            divisions = await self.get_standings_by_division(season)
            
            if not divisions:
                return {"division_leaders": [], "wild_card": []}
            
            # Get division leaders (first place in each division)
            division_leaders = []
            wild_card_candidates = []
            
            for div_name, teams in divisions.items():
                if teams:  # Division has teams
                    # First team is division leader
                    division_leaders.append(teams[0])
                    
                    # Rest are potential wild card candidates
                    for team in teams[1:]:
                        wild_card_candidates.append(team)
            
            # Sort wild card candidates by record
            wild_card_candidates.sort(
                key=lambda x: (x.wins, x.winning_percentage),
                reverse=True
            )
            
            # Take top wild card contenders (typically top 6-8 teams)
            wild_card_contenders = wild_card_candidates[:8]
            
            logger.debug(f"Playoff picture: {len(division_leaders)} division leaders, "
                        f"{len(wild_card_contenders)} wild card contenders")
            
            return {
                "division_leaders": division_leaders,
                "wild_card": wild_card_contenders
            }
            
        except Exception as e:
            logger.error(f"Error generating playoff picture: {e}")
            return {"division_leaders": [], "wild_card": []}

    async def recalculate_standings(self, season: int) -> bool:
        """
        Trigger standings recalculation for a season.

        Calls POST /standings/s{season}/recalculate

        Args:
            season: Season number to recalculate

        Returns:
            True if successful

        Raises:
            APIException: If recalculation fails
        """
        try:
            client = await self.get_client()

            # Use 8 second timeout for this potentially slow operation
            response = await client.post(
                f'standings/s{season}/recalculate',
                {},
                timeout=8.0
            )

            logger.info(f"Recalculated standings for season {season}")
            return True

        except Exception as e:
            logger.error(f"Failed to recalculate standings: {e}")
            raise APIException(f"Failed to recalculate standings: {e}")


# Global service instance
standings_service = StandingsService()