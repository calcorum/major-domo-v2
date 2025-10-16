"""
Game Service

Manages game CRUD operations and game-specific workflows for scorecard submission.
"""
from typing import Optional

from services.base_service import BaseService
from models.game import Game
from utils.logging import get_contextual_logger
from exceptions import APIException


class GameService(BaseService[Game]):
    """Game management service with specialized game operations."""

    def __init__(self):
        """Initialize game service."""
        super().__init__(Game, 'games')
        self.logger = get_contextual_logger(f'{__name__}.GameService')

    async def find_duplicate_game(
        self,
        season: int,
        week: int,
        game_num: int,
        away_team_id: int,
        home_team_id: int
    ) -> Optional[Game]:
        """
        Check for already-played duplicate game.

        Args:
            season: Season number
            week: Week number
            game_num: Game number in series
            away_team_id: Away team ID
            home_team_id: Home team ID

        Returns:
            Game if duplicate found (game_num is set), None otherwise
        """
        params = [
            ('season', str(season)),
            ('week', str(week)),
            ('game_num', str(game_num)),
            ('away_team_id', str(away_team_id)),
            ('home_team_id', str(home_team_id))
        ]

        games, count = await self.get_all(params=params)

        if count > 0:
            self.logger.warning(
                f"Found duplicate game: S{season} W{week} G{game_num} "
                f"({away_team_id} @ {home_team_id})"
            )
            return games[0]

        return None

    async def find_scheduled_game(
        self,
        season: int,
        week: int,
        away_team_id: int,
        home_team_id: int
    ) -> Optional[Game]:
        """
        Find unplayed scheduled game matching teams and week.

        Args:
            season: Season number
            week: Week number
            away_team_id: Away team ID
            home_team_id: Home team ID

        Returns:
            Game if found and not yet played (game_num is None), None otherwise
        """
        params = [
            ('season', str(season)),
            ('week', str(week)),
            ('away_team_id', str(away_team_id)),
            ('home_team_id', str(home_team_id)),
            ('played', 'false')  # Only unplayed games
        ]

        games, count = await self.get_all(params=params)

        if count == 0:
            self.logger.warning(
                f"No scheduled game found for S{season} W{week} "
                f"({away_team_id} @ {home_team_id})"
            )
            return None

        return games[0]

    async def wipe_game_data(self, game_id: int) -> bool:
        """
        Wipe game scores and manager assignments.

        Calls POST /games/wipe/{game_id} which sets:
        - away_score = None
        - home_score = None
        - game_num = None
        - away_manager = None
        - home_manager = None

        Args:
            game_id: Game ID to wipe

        Returns:
            True if successful

        Raises:
            APIException: If wipe fails
        """
        try:
            client = await self.get_client()
            response = await client.post(f'games/wipe/{game_id}', {})

            self.logger.info(f"Wiped game {game_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to wipe game {game_id}: {e}")
            raise APIException(f"Failed to wipe game data: {e}")

    async def update_game_result(
        self,
        game_id: int,
        away_score: int,
        home_score: int,
        away_manager_id: int,
        home_manager_id: int,
        game_num: int,
        scorecard_url: str
    ) -> Game:
        """
        Update game with scores, managers, and scorecard URL.

        Args:
            game_id: Game ID to update
            away_score: Away team final score
            home_score: Home team final score
            away_manager_id: Away team manager ID
            home_manager_id: Home team manager ID
            game_num: Game number in series
            scorecard_url: URL to scorecard

        Returns:
            Updated game object

        Raises:
            APIException: If update fails
        """
        update_data = {
            'away_score': away_score,
            'home_score': home_score,
            'away_manager_id': away_manager_id,
            'home_manager_id': home_manager_id,
            'game_num': game_num,
            'scorecard_url': scorecard_url
        }

        updated_game = await self.patch(
            game_id,
            update_data,
            use_query_params=True  # API expects query params for PATCH
        )

        if updated_game is None:
            raise APIException(f"Game {game_id} not found for update")

        self.logger.info(f"Updated game {game_id} with final score")
        return updated_game


# Global service instance
game_service = GameService()
