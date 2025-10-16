"""
Decision Service

Manages pitching decision operations for game submission.
"""
from typing import List, Dict, Any, Optional, Tuple

from utils.logging import get_contextual_logger
from api.client import get_global_client
from models.decision import Decision
from models.player import Player
from exceptions import APIException


class DecisionService:
    """Pitching decision management service."""

    def __init__(self):
        """Initialize decision service."""
        self.logger = get_contextual_logger(f'{__name__}.DecisionService')
        self._get_client = get_global_client

    async def get_client(self):
        """Get the API client."""
        return await self._get_client()

    async def create_decisions_batch(
        self,
        decisions: List[Dict[str, Any]]
    ) -> bool:
        """
        POST batch of decisions to /decisions endpoint.

        Args:
            decisions: List of decision dictionaries

        Returns:
            True if successful

        Raises:
            APIException: If POST fails
        """
        try:
            client = await self.get_client()

            payload = {'decisions': decisions}
            await client.post('decisions', payload)

            self.logger.info(f"Created {len(decisions)} decisions")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create decisions batch: {e}")
            error_msg = self._parse_api_error(e)
            raise APIException(error_msg) from e

    async def delete_decisions_for_game(self, game_id: int) -> bool:
        """
        Delete all decisions for a specific game.

        Calls DELETE /decisions/game/{game_id}

        Args:
            game_id: Game ID to delete decisions for

        Returns:
            True if successful

        Raises:
            APIException: If deletion fails
        """
        try:
            client = await self.get_client()
            await client.delete(f'decisions/game/{game_id}')

            self.logger.info(f"Deleted decisions for game {game_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete decisions for game {game_id}: {e}")
            raise APIException(f"Failed to delete decisions: {e}")

    async def find_winning_losing_pitchers(
        self,
        decisions_data: List[Dict[str, Any]]
    ) -> Tuple[Optional[Player], Optional[Player], Optional[Player], List[Player], List[Player]]:
        """
        Extract WP, LP, SV, Holds, Blown Saves from decisions list and fetch Player objects.

        Args:
            decisions_data: List of decision dictionaries from scorecard

        Returns:
            Tuple of (wp, lp, sv, holders, blown_saves)
            wp: Winning pitcher Player object (or None)
            lp: Losing pitcher Player object (or None)
            sv: Save pitcher Player object (or None)
            holders: List of Player objects with holds
            blown_saves: List of Player objects with blown saves

        Raises:
            APIException: If any player lookup fails
        """
        from services.player_service import player_service

        wp_id = None
        lp_id = None
        sv_id = None
        hold_ids = []
        bsv_ids = []

        # First pass: Extract IDs
        for decision in decisions_data:
            pitcher_id = int(decision.get('pitcher_id', 0))

            if int(decision.get('win', 0)) == 1:
                wp_id = pitcher_id
            if int(decision.get('loss', 0)) == 1:
                lp_id = pitcher_id
            if int(decision.get('is_save', 0)) == 1:
                sv_id = pitcher_id
            if int(decision.get('hold', 0)) == 1:
                hold_ids.append(pitcher_id)
            if int(decision.get('b_save', 0)) == 1:
                bsv_ids.append(pitcher_id)

        # Second pass: Fetch Player objects
        wp = await player_service.get_player(wp_id) if wp_id else None
        lp = await player_service.get_player(lp_id) if lp_id else None
        sv = await player_service.get_player(sv_id) if sv_id else None

        holders = []
        for hold_id in hold_ids:
            holder = await player_service.get_player(hold_id)
            if holder:
                holders.append(holder)

        blown_saves = []
        for bsv_id in bsv_ids:
            bsv = await player_service.get_player(bsv_id)
            if bsv:
                blown_saves.append(bsv)

        return wp, lp, sv, holders, blown_saves

    def _parse_api_error(self, error: Exception) -> str:
        """
        Parse API error into user-friendly message.

        Args:
            error: Exception from API call

        Returns:
            User-friendly error message
        """
        error_str = str(error)

        if 'Player ID' in error_str and 'not found' in error_str:
            return "Invalid pitcher ID in decision data."
        elif 'Game ID' in error_str and 'not found' in error_str:
            return "Game not found for decisions."
        else:
            return f"Error submitting decisions: {error_str}"


# Global service instance
decision_service = DecisionService()
