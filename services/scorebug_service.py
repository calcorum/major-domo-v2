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
        self.inning = data.get('inning', 1)
        self.is_final = data.get('is_final', False)
        self.outs = data.get('outs', 0)
        self.win_percentage = data.get('win_percentage', 50.0)

        # Current matchup information
        self.pitcher_name = data.get('pitcher_name', '')
        self.pitcher_url = data.get('pitcher_url', '')
        self.pitcher_stats = data.get('pitcher_stats', '')
        self.batter_name = data.get('batter_name', '')
        self.batter_url = data.get('batter_url', '')
        self.batter_stats = data.get('batter_stats', '')
        self.on_deck_name = data.get('on_deck_name', '')
        self.in_hole_name = data.get('in_hole_name', '')

        # Additional data
        self.runners = data.get('runners', [])  # [Catcher, On First, On Second, On Third]
        self.summary = data.get('summary', [])  # Play-by-play summary lines

    @property
    def score_line(self) -> str:
        """Get formatted score line for display."""
        return f"{self.away_score} @ {self.home_score}"

    @property
    def is_active(self) -> bool:
        """Check if game is currently active (not final)."""
        return not self.is_final

    @property
    def current_matchup(self) -> str:
        """Get formatted current matchup string."""
        if self.batter_name and self.pitcher_name:
            return f"{self.batter_name} vs {self.pitcher_name}"
        return ""

    @property
    def situation(self) -> str:
        """Get game situation (outs and runners)."""
        parts = []
        if self.outs is not None:
            outs_text = "out" if self.outs == 1 else "outs"
            parts.append(f"{self.outs} {outs_text}")
        return ", ".join(parts) if parts else ""


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
        self.logger.info(f"📖 Reading scorebug data from sheet: {sheet_url_or_key}")
        self.logger.debug(f"   Full length mode: {full_length}")

        try:
            # Open scorecard
            scorecard = await self.open_scorecard(sheet_url_or_key)
            self.logger.debug(f"   ✅ Scorecard opened successfully")

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

            self.logger.debug(f"📊 Raw scorebug data dimensions: {len(all_data)} rows")
            self.logger.debug(f"📊 First row length: {len(all_data[0]) if all_data else 0} columns")
            self.logger.debug(f"📊 Reading from range B2:S20 (columns B-S = indices 0-17 in data)")
            self.logger.debug(f"📊 Raw data structure (all rows):")
            for idx, row in enumerate(all_data):
                self.logger.debug(f"   Row {idx} (Sheet row {idx + 2}): {row}")

            # Extract game state (B2:G8)
            # This corresponds to columns B-G (indices 0-5 in all_data)
            # Rows 2-8 in sheet (indices 0-6 in all_data)
            game_state = [
                all_data[0][:6], all_data[1][:6], all_data[2][:6], all_data[3][:6],
                all_data[4][:6], all_data[5][:6], all_data[6][:6]
            ]

            self.logger.debug(f"🎮 Extracted game_state (B2:G8):")
            for idx, row in enumerate(game_state):
                self.logger.debug(f"   game_state[{idx}] (Sheet row {idx + 2}): {row}")

            # Extract team IDs from game_state (already read from Scorebug tab)
            # game_state[3] is away team row (Sheet row 5), game_state[4] is home team row (Sheet row 6)
            # First column (index 0) contains the team ID - this is column B in the sheet
            self.logger.debug(f"🏟️ Extracting team IDs from game_state:")
            self.logger.debug(f"   Away team row: game_state[3] = Sheet row 5, column B (index 0)")
            self.logger.debug(f"   Home team row: game_state[4] = Sheet row 6, column B (index 0)")

            try:
                away_team_id_raw = game_state[3][0] if len(game_state) > 3 and len(game_state[3]) > 0 else None
                home_team_id_raw = game_state[4][0] if len(game_state) > 4 and len(game_state[4]) > 0 else None

                self.logger.debug(f"   Raw away team ID value: '{away_team_id_raw}'")
                self.logger.debug(f"   Raw home team ID value: '{home_team_id_raw}'")

                away_team_id = int(away_team_id_raw) if away_team_id_raw else None
                home_team_id = int(home_team_id_raw) if home_team_id_raw else None

                self.logger.debug(f"   ✅ Parsed team IDs - Away: {away_team_id}, Home: {home_team_id}")

                if away_team_id is None or home_team_id is None:
                    raise ValueError(f'Team IDs not found in scorebug (away: {away_team_id}, home: {home_team_id})')
            except (ValueError, IndexError) as e:
                self.logger.error(f"❌ Failed to parse team IDs from scorebug: {e}")
                raise ValueError(f'Could not extract team IDs from scorecard')

            # Parse game state
            self.logger.debug(f"📝 Parsing header from game_state[0][0] (Sheet B2):")
            header = game_state[0][0] if game_state[0] else ''
            is_final = header[-5:] == 'FINAL' if header else False
            self.logger.debug(f"   Header value: '{header}'")
            self.logger.debug(f"   Is Final: {is_final}")

            # Parse scores with validation
            self.logger.debug(f"⚾ Parsing scores:")
            self.logger.debug(f"   Away score: game_state[3][2] (Sheet row 5, column D)")
            self.logger.debug(f"   Home score: game_state[4][2] (Sheet row 6, column D)")

            try:
                away_score_raw = game_state[3][2] if len(game_state) > 3 and len(game_state[3]) > 2 else '0'
                self.logger.debug(f"   Raw away score value: '{away_score_raw}' (type: {type(away_score_raw).__name__})")
                away_score = int(away_score_raw) if away_score_raw != '' else 0
                self.logger.debug(f"   ✅ Parsed away score: {away_score}")
            except (ValueError, IndexError) as e:
                self.logger.warning(f"   ⚠️ Failed to parse away score: {e}")
                away_score = 0

            try:
                home_score_raw = game_state[4][2] if len(game_state) > 4 and len(game_state[4]) > 2 else '0'
                self.logger.debug(f"   Raw home score value: '{home_score_raw}' (type: {type(home_score_raw).__name__})")
                home_score = int(home_score_raw) if home_score_raw != '' else 0
                self.logger.debug(f"   ✅ Parsed home score: {home_score}")
            except (ValueError, IndexError) as e:
                self.logger.warning(f"   ⚠️ Failed to parse home score: {e}")
                home_score = 0

            try:
                inning_raw = game_state[3][5] if len(game_state) > 3 and len(game_state[3]) > 5 else '0'
                self.logger.debug(f"   Raw inning value: '{inning_raw}' (type: {type(inning_raw).__name__})")
                inning = int(inning_raw) if inning_raw != '' else 1
                self.logger.debug(f"   ✅ Parsed inning: {inning}")
            except (ValueError, IndexError) as e:
                self.logger.warning(f"   ⚠️ Failed to parse home score: {e}")
                inning = 1

            self.logger.debug(f"⏱️ Parsing game state from game_state[3][4] (Sheet row 5, column F):")
            which_half = game_state[3][4] if len(game_state) > 3 and len(game_state[3]) > 4 else ''
            self.logger.debug(f"   Which half value: '{which_half}'")

            # Parse outs from all_data[4][4] (Sheet F6 - columns start at B, so F=index 4)
            self.logger.debug(f"🔢 Parsing outs from F6 (all_data[4][4]):")
            try:
                outs_raw = all_data[4][4] if len(all_data) > 4 and len(all_data[4]) > 4 else '0'
                self.logger.debug(f"   Raw outs value: '{outs_raw}'")
                # Handle "2" or any number
                outs = int(outs_raw) if outs_raw and str(outs_raw).strip() else 0
                self.logger.debug(f"   ✅ Parsed outs: {outs}")
            except (ValueError, IndexError, AttributeError) as e:
                self.logger.warning(f"   ⚠️ Failed to parse outs: {e}")
                outs = 0

            # Extract matchup information - K3:O6 (rows 3-6, columns K-O)
            # In all_data: rows 1-4 (sheet rows 3-6), columns 9-13 (sheet columns K-O)
            self.logger.debug(f"⚔️ Extracting matchups from K3:O6:")
            matchups = [
                all_data[1][9:14] if len(all_data) > 1 else [],  # Pitcher (row 3)
                all_data[2][9:14] if len(all_data) > 2 else [],  # Batter (row 4)
                all_data[3][9:14] if len(all_data) > 3 else [],  # On Deck (row 5)
                all_data[4][9:14] if len(all_data) > 4 else [],  # In Hole (row 6)
            ]

            # Pitcher: matchups[0][0]=name, [1]=URL, [2]=stats
            pitcher_name = matchups[0][0] if len(matchups[0]) > 0 else ''
            pitcher_url = matchups[0][1] if len(matchups[0]) > 1 else ''
            pitcher_stats = matchups[0][2] if len(matchups[0]) > 2 else ''
            self.logger.debug(f"   Pitcher: {pitcher_name} | {pitcher_stats} | {pitcher_url}")

            # Batter: matchups[1][0]=name, [1]=URL, [2]=stats, [3]=order, [4]=position
            batter_name = matchups[1][0] if len(matchups[1]) > 0 else ''
            batter_url = matchups[1][1] if len(matchups[1]) > 1 else ''
            batter_stats = matchups[1][2] if len(matchups[1]) > 2 else ''
            self.logger.debug(f"   Batter: {batter_name} | {batter_stats} | {batter_url}")

            # On Deck: matchups[2][0]=name
            on_deck_name = matchups[2][0] if len(matchups[2]) > 0 else ''
            on_deck_url = matchups[2][1] if len(matchups[2]) > 1 else ''
            self.logger.debug(f"   On Deck: {on_deck_name}")

            # In Hole: matchups[3][0]=name
            in_hole_name = matchups[3][0] if len(matchups[3]) > 0 else ''
            in_hole_url = matchups[3][1] if len(matchups[3]) > 1 else ''
            self.logger.debug(f"   In Hole: {in_hole_name}")

            # Parse win percentage from all_data[6][2] (Sheet D8 - row 8, column D)
            self.logger.debug(f"📈 Parsing win percentage from D8 (all_data[6][2]):")
            try:
                win_pct_raw = all_data[6][2] if len(all_data) > 6 and len(all_data[6]) > 2 else '50%'
                self.logger.debug(f"   Raw win percentage value: '{win_pct_raw}'")
                # Remove % sign if present and convert to float
                win_pct_str = str(win_pct_raw).replace('%', '').strip()
                win_percentage = float(win_pct_str) if win_pct_str else 50.0
                self.logger.debug(f"   ✅ Parsed win percentage: {win_percentage}%")
            except (ValueError, IndexError, AttributeError) as e:
                self.logger.warning(f"   ⚠️ Failed to parse win percentage: {e}")
                win_percentage = 50.0

            self.logger.debug(f"📊 Final parsed values:")
            self.logger.debug(f"   Away team {away_team_id}: {away_score}")
            self.logger.debug(f"   Home team {home_team_id}: {home_score}")
            self.logger.debug(f"   Game state: '{which_half}'")
            self.logger.debug(f"   Outs: {outs}")
            self.logger.debug(f"   Win percentage: {win_percentage}%")
            self.logger.debug(f"   Current matchup: {batter_name} vs {pitcher_name}")
            self.logger.debug(f"   Status: {'FINAL' if is_final else 'IN PROGRESS'}")

            # Extract runners - K11:L14 (rows 11-14, columns K-L)
            # In all_data: rows 9-12 (sheet rows 11-14), columns 9-10 (sheet columns K-L)
            # runners[0] = Catcher, runners[1] = On First, runners[2] = On Second, runners[3] = On Third
            # Each runner is [name, URL]
            self.logger.debug(f"🏃 Extracting runners from K11:L14:")
            runners = [
                all_data[9][9:11] if len(all_data) > 9 else [],   # Catcher (row 11)
                all_data[10][9:11] if len(all_data) > 10 else [],  # On First (row 12)
                all_data[11][9:11] if len(all_data) > 11 else [],  # On Second (row 13)
                all_data[12][9:11] if len(all_data) > 12 else []   # On Third (row 14)
            ]
            self.logger.debug(f"   Catcher: {runners[0]}")
            self.logger.debug(f"   On First: {runners[1]}")
            self.logger.debug(f"   On Second: {runners[2]}")
            self.logger.debug(f"   On Third: {runners[3]}")

            # Extract summary if full_length (R3:S20 for inning-by-inning plays)
            # This is the "Play by Play" summary section
            summary = []
            if full_length:
                self.logger.debug(f"📋 Extracting summary from R3:S20:")
                # R3:S20 is columns 16-17 (R-S), rows 3-20 (indices 1-18)
                for row_idx in range(1, min(19, len(all_data))):
                    if len(all_data[row_idx]) > 17:
                        play_line = [all_data[row_idx][16], all_data[row_idx][17]]
                        if play_line[0] or play_line[1]:  # Only add if not empty
                            summary.append(play_line)
                self.logger.debug(f"   Found {len(summary)} summary lines")
            else:
                self.logger.debug(f"📝 Skipping summary (compact view)")

            self.logger.debug(f"✅ Scorebug data extraction complete!")

            scorebug_data = ScorebugData({
                'away_team_id': away_team_id,
                'home_team_id': home_team_id,
                'header': header,
                'away_score': away_score,
                'home_score': home_score,
                'which_half': which_half,
                'inning': inning,
                'is_final': is_final,
                'outs': outs,
                'win_percentage': win_percentage,
                'pitcher_name': pitcher_name,
                'pitcher_url': pitcher_url,
                'pitcher_stats': pitcher_stats,
                'batter_name': batter_name,
                'batter_url': batter_url,
                'batter_stats': batter_stats,
                'on_deck_name': on_deck_name,
                'in_hole_name': in_hole_name,
                'runners': runners,  # [Catcher, On First, On Second, On Third], each is [name, URL]
                'summary': summary   # Play-by-play lines from R3:S20
            })

            self.logger.debug(f"🎯 Created ScorebugData object:")
            self.logger.debug(f"   Away Team ID: {scorebug_data.away_team_id}")
            self.logger.debug(f"   Home Team ID: {scorebug_data.home_team_id}")
            self.logger.debug(f"   Header: '{scorebug_data.header}'")
            self.logger.debug(f"   Score Line: {scorebug_data.score_line}")
            self.logger.debug(f"   Which Half: '{scorebug_data.which_half}'")
            self.logger.debug(f"   Is Final: {scorebug_data.is_final}")
            self.logger.debug(f"   Is Active: {scorebug_data.is_active}")

            return scorebug_data

        except pygsheets.WorksheetNotFound:
            self.logger.error(f"Scorebug tab not found in scorecard")
            raise SheetsException("Scorebug tab not found. Is this a valid scorecard?")
        except Exception as e:
            self.logger.error(f"Failed to read scorebug data: {e}")
            raise SheetsException(f"Unable to read scorebug data: {str(e)}")
