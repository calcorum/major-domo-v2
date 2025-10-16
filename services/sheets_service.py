"""
Google Sheets Service

Handles reading data from Google Sheets scorecards for game submission.
"""
import asyncio
from typing import Dict, List, Any, Optional
import pygsheets

from utils.logging import get_contextual_logger
from exceptions import SheetsException


class SheetsService:
    """Google Sheets integration for scorecard reading."""

    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize sheets service.

        Args:
            credentials_path: Path to service account credentials JSON
                             If None, will use path from config
        """
        if credentials_path is None:
            from config import get_config
            credentials_path = get_config().sheets_credentials_path

        self.credentials_path = credentials_path
        self.logger = get_contextual_logger(f'{__name__}.SheetsService')
        self._sheets_client = None

    def _get_client(self) -> pygsheets.client.Client:
        """Get or create pygsheets client."""
        if self._sheets_client is None:
            self._sheets_client = pygsheets.authorize(
                service_file=self.credentials_path
            )
        return self._sheets_client

    async def open_scorecard(self, sheet_url: str) -> pygsheets.Spreadsheet:
        """
        Open and validate access to a Google Sheet.

        Args:
            sheet_url: Full URL to Google Sheet

        Returns:
            Opened spreadsheet object

        Raises:
            SheetsException: If sheet cannot be accessed
        """
        try:
            # Run in thread pool since pygsheets is synchronous
            loop = asyncio.get_event_loop()
            sheets = await loop.run_in_executor(
                None,
                self._get_client
            )
            scorecard = await loop.run_in_executor(
                None,
                sheets.open_by_url,
                sheet_url
            )

            self.logger.info(f"Opened scorecard: {scorecard.title}")
            return scorecard

        except Exception as e:
            self.logger.error(f"Failed to open scorecard {sheet_url}: {e}")
            raise SheetsException(
                "Unable to access scorecard. Is it publicly readable?"
            ) from e

    async def read_setup_data(
        self,
        scorecard: pygsheets.Spreadsheet
    ) -> Dict[str, Any]:
        """
        Read game metadata from Setup tab.

        Cell mappings:
        - V35: Scorecard version
        - C3:D7: Game data (week, game_num, teams, managers)

        Returns:
            Dictionary with keys:
            - version: str
            - week: int
            - game_num: int
            - away_team_abbrev: str
            - home_team_abbrev: str
            - away_manager_name: str
            - home_manager_name: str
        """
        try:
            loop = asyncio.get_event_loop()

            # Get Setup tab
            setup_tab = await loop.run_in_executor(
                None,
                scorecard.worksheet_by_title,
                'Setup'
            )

            # Read version
            version = await loop.run_in_executor(
                None,
                setup_tab.get_value,
                'V35'
            )

            # Read game data (C3:D7)
            g_data = await loop.run_in_executor(
                None,
                setup_tab.get_values,
                'C3',
                'D7'
            )

            return {
                'version': version,
                'week': int(g_data[1][0]),
                'game_num': int(g_data[2][0]),
                'away_team_abbrev': g_data[3][0],
                'home_team_abbrev': g_data[4][0],
                'away_manager_name': g_data[3][1],
                'home_manager_name': g_data[4][1]
            }

        except Exception as e:
            self.logger.error(f"Failed to read setup data: {e}")
            raise SheetsException("Unable to read game setup data") from e

    async def read_playtable_data(
        self,
        scorecard: pygsheets.Spreadsheet
    ) -> List[Dict[str, Any]]:
        """
        Read all plays from Playtable tab.

        Reads range B3:BW300 which contains up to 297 rows of play data
        with 68 columns per row.

        Returns:
            List of play dictionaries with field names mapped
        """
        try:
            loop = asyncio.get_event_loop()

            # Get Playtable tab
            playtable = await loop.run_in_executor(
                None,
                scorecard.worksheet_by_title,
                'Playtable'
            )

            # Read play data
            all_plays = await loop.run_in_executor(
                None,
                playtable.get_values,
                'B3',
                'BW300'
            )

            # Field names in order (from old bot lines 1621-1632)
            play_keys = [
                'play_num', 'batter_id', 'batter_pos', 'pitcher_id',
                'on_base_code', 'inning_half', 'inning_num', 'batting_order',
                'starting_outs', 'away_score', 'home_score', 'on_first_id',
                'on_first_final', 'on_second_id', 'on_second_final',
                'on_third_id', 'on_third_final', 'batter_final', 'pa', 'ab',
                'run', 'e_run', 'hit', 'rbi', 'double', 'triple', 'homerun',
                'bb', 'so', 'hbp', 'sac', 'ibb', 'gidp', 'bphr', 'bpfo',
                'bp1b', 'bplo', 'sb', 'cs', 'outs', 'pitcher_rest_outs',
                'wpa', 'catcher_id', 'defender_id', 'runner_id', 'check_pos',
                'error', 'wild_pitch', 'passed_ball', 'pick_off', 'balk',
                'is_go_ahead', 'is_tied', 'is_new_inning', 'inherited_runners',
                'inherited_scored', 'on_hook_for_loss', 'run_differential',
                'unused-manager', 'unused-pitcherpow', 'unused-pitcherrestip',
                'unused-runners', 'unused-fatigue', 'unused-roundedip',
                'unused-elitestart', 'unused-scenario', 'unused-winxaway',
                'unused-winxhome', 'unused-pinchrunner', 'unused-order',
                'hand_batting', 'hand_pitching', 're24_primary', 're24_running'
            ]

            p_data = []
            for line in all_plays:
                this_data = {}
                for count, value in enumerate(line):
                    if value != '' and count < len(play_keys):
                        this_data[play_keys[count]] = value

                # Only include rows with meaningful data (>5 fields)
                if len(this_data.keys()) > 5:
                    p_data.append(this_data)

            self.logger.info(f"Read {len(p_data)} plays from scorecard")
            return p_data

        except Exception as e:
            self.logger.error(f"Failed to read playtable data: {e}")
            raise SheetsException("Unable to read play-by-play data") from e

    async def read_pitching_decisions(
        self,
        scorecard: pygsheets.Spreadsheet
    ) -> List[Dict[str, Any]]:
        """
        Read pitching decisions from Pitcherstats tab.

        Reads range B3:O30 which contains up to 27 rows of pitcher data
        with 14 columns per row.

        Returns:
            List of decision dictionaries with field names mapped
        """
        try:
            loop = asyncio.get_event_loop()

            # Get Pitcherstats tab
            pitching = await loop.run_in_executor(
                None,
                scorecard.worksheet_by_title,
                'Pitcherstats'
            )

            # Read decision data
            all_decisions = await loop.run_in_executor(
                None,
                pitching.get_values,
                'B3',
                'O30'
            )

            # Field names in order (from old bot lines 1688-1691)
            pit_keys = [
                'pitcher_id', 'rest_ip', 'is_start', 'base_rest',
                'extra_rest', 'rest_required', 'win', 'loss', 'is_save',
                'hold', 'b_save', 'irunners', 'irunners_scored', 'team_id'
            ]

            pit_data = []
            for line in all_decisions:
                if not line:  # Skip empty rows
                    continue

                this_data = {}
                for count, value in enumerate(line):
                    if value != '' and count < len(pit_keys):
                        this_data[pit_keys[count]] = value

                if this_data:  # Only include non-empty rows
                    pit_data.append(this_data)

            self.logger.info(f"Read {len(pit_data)} pitching decisions")
            return pit_data

        except Exception as e:
            self.logger.error(f"Failed to read pitching decisions: {e}")
            raise SheetsException("Unable to read pitching decisions") from e

    async def read_box_score(
        self,
        scorecard: pygsheets.Spreadsheet
    ) -> Dict[str, List[int]]:
        """
        Read box score from Scorecard or Box Score tab.

        Tries 'Scorecard' tab first (BW8:BY9), falls back to
        'Box Score' tab (T6:V7).

        Returns:
            Dictionary with 'away' and 'home' keys, each containing
            [runs, hits, errors]
        """
        try:
            loop = asyncio.get_event_loop()

            # Try Scorecard tab first
            try:
                sc_tab = await loop.run_in_executor(
                    None,
                    scorecard.worksheet_by_title,
                    'Scorecard'
                )
                score_table = await loop.run_in_executor(
                    None,
                    sc_tab.get_values,
                    'BW8',
                    'BY9'
                )
            except pygsheets.WorksheetNotFound:
                # Fallback to Box Score tab
                sc_tab = await loop.run_in_executor(
                    None,
                    scorecard.worksheet_by_title,
                    'Box Score'
                )
                score_table = await loop.run_in_executor(
                    None,
                    sc_tab.get_values,
                    'T6',
                    'V7'
                )

            return {
                'away': [int(x) for x in score_table[0]],  # [R, H, E]
                'home': [int(x) for x in score_table[1]]   # [R, H, E]
            }

        except Exception as e:
            self.logger.error(f"Failed to read box score: {e}")
            raise SheetsException("Unable to read box score") from e
