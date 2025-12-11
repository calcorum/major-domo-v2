"""
Draft Sheet Service

Handles writing draft picks to Google Sheets for public tracking.
Extends SheetsService to reuse authentication and async patterns.
"""
import asyncio
from typing import List, Optional, Tuple

from config import get_config
from exceptions import SheetsException
from services.sheets_service import SheetsService
from utils.logging import get_contextual_logger


class DraftSheetService(SheetsService):
    """Service for writing draft picks to Google Sheets."""

    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize draft sheet service.

        Args:
            credentials_path: Path to service account credentials JSON
                             If None, will use path from config
        """
        super().__init__(credentials_path)
        self.logger = get_contextual_logger(f'{__name__}.DraftSheetService')
        self._config = get_config()

    async def write_pick(
        self,
        season: int,
        overall: int,
        orig_owner_abbrev: str,
        owner_abbrev: str,
        player_name: str,
        swar: float
    ) -> bool:
        """
        Write a single draft pick to the season's draft sheet.

        Data is written to columns D-G (4 columns):
        - D: Original owner abbreviation (for traded picks)
        - E: Current owner abbreviation
        - F: Player name
        - G: Player sWAR value

        Row number is calculated as: overall + 1 (pick 1 goes to row 2).

        Args:
            season: Draft season number
            overall: Overall pick number (1-512)
            orig_owner_abbrev: Original owner team abbreviation
            owner_abbrev: Current owner team abbreviation
            player_name: Name of the drafted player
            swar: Player's sWAR (WAR Above Replacement) value

        Returns:
            True if write succeeded, False otherwise
        """
        if not self._config.draft_sheet_enabled:
            self.logger.debug("Draft sheet writes are disabled")
            return False

        sheet_key = self._config.get_draft_sheet_key(season)
        if not sheet_key:
            self.logger.warning(f"No draft sheet configured for season {season}")
            return False

        try:
            loop = asyncio.get_event_loop()

            # Get pygsheets client
            sheets = await loop.run_in_executor(None, self._get_client)

            # Open the draft sheet by key
            spreadsheet = await loop.run_in_executor(
                None,
                sheets.open_by_key,
                sheet_key
            )

            # Get the worksheet
            worksheet = await loop.run_in_executor(
                None,
                spreadsheet.worksheet_by_title,
                self._config.draft_sheet_worksheet
            )

            # Prepare pick data (4 columns: orig_owner, owner, player, swar)
            pick_data = [[orig_owner_abbrev, owner_abbrev, player_name, swar]]

            # Calculate row (overall + 1 to leave row 1 for headers)
            row = overall + 1
            start_column = self._config.draft_sheet_start_column
            cell_range = f'{start_column}{row}'

            # Write the pick data
            await loop.run_in_executor(
                None,
                lambda: worksheet.update_values(crange=cell_range, values=pick_data)
            )

            self.logger.info(
                f"Wrote pick {overall} to draft sheet",
                season=season,
                overall=overall,
                player=player_name,
                owner=owner_abbrev
            )
            return True

        except Exception as e:
            self.logger.error(
                f"Failed to write pick to draft sheet: {e}",
                season=season,
                overall=overall,
                player=player_name
            )
            return False

    async def write_picks_batch(
        self,
        season: int,
        picks: List[Tuple[int, str, str, str, float]]
    ) -> Tuple[int, int]:
        """
        Write multiple draft picks to the sheet in a single batch operation.

        Used for resync operations to repopulate the entire sheet from database.

        Args:
            season: Draft season number
            picks: List of tuples (overall, orig_owner_abbrev, owner_abbrev, player_name, swar)

        Returns:
            Tuple of (success_count, failure_count)
        """
        if not self._config.draft_sheet_enabled:
            self.logger.debug("Draft sheet writes are disabled")
            return (0, len(picks))

        sheet_key = self._config.get_draft_sheet_key(season)
        if not sheet_key:
            self.logger.warning(f"No draft sheet configured for season {season}")
            return (0, len(picks))

        if not picks:
            return (0, 0)

        try:
            loop = asyncio.get_event_loop()

            # Get pygsheets client
            sheets = await loop.run_in_executor(None, self._get_client)

            # Open the draft sheet by key
            spreadsheet = await loop.run_in_executor(
                None,
                sheets.open_by_key,
                sheet_key
            )

            # Get the worksheet
            worksheet = await loop.run_in_executor(
                None,
                spreadsheet.worksheet_by_title,
                self._config.draft_sheet_worksheet
            )

            # Sort picks by overall to write in order
            sorted_picks = sorted(picks, key=lambda p: p[0])

            # Build batch data - each pick goes to its calculated row
            # We'll write one row at a time to handle non-contiguous picks
            success_count = 0
            failure_count = 0

            for overall, orig_owner, owner, player_name, swar in sorted_picks:
                try:
                    pick_data = [[orig_owner, owner, player_name, swar]]
                    row = overall + 1
                    start_column = self._config.draft_sheet_start_column
                    cell_range = f'{start_column}{row}'

                    await loop.run_in_executor(
                        None,
                        lambda cr=cell_range, pd=pick_data: worksheet.update_values(
                            crange=cr, values=pd
                        )
                    )
                    success_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to write pick {overall}: {e}")
                    failure_count += 1

            self.logger.info(
                f"Batch write complete: {success_count} succeeded, {failure_count} failed",
                season=season,
                total_picks=len(picks)
            )
            return (success_count, failure_count)

        except Exception as e:
            self.logger.error(f"Failed to initialize batch write: {e}", season=season)
            return (0, len(picks))

    async def clear_picks_range(
        self,
        season: int,
        start_overall: int = 1,
        end_overall: int = 512
    ) -> bool:
        """
        Clear a range of picks from the draft sheet.

        Used before resync to clear existing data.

        Args:
            season: Draft season number
            start_overall: First pick to clear (default: 1)
            end_overall: Last pick to clear (default: 512 for 32 rounds * 16 teams)

        Returns:
            True if clear succeeded, False otherwise
        """
        if not self._config.draft_sheet_enabled:
            self.logger.debug("Draft sheet writes are disabled")
            return False

        sheet_key = self._config.get_draft_sheet_key(season)
        if not sheet_key:
            self.logger.warning(f"No draft sheet configured for season {season}")
            return False

        try:
            loop = asyncio.get_event_loop()

            # Get pygsheets client
            sheets = await loop.run_in_executor(None, self._get_client)

            # Open the draft sheet by key
            spreadsheet = await loop.run_in_executor(
                None,
                sheets.open_by_key,
                sheet_key
            )

            # Get the worksheet
            worksheet = await loop.run_in_executor(
                None,
                spreadsheet.worksheet_by_title,
                self._config.draft_sheet_worksheet
            )

            # Calculate range (4 columns: D through G)
            start_row = start_overall + 1
            end_row = end_overall + 1
            start_column = self._config.draft_sheet_start_column

            # Convert start column letter to end column (D -> G for 4 columns)
            end_column = chr(ord(start_column) + 3)

            cell_range = f'{start_column}{start_row}:{end_column}{end_row}'

            # Clear the range by setting empty values
            # We create a 2D array of empty strings
            num_rows = end_row - start_row + 1
            empty_data = [['', '', '', ''] for _ in range(num_rows)]

            await loop.run_in_executor(
                None,
                lambda: worksheet.update_values(
                    crange=f'{start_column}{start_row}',
                    values=empty_data
                )
            )

            self.logger.info(
                f"Cleared picks {start_overall}-{end_overall} from draft sheet",
                season=season
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to clear draft sheet: {e}", season=season)
            return False

    def get_sheet_url(self, season: int) -> Optional[str]:
        """
        Get the full Google Sheets URL for a given draft season.

        Args:
            season: Draft season number

        Returns:
            Full URL to the draft sheet, or None if not configured
        """
        return self._config.get_draft_sheet_url(season)


# Global service instance - lazily initialized
_draft_sheet_service: Optional[DraftSheetService] = None


def get_draft_sheet_service() -> DraftSheetService:
    """Get the global draft sheet service instance."""
    global _draft_sheet_service
    if _draft_sheet_service is None:
        _draft_sheet_service = DraftSheetService()
    return _draft_sheet_service
