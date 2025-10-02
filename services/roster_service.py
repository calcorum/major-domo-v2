"""
Roster service for Discord Bot v2.0

Handles roster operations and validation.
"""
import logging
from typing import Optional, List, Dict

from services.base_service import BaseService
from models.roster import TeamRoster
from models.player import Player
from models.transaction import RosterValidation
from exceptions import APIException

logger = logging.getLogger(f'{__name__}.RosterService')


class RosterService:
    """Service for roster operations and validation."""
    
    def __init__(self):
        """Initialize roster service."""
        from api.client import get_global_client
        self._get_client = get_global_client
        logger.debug("RosterService initialized")
    
    async def get_client(self):
        """Get the API client."""
        return await self._get_client()
    
    async def get_team_roster(
        self, 
        team_id: int, 
        week_type: str = "current"
    ) -> Optional[TeamRoster]:
        """
        Get team roster for current or next week.
        
        Args:
            team_id: Team ID from database
            week_type: "current" or "next"
            
        Returns:
            TeamRoster object or None if not found
        """
        try:
            client = await self.get_client()
            
            # Use the team roster endpoint
            roster_data = await client.get(f'teams/{team_id}/roster/{week_type}')
            
            if not roster_data:
                logger.warning(f"No roster data found for team {team_id}, week {week_type}")
                return None
            
            # Add team metadata if not present
            if 'team_id' not in roster_data:
                roster_data['team_id'] = team_id
            
            # Determine week number (this might need adjustment based on API)
            roster_data.setdefault('week', 0)  # Will need current week info
            roster_data.setdefault('season', 12)  # Will need current season info
            
            roster = TeamRoster.from_api_data(roster_data)
            
            logger.debug(f"Retrieved roster for team {team_id}, {week_type} week")
            return roster
            
        except Exception as e:
            logger.error(f"Error getting roster for team {team_id}: {e}")
            raise APIException(f"Failed to retrieve roster: {e}")
    
    async def get_current_roster(self, team_id: int) -> Optional[TeamRoster]:
        """Get current week roster."""
        return await self.get_team_roster(team_id, "current")
    
    async def get_next_roster(self, team_id: int) -> Optional[TeamRoster]:
        """Get next week roster.""" 
        return await self.get_team_roster(team_id, "next")
    
    async def validate_roster(self, roster: TeamRoster) -> RosterValidation:
        """
        Validate roster for legality according to league rules.
        
        Args:
            roster: TeamRoster to validate
            
        Returns:
            RosterValidation with results
        """
        try:
            validation = RosterValidation(
                is_legal=True,
                total_players=roster.total_players,
                active_players=roster.active_count,
                il_players=roster.il_count,
                minor_league_players=roster.minor_league_count,
                total_wara=roster.total_wara
            )
            
            # Validate active roster size (typical limits)
            if roster.active_count > 25:  # Adjust based on league rules
                validation.is_legal = False
                validation.errors.append(f"Too many active players: {roster.active_count}/25")
            elif roster.active_count < 20:  # Minimum active roster
                validation.warnings.append(f"Low active player count: {roster.active_count}")
            
            # Validate total roster size
            if roster.total_players > 50:  # Adjust based on league rules
                validation.is_legal = False
                validation.errors.append(f"Total roster too large: {roster.total_players}/50")
            
            # Position requirements validation
            position_counts = self._count_positions(roster.active_players)
            
            # Check catcher requirement (at least 2 catchers)
            if position_counts.get('C', 0) < 2:
                validation.warnings.append("Fewer than 2 catchers on active roster")
            
            # Check pitcher requirements (at least 10 pitchers)
            pitcher_count = position_counts.get('SP', 0) + position_counts.get('RP', 0) + position_counts.get('P', 0)
            if pitcher_count < 10:
                validation.warnings.append(f"Fewer than 10 pitchers on active roster: {pitcher_count}")
            
            # WARA validation (if there are limits)
            if validation.total_wara > 100:  # Adjust based on league rules
                validation.warnings.append(f"High WARA total: {validation.total_wara:.1f}")
            elif validation.total_wara < 20:
                validation.warnings.append(f"Low WARA total: {validation.total_wara:.1f}")
            
            logger.debug(f"Validated roster: legal={validation.is_legal}, {len(validation.errors)} errors, {len(validation.warnings)} warnings")
            return validation
            
        except Exception as e:
            logger.error(f"Error validating roster: {e}")
            return RosterValidation(
                is_legal=False,
                errors=[f"Validation error: {str(e)}"]
            )
    
    def _count_positions(self, players: List[Player]) -> Dict[str, int]:
        """Count players by position."""
        position_counts = {}
        for player in players:
            pos = player.primary_position
            position_counts[pos] = position_counts.get(pos, 0) + 1
        return position_counts
    
    async def get_roster_summary(self, roster: TeamRoster) -> Dict[str, any]:
        """
        Get a summary of roster composition.
        
        Args:
            roster: TeamRoster to summarize
            
        Returns:
            Dictionary with roster summary information
        """
        try:
            position_counts = self._count_positions(roster.active_players)
            
            # Group positions
            catchers = position_counts.get('C', 0)
            infielders = sum(position_counts.get(pos, 0) for pos in ['1B', '2B', '3B', 'SS', 'IF'])
            outfielders = sum(position_counts.get(pos, 0) for pos in ['LF', 'CF', 'RF', 'OF'])
            pitchers = sum(position_counts.get(pos, 0) for pos in ['SP', 'RP', 'P'])
            dh = position_counts.get('DH', 0)
            
            summary = {
                'total_active': roster.active_count,
                'total_il': roster.il_count,
                'total_minor': roster.minor_league_count,
                'total_wara': roster.total_wara,
                'positions': {
                    'catchers': catchers,
                    'infielders': infielders,
                    'outfielders': outfielders,
                    'pitchers': pitchers,
                    'dh': dh
                },
                'detailed_positions': position_counts
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error creating roster summary: {e}")
            return {}


# Global service instance
roster_service = RosterService()