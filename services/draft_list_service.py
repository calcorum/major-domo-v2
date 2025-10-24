"""
Draft list service for Discord Bot v2.0

Handles team draft list (auto-draft queue) operations. NO CACHING - lists change frequently.
"""
import logging
from typing import Optional, List

from services.base_service import BaseService
from models.draft_list import DraftList
from exceptions import APIException

logger = logging.getLogger(f'{__name__}.DraftListService')


class DraftListService(BaseService[DraftList]):
    """
    Service for draft list operations.

    IMPORTANT: This service does NOT use caching decorators because draft lists
    change as users add/remove players from their auto-draft queues.

    Features:
    - Get team's draft list (ranked by priority)
    - Add player to draft list
    - Remove player from draft list
    - Reorder draft list
    - Clear entire draft list
    """

    def __init__(self):
        """Initialize draft list service."""
        super().__init__(DraftList, 'draftlist')
        logger.debug("DraftListService initialized")

    async def get_team_list(
        self,
        season: int,
        team_id: int
    ) -> List[DraftList]:
        """
        Get team's draft list ordered by rank.

        NOT cached - teams update their lists frequently during draft.

        Args:
            season: Draft season
            team_id: Team ID

        Returns:
            List of DraftList entries ordered by rank (1 = highest priority)
        """
        try:
            params = [
                ('season', str(season)),
                ('team_id', str(team_id)),
                ('sort', 'rank-asc')  # Order by priority
            ]

            entries = await self.get_all_items(params=params)
            logger.debug(f"Found {len(entries)} draft list entries for team {team_id}")
            return entries

        except Exception as e:
            logger.error(f"Error getting draft list for team {team_id}: {e}")
            return []

    async def add_to_list(
        self,
        season: int,
        team_id: int,
        player_id: int,
        rank: Optional[int] = None
    ) -> Optional[DraftList]:
        """
        Add player to team's draft list.

        If rank is not provided, adds to end of list.

        Args:
            season: Draft season
            team_id: Team ID
            player_id: Player ID to add
            rank: Priority rank (1 = highest), None = add to end

        Returns:
            Created DraftList entry or None if creation failed
        """
        try:
            # If rank not provided, get current list and add to end
            if rank is None:
                current_list = await self.get_team_list(season, team_id)
                rank = len(current_list) + 1

            entry_data = {
                'season': season,
                'team_id': team_id,
                'player_id': player_id,
                'rank': rank
            }

            created_entry = await self.create(entry_data)

            if created_entry:
                logger.info(f"Added player {player_id} to team {team_id} draft list at rank {rank}")
            else:
                logger.error(f"Failed to add player {player_id} to draft list")

            return created_entry

        except Exception as e:
            logger.error(f"Error adding player {player_id} to draft list: {e}")
            return None

    async def remove_from_list(
        self,
        entry_id: int
    ) -> bool:
        """
        Remove entry from draft list by ID.

        Args:
            entry_id: Draft list entry database ID

        Returns:
            True if deletion succeeded
        """
        try:
            result = await self.delete(entry_id)

            if result:
                logger.info(f"Removed draft list entry {entry_id}")
            else:
                logger.error(f"Failed to remove draft list entry {entry_id}")

            return result

        except Exception as e:
            logger.error(f"Error removing draft list entry {entry_id}: {e}")
            return False

    async def remove_player_from_list(
        self,
        season: int,
        team_id: int,
        player_id: int
    ) -> bool:
        """
        Remove specific player from team's draft list.

        Args:
            season: Draft season
            team_id: Team ID
            player_id: Player ID to remove

        Returns:
            True if player was found and removed
        """
        try:
            # Get team's list
            entries = await self.get_team_list(season, team_id)

            # Find entry with this player
            for entry in entries:
                if entry.player_id == player_id:
                    return await self.remove_from_list(entry.id)

            logger.warning(f"Player {player_id} not found in team {team_id} draft list")
            return False

        except Exception as e:
            logger.error(f"Error removing player {player_id} from draft list: {e}")
            return False

    async def clear_list(
        self,
        season: int,
        team_id: int
    ) -> bool:
        """
        Clear entire draft list for team.

        Args:
            season: Draft season
            team_id: Team ID

        Returns:
            True if all entries were deleted successfully
        """
        try:
            entries = await self.get_team_list(season, team_id)

            if not entries:
                logger.debug(f"No draft list entries to clear for team {team_id}")
                return True

            success = True
            for entry in entries:
                if not await self.remove_from_list(entry.id):
                    success = False

            if success:
                logger.info(f"Cleared {len(entries)} draft list entries for team {team_id}")
            else:
                logger.warning(f"Failed to clear some draft list entries for team {team_id}")

            return success

        except Exception as e:
            logger.error(f"Error clearing draft list for team {team_id}: {e}")
            return False

    async def reorder_list(
        self,
        season: int,
        team_id: int,
        new_order: List[int]
    ) -> bool:
        """
        Reorder team's draft list.

        Args:
            season: Draft season
            team_id: Team ID
            new_order: List of player IDs in desired order

        Returns:
            True if reordering succeeded
        """
        try:
            # Get current list
            entries = await self.get_team_list(season, team_id)

            # Build mapping of player_id -> entry
            entry_map = {e.player_id: e for e in entries}

            # Update each entry with new rank
            success = True
            for new_rank, player_id in enumerate(new_order, start=1):
                if player_id not in entry_map:
                    logger.warning(f"Player {player_id} not in draft list, skipping")
                    continue

                entry = entry_map[player_id]
                if entry.rank != new_rank:
                    updated = await self.patch(entry.id, {'rank': new_rank})
                    if not updated:
                        logger.error(f"Failed to update rank for entry {entry.id}")
                        success = False

            if success:
                logger.info(f"Reordered draft list for team {team_id}")
            else:
                logger.warning(f"Some errors occurred reordering draft list for team {team_id}")

            return success

        except Exception as e:
            logger.error(f"Error reordering draft list for team {team_id}: {e}")
            return False

    async def move_entry_up(
        self,
        season: int,
        team_id: int,
        player_id: int
    ) -> bool:
        """
        Move player up one position in draft list (higher priority).

        Args:
            season: Draft season
            team_id: Team ID
            player_id: Player ID to move up

        Returns:
            True if move succeeded
        """
        try:
            entries = await self.get_team_list(season, team_id)

            # Find player's current position
            current_entry = None
            for entry in entries:
                if entry.player_id == player_id:
                    current_entry = entry
                    break

            if not current_entry:
                logger.warning(f"Player {player_id} not found in draft list")
                return False

            if current_entry.rank == 1:
                logger.debug(f"Player {player_id} already at top of draft list")
                return False

            # Swap with entry above (rank - 1)
            above_entry = next((e for e in entries if e.rank == current_entry.rank - 1), None)
            if not above_entry:
                logger.error(f"Could not find entry above rank {current_entry.rank}")
                return False

            # Swap ranks
            await self.patch(current_entry.id, {'rank': current_entry.rank - 1})
            await self.patch(above_entry.id, {'rank': above_entry.rank + 1})

            logger.info(f"Moved player {player_id} up to rank {current_entry.rank - 1}")
            return True

        except Exception as e:
            logger.error(f"Error moving player {player_id} up in draft list: {e}")
            return False

    async def move_entry_down(
        self,
        season: int,
        team_id: int,
        player_id: int
    ) -> bool:
        """
        Move player down one position in draft list (lower priority).

        Args:
            season: Draft season
            team_id: Team ID
            player_id: Player ID to move down

        Returns:
            True if move succeeded
        """
        try:
            entries = await self.get_team_list(season, team_id)

            # Find player's current position
            current_entry = None
            for entry in entries:
                if entry.player_id == player_id:
                    current_entry = entry
                    break

            if not current_entry:
                logger.warning(f"Player {player_id} not found in draft list")
                return False

            if current_entry.rank == len(entries):
                logger.debug(f"Player {player_id} already at bottom of draft list")
                return False

            # Swap with entry below (rank + 1)
            below_entry = next((e for e in entries if e.rank == current_entry.rank + 1), None)
            if not below_entry:
                logger.error(f"Could not find entry below rank {current_entry.rank}")
                return False

            # Swap ranks
            await self.patch(current_entry.id, {'rank': current_entry.rank + 1})
            await self.patch(below_entry.id, {'rank': below_entry.rank - 1})

            logger.info(f"Moved player {player_id} down to rank {current_entry.rank + 1}")
            return True

        except Exception as e:
            logger.error(f"Error moving player {player_id} down in draft list: {e}")
            return False


# Global service instance
draft_list_service = DraftListService()
