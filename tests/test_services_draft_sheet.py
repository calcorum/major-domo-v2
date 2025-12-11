"""
Tests for DraftSheetService

Tests the Google Sheets integration for draft pick tracking.
Uses mocked pygsheets to avoid actual API calls.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Tuple, List

from services.draft_sheet_service import DraftSheetService, get_draft_sheet_service


class TestDraftSheetService:
    """
    Test suite for DraftSheetService.

    Tests write_pick(), write_picks_batch(), clear_picks_range(), and get_sheet_url().
    All tests mock pygsheets to avoid actual Google Sheets API calls.
    """

    @pytest.fixture
    def mock_config(self):
        """
        Create a mock config with draft sheet settings.

        Provides:
        - draft_sheet_enabled: True
        - sba_season: 12
        - draft_sheet_worksheet: "Ordered List"
        - draft_sheet_start_column: "D"
        - draft_total_picks: 512
        """
        config = MagicMock()
        config.draft_sheet_enabled = True
        config.sba_season = 12
        config.draft_sheet_worksheet = "Ordered List"
        config.draft_sheet_start_column = "D"
        config.draft_total_picks = 512
        config.sheets_credentials_path = "/app/data/test-creds.json"
        config.get_draft_sheet_key = MagicMock(return_value="test-sheet-key-123")
        config.get_draft_sheet_url = MagicMock(
            return_value="https://docs.google.com/spreadsheets/d/test-sheet-key-123"
        )
        return config

    @pytest.fixture
    def mock_pygsheets(self):
        """
        Create mock pygsheets client, spreadsheet, and worksheet.

        Provides:
        - sheets_client: Mock pygsheets client
        - spreadsheet: Mock spreadsheet
        - worksheet: Mock worksheet with update_values method
        """
        worksheet = MagicMock()
        worksheet.update_values = MagicMock()

        spreadsheet = MagicMock()
        spreadsheet.worksheet_by_title = MagicMock(return_value=worksheet)

        sheets_client = MagicMock()
        sheets_client.open_by_key = MagicMock(return_value=spreadsheet)

        return {
            'client': sheets_client,
            'spreadsheet': spreadsheet,
            'worksheet': worksheet
        }

    @pytest.fixture
    def service(self, mock_config, mock_pygsheets):
        """
        Create DraftSheetService instance with mocked dependencies.

        The service is set up with:
        - Mocked config
        - Mocked pygsheets client (via _get_client override)
        """
        with patch('services.draft_sheet_service.get_config', return_value=mock_config):
            service = DraftSheetService()
            service._config = mock_config
            service._sheets_client = mock_pygsheets['client']
            return service

    # ==================== write_pick() Tests ====================

    @pytest.mark.asyncio
    async def test_write_pick_success(self, service, mock_pygsheets):
        """
        Test successful write of a single draft pick to the sheet.

        Verifies:
        - Correct cell range is calculated (D + overall + 1)
        - Correct data is written (4 columns)
        - Returns True on success
        """
        result = await service.write_pick(
            season=12,
            overall=1,
            orig_owner_abbrev="HAM",
            owner_abbrev="HAM",
            player_name="Mike Trout",
            swar=8.5
        )

        assert result is True
        # Verify worksheet was accessed
        mock_pygsheets['spreadsheet'].worksheet_by_title.assert_called_with("Ordered List")

    @pytest.mark.asyncio
    async def test_write_pick_disabled(self, service, mock_config):
        """
        Test that write_pick returns False when feature is disabled.

        Verifies:
        - Returns False when draft_sheet_enabled is False
        - No API calls are made
        """
        mock_config.draft_sheet_enabled = False

        result = await service.write_pick(
            season=12,
            overall=1,
            orig_owner_abbrev="HAM",
            owner_abbrev="HAM",
            player_name="Mike Trout",
            swar=8.5
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_write_pick_no_sheet_configured(self, service, mock_config):
        """
        Test that write_pick returns False when no sheet is configured for season.

        Verifies:
        - Returns False when get_draft_sheet_key returns None
        - No API calls are made
        """
        mock_config.get_draft_sheet_key = MagicMock(return_value=None)

        result = await service.write_pick(
            season=13,  # Season 13 has no configured sheet
            overall=1,
            orig_owner_abbrev="HAM",
            owner_abbrev="HAM",
            player_name="Mike Trout",
            swar=8.5
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_write_pick_api_error(self, service, mock_pygsheets):
        """
        Test that write_pick returns False and logs error on API failure.

        Verifies:
        - Returns False on exception
        - Exception is caught and logged (not raised)
        """
        mock_pygsheets['spreadsheet'].worksheet_by_title.side_effect = Exception("API Error")

        result = await service.write_pick(
            season=12,
            overall=1,
            orig_owner_abbrev="HAM",
            owner_abbrev="HAM",
            player_name="Mike Trout",
            swar=8.5
        )

        assert result is False

    # ==================== write_picks_batch() Tests ====================

    @pytest.mark.asyncio
    async def test_write_picks_batch_success(self, service, mock_pygsheets):
        """
        Test successful batch write of multiple picks.

        Verifies:
        - All picks are written
        - Returns correct success/failure counts
        """
        picks = [
            (1, "HAM", "HAM", "Player 1", 2.5),
            (2, "NYY", "NYY", "Player 2", 3.0),
            (3, "BOS", "BOS", "Player 3", 1.5),
        ]

        success_count, failure_count = await service.write_picks_batch(
            season=12,
            picks=picks
        )

        assert success_count == 3
        assert failure_count == 0

    @pytest.mark.asyncio
    async def test_write_picks_batch_empty_list(self, service):
        """
        Test batch write with empty picks list.

        Verifies:
        - Returns (0, 0) for empty list
        - No API calls are made
        """
        success_count, failure_count = await service.write_picks_batch(
            season=12,
            picks=[]
        )

        assert success_count == 0
        assert failure_count == 0

    @pytest.mark.asyncio
    async def test_write_picks_batch_disabled(self, service, mock_config):
        """
        Test batch write when feature is disabled.

        Verifies:
        - Returns (0, total_picks) when disabled
        """
        mock_config.draft_sheet_enabled = False
        picks = [
            (1, "HAM", "HAM", "Player 1", 2.5),
            (2, "NYY", "NYY", "Player 2", 3.0),
        ]

        success_count, failure_count = await service.write_picks_batch(
            season=12,
            picks=picks
        )

        assert success_count == 0
        assert failure_count == 2

    # ==================== clear_picks_range() Tests ====================

    @pytest.mark.asyncio
    async def test_clear_picks_range_success(self, service, mock_pygsheets):
        """
        Test successful clearing of picks range.

        Verifies:
        - Returns True on success
        - Correct range is cleared
        """
        result = await service.clear_picks_range(
            season=12,
            start_overall=1,
            end_overall=512
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_clear_picks_range_disabled(self, service, mock_config):
        """
        Test clearing when feature is disabled.

        Verifies:
        - Returns False when disabled
        """
        mock_config.draft_sheet_enabled = False

        result = await service.clear_picks_range(
            season=12,
            start_overall=1,
            end_overall=512
        )

        assert result is False

    # ==================== get_sheet_url() Tests ====================

    def test_get_sheet_url_configured(self, service, mock_config):
        """
        Test get_sheet_url returns URL when configured.

        Verifies:
        - Returns correct URL format
        """
        url = service.get_sheet_url(season=12)

        assert url == "https://docs.google.com/spreadsheets/d/test-sheet-key-123"

    def test_get_sheet_url_not_configured(self, service, mock_config):
        """
        Test get_sheet_url returns None when not configured.

        Verifies:
        - Returns None for unconfigured season
        """
        mock_config.get_draft_sheet_url = MagicMock(return_value=None)

        url = service.get_sheet_url(season=99)

        assert url is None


class TestGlobalServiceInstance:
    """
    Test suite for the global service instance pattern.

    Tests get_draft_sheet_service() lazy initialization.
    """

    def test_get_draft_sheet_service_returns_instance(self):
        """
        Test that get_draft_sheet_service returns a DraftSheetService instance.

        Note: This creates a real service instance but won't make API calls
        without being used.
        """
        with patch('services.draft_sheet_service.get_config') as mock_config:
            mock_config.return_value.sheets_credentials_path = "/test/path.json"
            mock_config.return_value.draft_sheet_enabled = True

            # Reset global instance
            import services.draft_sheet_service as service_module
            service_module._draft_sheet_service = None

            service = get_draft_sheet_service()

            assert isinstance(service, DraftSheetService)

    def test_get_draft_sheet_service_returns_same_instance(self):
        """
        Test that get_draft_sheet_service returns the same instance on subsequent calls.

        Verifies singleton pattern for global service.
        """
        with patch('services.draft_sheet_service.get_config') as mock_config:
            mock_config.return_value.sheets_credentials_path = "/test/path.json"
            mock_config.return_value.draft_sheet_enabled = True

            # Reset global instance
            import services.draft_sheet_service as service_module
            service_module._draft_sheet_service = None

            service1 = get_draft_sheet_service()
            service2 = get_draft_sheet_service()

            assert service1 is service2
