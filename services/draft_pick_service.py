"""
Draft pick service for Discord Bot v2.0

Handles draft pick CRUD operations. NO CACHING - draft data changes constantly.
"""
import logging
from typing import Optional, List

from services.base_service import BaseService
from models.draft_pick import DraftPick
from exceptions import APIException

logger = logging.getLogger(f'{__name__}.DraftPickService')


class DraftPickService(BaseService[DraftPick]):
    """
    Service for draft pick operations.

    IMPORTANT: This service does NOT use caching decorators because draft picks
    change constantly during an active draft. Always fetch fresh data.

    Features:
    - Get pick by overall number
    - Get picks by team
    - Get picks by round
    - Update pick with player selection
    - Query available/taken picks
    """

    def __init__(self):
        """Initialize draft pick service."""
        super().__init__(DraftPick, 'draftpicks')
        logger.debug("DraftPickService initialized")

    async def get_pick(self, season: int, overall: int) -> Optional[DraftPick]:
        """
        Get specific pick by season and overall number.

        NOT cached - picks change during draft.

        Args:
            season: Draft season
            overall: Overall pick number

        Returns:
            DraftPick instance or None if not found
        """
        try:
            params = [
                ('season', str(season)),
                ('overall', str(overall))
            ]

            picks = await self.get_all_items(params=params)

            if picks:
                pick = picks[0]
                logger.debug(f"Found pick #{overall} for season {season}")
                return pick

            logger.debug(f"No pick found for season {season}, overall #{overall}")
            return None

        except Exception as e:
            logger.error(f"Error getting pick season={season} overall={overall}: {e}")
            return None

    async def get_picks_by_team(
        self,
        season: int,
        team_id: int,
        round_start: int = 1,
        round_end: int = 32
    ) -> List[DraftPick]:
        """
        Get all picks owned by a team in a season.

        NOT cached - picks change as they're traded.

        Args:
            season: Draft season
            team_id: Team ID that owns the picks
            round_start: Starting round (inclusive)
            round_end: Ending round (inclusive)

        Returns:
            List of DraftPick instances owned by team
        """
        try:
            params = [
                ('season', str(season)),
                ('owner_team_id', str(team_id)),
                ('round_start', str(round_start)),
                ('round_end', str(round_end)),
                ('sort', 'order-asc')
            ]

            picks = await self.get_all_items(params=params)
            logger.debug(f"Found {len(picks)} picks for team {team_id} in rounds {round_start}-{round_end}")
            return picks

        except Exception as e:
            logger.error(f"Error getting picks for team {team_id}: {e}")
            return []

    async def get_picks_by_round(
        self,
        season: int,
        round_num: int,
        include_taken: bool = True
    ) -> List[DraftPick]:
        """
        Get all picks in a specific round.

        NOT cached - picks change as they're selected.

        Args:
            season: Draft season
            round_num: Round number
            include_taken: Whether to include picks with players selected

        Returns:
            List of DraftPick instances in the round
        """
        try:
            params = [
                ('season', str(season)),
                ('pick_round_start', str(round_num)),
                ('pick_round_end', str(round_num)),
                ('sort', 'order-asc')
            ]

            if not include_taken:
                params.append(('player_taken', 'false'))

            picks = await self.get_all_items(params=params)
            logger.debug(f"Found {len(picks)} picks in round {round_num}")
            return picks

        except Exception as e:
            logger.error(f"Error getting picks for round {round_num}: {e}")
            return []

    async def get_available_picks(
        self,
        season: int,
        overall_start: Optional[int] = None,
        overall_end: Optional[int] = None
    ) -> List[DraftPick]:
        """
        Get picks that haven't been selected yet.

        NOT cached - availability changes constantly.

        Args:
            season: Draft season
            overall_start: Starting overall pick number (optional)
            overall_end: Ending overall pick number (optional)

        Returns:
            List of available DraftPick instances
        """
        try:
            params = [
                ('season', str(season)),
                ('player_taken', 'false'),
                ('sort', 'order-asc')
            ]

            if overall_start is not None:
                params.append(('overall_start', str(overall_start)))
            if overall_end is not None:
                params.append(('overall_end', str(overall_end)))

            picks = await self.get_all_items(params=params)
            logger.debug(f"Found {len(picks)} available picks")
            return picks

        except Exception as e:
            logger.error(f"Error getting available picks: {e}")
            return []

    async def get_recent_picks(
        self,
        season: int,
        overall_end: int,
        limit: int = 5
    ) -> List[DraftPick]:
        """
        Get recent picks before a specific pick number.

        NOT cached - recent picks change as draft progresses.

        Args:
            season: Draft season
            overall_end: Get picks before this overall number
            limit: Number of picks to retrieve

        Returns:
            List of recent DraftPick instances (reverse chronological)
        """
        try:
            params = [
                ('season', str(season)),
                ('overall_end', str(overall_end - 1)),  # Exclude current pick
                ('player_taken', 'true'),  # Only taken picks
                ('sort', 'order-desc'),  # Most recent first
                ('limit', str(limit))
            ]

            picks = await self.get_all_items(params=params)
            logger.debug(f"Found {len(picks)} recent picks before #{overall_end}")
            return picks

        except Exception as e:
            logger.error(f"Error getting recent picks: {e}")
            return []

    async def get_upcoming_picks(
        self,
        season: int,
        overall_start: int,
        limit: int = 5
    ) -> List[DraftPick]:
        """
        Get upcoming picks after a specific pick number.

        NOT cached - upcoming picks change as draft progresses.

        Args:
            season: Draft season
            overall_start: Get picks after this overall number
            limit: Number of picks to retrieve

        Returns:
            List of upcoming DraftPick instances
        """
        try:
            params = [
                ('season', str(season)),
                ('overall_start', str(overall_start + 1)),  # Exclude current pick
                ('sort', 'order-asc'),  # Chronological order
                ('limit', str(limit))
            ]

            picks = await self.get_all_items(params=params)
            logger.debug(f"Found {len(picks)} upcoming picks after #{overall_start}")
            return picks

        except Exception as e:
            logger.error(f"Error getting upcoming picks: {e}")
            return []

    async def update_pick_selection(
        self,
        pick_id: int,
        player_id: int
    ) -> Optional[DraftPick]:
        """
        Update a pick with player selection.

        Args:
            pick_id: Draft pick database ID
            player_id: Player ID being selected

        Returns:
            Updated DraftPick instance or None if update failed
        """
        try:
            update_data = {'player_id': player_id}
            updated_pick = await self.patch(pick_id, update_data)

            if updated_pick:
                logger.info(f"Updated pick #{pick_id} with player {player_id}")
            else:
                logger.error(f"Failed to update pick #{pick_id}")

            return updated_pick

        except Exception as e:
            logger.error(f"Error updating pick {pick_id}: {e}")
            return None

    async def clear_pick_selection(self, pick_id: int) -> Optional[DraftPick]:
        """
        Clear player selection from a pick (for admin wipe operations).

        Args:
            pick_id: Draft pick database ID

        Returns:
            Updated DraftPick instance with player cleared, or None if failed
        """
        try:
            update_data = {'player_id': None}
            updated_pick = await self.patch(pick_id, update_data)

            if updated_pick:
                logger.info(f"Cleared player selection from pick #{pick_id}")
            else:
                logger.error(f"Failed to clear pick #{pick_id}")

            return updated_pick

        except Exception as e:
            logger.error(f"Error clearing pick {pick_id}: {e}")
            return None


# Global service instance
draft_pick_service = DraftPickService()
