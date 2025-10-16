"""
Play Service

Manages play-by-play data operations for game submission.
"""
from typing import List, Dict, Any

from utils.logging import get_contextual_logger
from api.client import get_global_client
from models.play import Play
from exceptions import APIException


class PlayService:
    """Play-by-play data management service."""

    def __init__(self):
        """Initialize play service."""
        self.logger = get_contextual_logger(f'{__name__}.PlayService')
        self._get_client = get_global_client

    async def get_client(self):
        """Get the API client."""
        return await self._get_client()

    async def create_plays_batch(self, plays: List[Dict[str, Any]]) -> bool:
        """
        POST batch of plays to /plays endpoint.

        Args:
            plays: List of play dictionaries with game_id and play data

        Returns:
            True if successful

        Raises:
            APIException: If POST fails with validation errors
        """
        try:
            client = await self.get_client()

            payload = {'plays': plays}
            response = await client.post('plays', payload)

            self.logger.info(f"Created {len(plays)} plays")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create plays batch: {e}")
            # Parse API error for user-friendly message
            error_msg = self._parse_api_error(e)
            raise APIException(error_msg) from e

    async def delete_plays_for_game(self, game_id: int) -> bool:
        """
        Delete all plays for a specific game.

        Calls DELETE /plays/game/{game_id}

        Args:
            game_id: Game ID to delete plays for

        Returns:
            True if successful

        Raises:
            APIException: If deletion fails
        """
        try:
            client = await self.get_client()
            response = await client.delete(f'plays/game/{game_id}')

            self.logger.info(f"Deleted plays for game {game_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete plays for game {game_id}: {e}")
            raise APIException(f"Failed to delete plays: {e}")

    async def get_top_plays_by_wpa(
        self,
        game_id: int,
        limit: int = 3
    ) -> List[Play]:
        """
        Get top plays by WPA (absolute value) for key plays display.

        Args:
            game_id: Game ID to get plays for
            limit: Number of plays to return (default 3)

        Returns:
            List of Play objects sorted by |WPA| descending
        """
        try:
            client = await self.get_client()

            params = [
                ('game_id', game_id),
                ('sort', 'wpa-desc'),
                ('limit', limit)
            ]

            response = await client.get('plays', params=params)

            if not response or 'plays' not in response:
                self.logger.info(f'No plays found for game ID {game_id}')
                return []

            plays = [Play.from_api_data(p) for p in response['plays']]

            self.logger.debug(f"Retrieved {len(plays)} top plays for game {game_id}")
            return plays

        except Exception as e:
            self.logger.error(f"Failed to get top plays: {e}")
            return []  # Non-critical, return empty list

    def _parse_api_error(self, error: Exception) -> str:
        """
        Parse API error into user-friendly message.

        Args:
            error: Exception from API call

        Returns:
            User-friendly error message
        """
        error_str = str(error)

        # Common error patterns
        if 'Player ID' in error_str and 'not found' in error_str:
            return "Invalid player ID in scorecard data. Please check player IDs."
        elif 'Game ID' in error_str and 'not found' in error_str:
            return "Game not found in database. Please contact an admin."
        elif 'validation' in error_str.lower():
            return f"Data validation error: {error_str}"
        else:
            return f"Error submitting plays: {error_str}"


# Global service instance
play_service = PlayService()
