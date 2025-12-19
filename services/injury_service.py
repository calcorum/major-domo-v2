"""
Injury service for Discord Bot v2.0

Handles injury-related operations including checking, creating, and clearing injuries.
"""
import logging
from typing import Optional, List

from services.base_service import BaseService
from models.injury import Injury
from exceptions import APIException

logger = logging.getLogger(f'{__name__}.InjuryService')


class InjuryService(BaseService[Injury]):
    """
    Service for injury-related operations.

    Features:
    - Get active injuries for a player
    - Create new injury records
    - Clear active injuries
    - Season-specific filtering
    """

    def __init__(self):
        """Initialize injury service."""
        super().__init__(Injury, 'injuries')
        logger.debug("InjuryService initialized")

    async def get_active_injury(self, player_id: int, season: int) -> Optional[Injury]:
        """
        Get the active injury for a player in a specific season.

        Args:
            player_id: Player identifier
            season: Season number

        Returns:
            Active Injury instance or None if player has no active injury
        """
        try:
            params = [
                ('player_id', str(player_id)),
                ('season', str(season)),
                ('is_active', 'true')
            ]

            injuries = await self.get_all_items(params=params)

            if injuries:
                logger.debug(f"Found active injury for player {player_id} in season {season}")
                return injuries[0]

            logger.debug(f"No active injury found for player {player_id} in season {season}")
            return None

        except Exception as e:
            logger.error(f"Error getting active injury for player {player_id}: {e}")
            return None

    async def get_injuries_by_player(self, player_id: int, season: int, active_only: bool = False) -> List[Injury]:
        """
        Get all injuries for a player in a specific season.

        Args:
            player_id: Player identifier
            season: Season number
            active_only: If True, only return active injuries

        Returns:
            List of injuries for the player
        """
        try:
            params = [
                ('player_id', str(player_id)),
                ('season', str(season))
            ]

            if active_only:
                params.append(('is_active', 'true'))

            injuries = await self.get_all_items(params=params)
            logger.debug(f"Retrieved {len(injuries)} injuries for player {player_id}")
            return injuries

        except Exception as e:
            logger.error(f"Error getting injuries for player {player_id}: {e}")
            return []

    async def get_injuries_by_team(self, team_id: int, season: int, active_only: bool = True) -> List[Injury]:
        """
        Get all injuries for a team in a specific season.

        Args:
            team_id: Team identifier
            season: Season number
            active_only: If True, only return active injuries

        Returns:
            List of injuries for the team
        """
        try:
            params = [
                ('team_id', str(team_id)),
                ('season', str(season))
            ]

            if active_only:
                params.append(('is_active', 'true'))

            injuries = await self.get_all_items(params=params)
            logger.debug(f"Retrieved {len(injuries)} injuries for team {team_id}")
            return injuries

        except Exception as e:
            logger.error(f"Error getting injuries for team {team_id}: {e}")
            return []

    async def create_injury(
        self,
        season: int,
        player_id: int,
        total_games: int,
        start_week: int,
        start_game: int,
        end_week: int,
        end_game: int
    ) -> Optional[Injury]:
        """
        Create a new injury record.

        Args:
            season: Season number
            player_id: Player identifier
            total_games: Total games player will be out
            start_week: Week injury started
            start_game: Game number injury started (1-4)
            end_week: Week player returns
            end_game: Game number player returns (1-4)

        Returns:
            Created Injury instance or None on failure
        """
        try:
            injury_data = {
                'season': season,
                'player_id': player_id,
                'total_games': total_games,
                'start_week': start_week,
                'start_game': start_game,
                'end_week': end_week,
                'end_game': end_game,
                'is_active': True
            }

            # Call the API to create the injury
            client = await self.get_client()
            response = await client.post(self.endpoint, injury_data)

            if not response:
                logger.error(f"Failed to create injury for player {player_id}: No response from API")
                return None

            # Merge the request data with the response to ensure all required fields are present
            # (API may not return all fields that were sent)
            merged_data = {**injury_data, **response}

            # Create Injury model from merged data
            injury = Injury.from_api_data(merged_data)
            logger.info(f"Created injury for player {player_id}: {total_games} games")
            return injury

        except Exception as e:
            logger.error(f"Error creating injury for player {player_id}: {e}")
            return None

    async def clear_injury(self, injury_id: int) -> bool:
        """
        Clear (deactivate) an injury.

        Args:
            injury_id: Injury identifier

        Returns:
            True if successfully cleared, False otherwise
        """
        try:
            # Note: API expects is_active as query parameter, not JSON body
            updated_injury = await self.patch(injury_id, {'is_active': False}, use_query_params=True)

            if updated_injury:
                logger.info(f"Cleared injury {injury_id}")
                return True

            logger.error(f"Failed to clear injury {injury_id}")
            return False

        except Exception as e:
            logger.error(f"Error clearing injury {injury_id}: {e}")
            return False

    async def get_all_active_injuries_raw(self, season: int) -> list[dict]:
        """
        Get all active injuries for a season with raw API response data.

        This method returns the raw API response which includes nested player
        objects with team information, needed for injury log displays.

        Args:
            season: Season number

        Returns:
            List of raw injury dictionaries from API with nested player/team data
        """
        try:
            client = await self.get_client()
            params = [
                ('season', str(season)),
                ('is_active', 'true'),
                ('sort', 'return-asc')
            ]

            response = await client.get(self.endpoint, params=params)

            if response and 'injuries' in response:
                logger.debug(f"Retrieved {len(response['injuries'])} active injuries for season {season}")
                return response['injuries']

            logger.debug(f"No active injuries found for season {season}")
            return []

        except Exception as e:
            logger.error(f"Error getting all active injuries for season {season}: {e}")
            return []


# Global service instance
injury_service = InjuryService()
