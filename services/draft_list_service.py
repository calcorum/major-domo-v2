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

    API QUIRK: GET endpoint returns items under 'picks' key, not 'draftlist'.
    POST endpoint expects items under 'draft_list' key.

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

    def _extract_items_and_count_from_response(self, data):
        """
        Override to handle API quirk: GET returns 'picks' instead of 'draftlist'.

        Args:
            data: API response data

        Returns:
            Tuple of (items list, total count)
        """
        from typing import Any, Dict, List, Tuple

        if isinstance(data, list):
            return data, len(data)

        if not isinstance(data, dict):
            logger.warning(f"Unexpected response format: {type(data)}")
            return [], 0

        # Get count
        count = data.get('count', 0)

        # API returns items under 'picks' key (not 'draftlist')
        if 'picks' in data and isinstance(data['picks'], list):
            return data['picks'], count or len(data['picks'])

        # Fallback to standard extraction
        return super()._extract_items_and_count_from_response(data)

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
    ) -> Optional[List[DraftList]]:
        """
        Add player to team's draft list.

        If rank is not provided, adds to end of list.

        NOTE: The API uses bulk replacement - we get the full list, add the new entry,
        and POST the entire updated list back.

        Args:
            season: Draft season
            team_id: Team ID
            player_id: Player ID to add
            rank: Priority rank (1 = highest), None = add to end

        Returns:
            Full updated draft list or None if operation failed
        """
        try:
            # Get current list
            current_list = await self.get_team_list(season, team_id)

            # If rank not provided, add to end
            if rank is None:
                rank = len(current_list) + 1

            # Create new entry data
            new_entry_data = {
                'season': season,
                'team_id': team_id,
                'player_id': player_id,
                'rank': rank
            }

            # Build complete list for bulk replacement
            draft_list_entries = []

            # Add existing entries, adjusting ranks if inserting in middle
            for entry in current_list:
                if entry.rank >= rank:
                    # Shift down entries at or after insertion point
                    draft_list_entries.append({
                        'season': entry.season,
                        'team_id': entry.team_id,
                        'player_id': entry.player_id,
                        'rank': entry.rank + 1
                    })
                else:
                    # Keep existing rank for entries before insertion point
                    draft_list_entries.append({
                        'season': entry.season,
                        'team_id': entry.team_id,
                        'player_id': entry.player_id,
                        'rank': entry.rank
                    })

            # Add new entry
            draft_list_entries.append(new_entry_data)

            # Sort by rank for consistency
            draft_list_entries.sort(key=lambda x: x['rank'])

            # POST entire list (bulk replacement)
            client = await self.get_client()
            payload = {
                'count': len(draft_list_entries),
                'draft_list': draft_list_entries
            }

            logger.debug(f"Posting draft list for team {team_id}: {len(draft_list_entries)} entries")
            response = await client.post(self.endpoint, payload)
            logger.debug(f"POST response: {response}")

            # Verify by fetching the list back (API returns full objects)
            verification = await self.get_team_list(season, team_id)
            logger.debug(f"Verification: found {len(verification)} entries after POST")

            # Verify the player was added
            if not any(entry.player_id == player_id for entry in verification):
                logger.error(f"Player {player_id} not found in list after POST - operation may have failed")
                return None

            logger.info(f"Added player {player_id} to team {team_id} draft list at rank {rank}")
            return verification  # Return full updated list

        except Exception as e:
            logger.error(f"Error adding player {player_id} to draft list: {e}")
            return None

    async def remove_from_list(
        self,
        entry_id: int
    ) -> bool:
        """
        Remove entry from draft list by ID.

        NOTE: No DELETE endpoint exists. This method is deprecated - use remove_player_from_list() instead.

        Args:
            entry_id: Draft list entry database ID

        Returns:
            True if deletion succeeded
        """
        logger.warning("remove_from_list() called with entry_id - use remove_player_from_list() instead")
        return False

    async def remove_player_from_list(
        self,
        season: int,
        team_id: int,
        player_id: int
    ) -> bool:
        """
        Remove specific player from team's draft list.

        Uses bulk replacement pattern - gets full list, removes player, POSTs updated list.

        Args:
            season: Draft season
            team_id: Team ID
            player_id: Player ID to remove

        Returns:
            True if player was found and removed
        """
        try:
            # Get team's list
            current_list = await self.get_team_list(season, team_id)

            # Check if player is in list
            player_found = any(entry.player_id == player_id for entry in current_list)
            if not player_found:
                logger.warning(f"Player {player_id} not found in team {team_id} draft list")
                return False

            # Build new list without the player, adjusting ranks
            draft_list_entries = []
            new_rank = 1
            for entry in current_list:
                if entry.player_id != player_id:
                    draft_list_entries.append({
                        'season': entry.season,
                        'team_id': entry.team_id,
                        'player_id': entry.player_id,
                        'rank': new_rank
                    })
                    new_rank += 1

            # POST updated list (bulk replacement)
            client = await self.get_client()
            payload = {
                'count': len(draft_list_entries),
                'draft_list': draft_list_entries
            }

            await client.post(self.endpoint, payload)
            logger.info(f"Removed player {player_id} from team {team_id} draft list")

            return True

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

        Uses DELETE /draftlist/team/{team_id} endpoint.

        Args:
            season: Draft season
            team_id: Team ID

        Returns:
            True if list was cleared successfully
        """
        try:
            # Check if list is already empty
            entries = await self.get_team_list(season, team_id)
            if not entries:
                logger.debug(f"No draft list entries to clear for team {team_id}")
                return True

            entry_count = len(entries)

            # Use DELETE endpoint: /draftlist/team/{team_id}
            client = await self.get_client()
            await client.delete(f"{self.endpoint}/team/{team_id}")

            logger.info(f"Cleared {entry_count} draft list entries for team {team_id}")

            return True

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

        Uses bulk replacement pattern - builds new list with updated ranks and POSTs it.

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

            # Build new list in specified order
            draft_list_entries = []
            for new_rank, player_id in enumerate(new_order, start=1):
                if player_id not in entry_map:
                    logger.warning(f"Player {player_id} not in draft list, skipping")
                    continue

                entry = entry_map[player_id]
                draft_list_entries.append({
                    'season': entry.season,
                    'team_id': entry.team_id,
                    'player_id': entry.player_id,
                    'rank': new_rank
                })

            # POST reordered list (bulk replacement)
            client = await self.get_client()
            payload = {
                'count': len(draft_list_entries),
                'draft_list': draft_list_entries
            }

            await client.post(self.endpoint, payload)
            logger.info(f"Reordered draft list for team {team_id}")

            return True

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

        Uses bulk replacement pattern - swaps ranks and POSTs updated list.

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

            # Find entry above (rank - 1)
            above_entry = next((e for e in entries if e.rank == current_entry.rank - 1), None)
            if not above_entry:
                logger.error(f"Could not find entry above rank {current_entry.rank}")
                return False

            # Build new list with swapped ranks
            draft_list_entries = []
            for entry in entries:
                if entry.player_id == current_entry.player_id:
                    # Move this player up
                    new_rank = current_entry.rank - 1
                elif entry.player_id == above_entry.player_id:
                    # Move above player down
                    new_rank = above_entry.rank + 1
                else:
                    # Keep existing rank
                    new_rank = entry.rank

                draft_list_entries.append({
                    'season': entry.season,
                    'team_id': entry.team_id,
                    'player_id': entry.player_id,
                    'rank': new_rank
                })

            # Sort by rank
            draft_list_entries.sort(key=lambda x: x['rank'])

            # POST updated list (bulk replacement)
            client = await self.get_client()
            payload = {
                'count': len(draft_list_entries),
                'draft_list': draft_list_entries
            }

            await client.post(self.endpoint, payload)
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

        Uses bulk replacement pattern - swaps ranks and POSTs updated list.

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

            # Find entry below (rank + 1)
            below_entry = next((e for e in entries if e.rank == current_entry.rank + 1), None)
            if not below_entry:
                logger.error(f"Could not find entry below rank {current_entry.rank}")
                return False

            # Build new list with swapped ranks
            draft_list_entries = []
            for entry in entries:
                if entry.player_id == current_entry.player_id:
                    # Move this player down
                    new_rank = current_entry.rank + 1
                elif entry.player_id == below_entry.player_id:
                    # Move below player up
                    new_rank = below_entry.rank - 1
                else:
                    # Keep existing rank
                    new_rank = entry.rank

                draft_list_entries.append({
                    'season': entry.season,
                    'team_id': entry.team_id,
                    'player_id': entry.player_id,
                    'rank': new_rank
                })

            # Sort by rank
            draft_list_entries.sort(key=lambda x: x['rank'])

            # POST updated list (bulk replacement)
            client = await self.get_client()
            payload = {
                'count': len(draft_list_entries),
                'draft_list': draft_list_entries
            }

            await client.post(self.endpoint, payload)
            logger.info(f"Moved player {player_id} down to rank {current_entry.rank + 1}")

            return True

        except Exception as e:
            logger.error(f"Error moving player {player_id} down in draft list: {e}")
            return False


# Global service instance
draft_list_service = DraftListService()
