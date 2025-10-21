"""
Scorebug Service

Handles reading live game data from Google Sheets scorecards for real-time score displays.
"""
import asyncio
from typing import Dict, List, Any, Optional
import pygsheets

from utils.logging import get_contextual_logger
from exceptions import SheetsException
from services.sheets_service import SheetsService


class ScorebugData:
    """Data class for scorebug information."""

    def __init__(self, data: Dict[str, Any]):
        self.away_team_id = data.get('away_team_id', 1)
        self.home_team_id = data.get('home_team_id', 1)
        self.header = data.get('header', '')
        self.away_score = data.get('away_score', 0)
        self.home_score = data.get('home_score', 0)
        self.which_half = data.get('which_half', '')
        self.is_final = data.get('is_final', False)
        self.runners = data.get('runners', [])
        self.matchups = data.get('matchups', [])
        self.summary = data.get('summary', [])

    @property
    def score_line(self) -> str:
        """Get formatted score line for display."""
        return f"{self.away_score} @ {self.home_score}"

    @property
    def is_active(self) -> bool:
        """Check if game is currently active (not final)."""
        return not self.is_final


class ScorebugService(SheetsService):
    """Google Sheets integration for reading live scorebug data."""

    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize scorebug service.

        Args:
            credentials_path: Path to service account credentials JSON
        """
        super().__init__(credentials_path)
        self.logger = get_contextual_logger(f'{__name__}.ScorebugService')

    async def read_scorebug_data(
        self,
        sheet_url_or_key: str,
        full_length: bool = True
    ) -> ScorebugData:
        """
        Read live scorebug data from Google Sheets scorecard.

        Args:
            sheet_url_or_key: Full URL or Google Sheets key
            full_length: If True, includes summary data; if False, compact view

        Returns:
            ScorebugData object with game state

        Raises:
            SheetsException: If scorecard cannot be read
        """
        try:
            # Open scorecard
            scorecard = await self.open_scorecard(sheet_url_or_key)

            loop = asyncio.get_event_loop()

            # Get Scorebug tab
            scorebug_tab = await loop.run_in_executor(
                None,
                scorecard.worksheet_by_title,
                'Scorebug'
            )

            # Read all data from B2:S20 for efficiency
            all_data = await loop.run_in_executor(
                None,
                lambda: scorebug_tab.get_values('B2', 'S20', include_tailing_empty_rows=True)
            )

            self.logger.debug(f"Raw scorebug data (first 10 rows): {all_data[:10]}")

            # Extract game state (B2:G8)
            game_state = [
                all_data[0][:6], all_data[1][:6], all_data[2][:6], all_data[3][:6],
                all_data[4][:6], all_data[5][:6], all_data[6][:6]
            ]

            self.logger.debug(f"Extracted game_state: {game_state}")

            # Extract team IDs from game_state (already read from Scorebug tab)
            # game_state[3] is away team row, game_state[4] is home team row
            # First column (index 0) contains the team ID
            try:
                away_team_id = int(game_state[3][0]) if len(game_state) > 3 and len(game_state[3]) > 0 else None
                home_team_id = int(game_state[4][0]) if len(game_state) > 4 and len(game_state[4]) > 0 else None

                self.logger.debug(f"Parsed team IDs - Away: {away_team_id}, Home: {home_team_id}")

                if away_team_id is None or home_team_id is None:
                    raise ValueError(f'Team IDs not found in scorebug (away: {away_team_id}, home: {home_team_id})')
            except (ValueError, IndexError) as e:
                self.logger.error(f"Failed to parse team IDs from scorebug: {e}")
                raise ValueError(f'Could not extract team IDs from scorecard')

            # Parse game state
            header = game_state[0][0] if game_state[0] else ''
            is_final = header[-5:] == 'FINAL' if header else False

            self.logger.debug(f"Header: '{header}', Is Final: {is_final}")
            self.logger.debug(f"Away team row (game_state[3]): {game_state[3] if len(game_state) > 3 else 'N/A'}")
            self.logger.debug(f"Home team row (game_state[4]): {game_state[4] if len(game_state) > 4 else 'N/A'}")

            # Parse scores with validation
            try:
                away_score_raw = game_state[3][2] if len(game_state) > 3 and len(game_state[3]) > 2 else '0'
                self.logger.debug(f"Raw away score value: '{away_score_raw}'")
                away_score = int(away_score_raw)
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Failed to parse away score: {e}")
                away_score = 0

            try:
                home_score_raw = game_state[4][2] if len(game_state) > 4 and len(game_state[4]) > 2 else '0'
                self.logger.debug(f"Raw home score value: '{home_score_raw}'")
                home_score = int(home_score_raw)
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Failed to parse home score: {e}")
                home_score = 0

            which_half = game_state[3][4] if len(game_state) > 3 and len(game_state[3]) > 4 else ''

            self.logger.debug(f"Parsed values - Away: {away_score}, Home: {home_score}, Which Half: '{which_half}'")

            # Extract runners (K11:L14 → offset in all_data)
            runners = [
                all_data[9][9:11] if len(all_data) > 9 else [],
                all_data[10][9:11] if len(all_data) > 10 else [],
                all_data[11][9:11] if len(all_data) > 11 else [],
                all_data[12][9:11] if len(all_data) > 12 else []
            ]

            # Extract matchups if full_length (M11:N14 → offset in all_data)
            matchups = []
            if full_length:
                matchups = [
                    all_data[9][11:13] if len(all_data) > 9 else [],
                    all_data[10][11:13] if len(all_data) > 10 else [],
                    all_data[11][11:13] if len(all_data) > 11 else [],
                    all_data[12][11:13] if len(all_data) > 12 else []
                ]

            # Extract summary if full_length (Q11:R14 → offset in all_data)
            summary = []
            if full_length:
                summary = [
                    all_data[9][15:17] if len(all_data) > 9 else [],
                    all_data[10][15:17] if len(all_data) > 10 else [],
                    all_data[11][15:17] if len(all_data) > 11 else [],
                    all_data[12][15:17] if len(all_data) > 12 else []
                ]

            return ScorebugData({
                'away_team_id': away_team_id,
                'home_team_id': home_team_id,
                'header': header,
                'away_score': away_score,
                'home_score': home_score,
                'which_half': which_half,
                'is_final': is_final,
                'runners': runners,
                'matchups': matchups,
                'summary': summary
            })

        except pygsheets.WorksheetNotFound:
            self.logger.error(f"Scorebug tab not found in scorecard")
            raise SheetsException("Scorebug tab not found. Is this a valid scorecard?")
        except Exception as e:
            self.logger.error(f"Failed to read scorebug data: {e}")
            raise SheetsException(f"Unable to read scorebug data: {str(e)}")
