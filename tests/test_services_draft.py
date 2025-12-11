"""
Comprehensive tests for Draft Services

Tests cover:
- DraftService: Draft configuration and state management
- DraftPickService: Draft pick CRUD operations
- DraftListService: Auto-draft queue management

API Specification Reference:
- GET /api/v3/draftdata - Returns draft configuration
- PATCH /api/v3/draftdata/{id} - Updates draft config (query params)
- GET /api/v3/draftpicks - Query draft picks with filters
- GET /api/v3/draftpicks/{id} - Get single pick
- PATCH /api/v3/draftpicks/{id} - Update pick (full model body required)
- GET /api/v3/draftlist - Get team draft lists
- POST /api/v3/draftlist - Bulk replace team draft list
- DELETE /api/v3/draftlist/team/{id} - Clear team draft list
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from services.draft_service import DraftService, draft_service
from services.draft_pick_service import DraftPickService, draft_pick_service
from services.draft_list_service import DraftListService, draft_list_service
from models.draft_data import DraftData
from models.draft_pick import DraftPick
from models.draft_list import DraftList
from models.team import Team
from models.player import Player
from exceptions import APIException


# =============================================================================
# Test Data Helpers
# =============================================================================

def create_draft_data(**overrides) -> dict:
    """
    Create complete draft data matching API response format.

    API returns: id, currentpick, timer, pick_deadline, result_channel,
                 ping_channel, pick_minutes
    """
    base_data = {
        'id': 1,
        'currentpick': 25,
        'timer': True,
        'pick_deadline': (datetime.now() + timedelta(minutes=10)).isoformat(),
        'result_channel': '123456789012345678',  # API returns as string
        'ping_channel': '987654321098765432',    # API returns as string
        'pick_minutes': 2
    }
    base_data.update(overrides)
    return base_data


def create_team_data(team_id: int, abbrev: str = "TST", **overrides) -> dict:
    """Create complete team data for nested objects (matches Team model requirements)."""
    base_data = {
        'id': team_id,
        'abbrev': abbrev,
        'sname': f'{abbrev}',           # Required: short name
        'lname': f'{abbrev} Team',      # Required: long name
        'season': 12,
        'division_id': 1,
        'gmid': 100 + team_id,
        'thumbnail': f'https://example.com/team{team_id}.png'
    }
    base_data.update(overrides)
    return base_data


def create_player_data(player_id: int, name: str = "Test Player", **overrides) -> dict:
    """Create complete player data for nested objects."""
    base_data = {
        'id': player_id,
        'name': name,
        'wara': 2.5,
        'season': 12,
        'team_id': 1,
        'image': f'https://example.com/player{player_id}.jpg',
        'pos_1': 'SS'
    }
    base_data.update(overrides)
    return base_data


def create_draft_pick_data(
    pick_id: int,
    season: int = 12,
    overall: int = 1,
    round_num: int = 1,
    player_id: int = None,
    include_nested: bool = True,
    **overrides
) -> dict:
    """
    Create complete draft pick data matching API response format.

    API returns nested team and player objects when short_output=False.
    """
    base_data = {
        'id': pick_id,
        'season': season,
        'overall': overall,
        'round': round_num,
        'origowner_id': 1,
        'owner_id': 1,
        'player_id': player_id
    }

    if include_nested:
        base_data['origowner'] = create_team_data(1, 'WV')
        base_data['owner'] = create_team_data(1, 'WV')
        if player_id:
            base_data['player'] = create_player_data(player_id, f'Player {player_id}')

    base_data.update(overrides)
    return base_data


def create_draft_list_data(
    entry_id: int,
    season: int = 12,
    team_id: int = 1,
    player_id: int = 100,
    rank: int = 1,
    **overrides
) -> dict:
    """
    Create complete draft list entry matching API response format.

    API returns nested team and player objects.
    """
    base_data = {
        'id': entry_id,
        'season': season,
        'rank': rank,
        'team': create_team_data(team_id, 'WV'),
        'player': create_player_data(player_id, f'Target Player {player_id}')
    }
    base_data.update(overrides)
    return base_data


# =============================================================================
# DraftService Tests
# =============================================================================

class TestDraftService:
    """Tests for DraftService - draft configuration and state management."""

    @pytest.fixture
    def mock_client(self):
        """Create mock API client."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_client):
        """Create DraftService with mocked client."""
        svc = DraftService()
        svc._client = mock_client
        return svc

    # -------------------------------------------------------------------------
    # get_draft_data() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_draft_data_success(self, service, mock_client):
        """
        Test successful retrieval of draft data.

        Verifies:
        - GET /draftdata endpoint is called
        - Response is parsed into DraftData model
        - All fields are correctly populated
        """
        mock_data = create_draft_data(currentpick=42, timer=True, pick_minutes=5)
        mock_client.get.return_value = {'count': 1, 'draftdata': [mock_data]}

        result = await service.get_draft_data()

        assert result is not None
        assert isinstance(result, DraftData)
        assert result.currentpick == 42
        assert result.timer is True
        assert result.pick_minutes == 5
        mock_client.get.assert_called_once_with('draftdata', params=None)

    @pytest.mark.asyncio
    async def test_get_draft_data_not_found(self, service, mock_client):
        """
        Test handling when no draft data exists.

        Verifies graceful handling when API returns empty list.
        """
        mock_client.get.return_value = {'count': 0, 'draftdata': []}

        result = await service.get_draft_data()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_draft_data_api_error(self, service, mock_client):
        """
        Test error handling when API call fails.

        Verifies service returns None on exception rather than crashing.
        """
        mock_client.get.side_effect = APIException("API unavailable")

        result = await service.get_draft_data()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_draft_data_channel_id_conversion(self, service, mock_client):
        """
        Test that channel IDs are converted from string to int.

        Database stores channel IDs as strings, but we need integers for Discord.
        """
        mock_data = create_draft_data(
            result_channel='123456789012345678',
            ping_channel='987654321098765432'
        )
        mock_client.get.return_value = {'count': 1, 'draftdata': [mock_data]}

        result = await service.get_draft_data()

        assert result.result_channel == 123456789012345678
        assert result.ping_channel == 987654321098765432

    # -------------------------------------------------------------------------
    # update_draft_data() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_draft_data_success(self, service, mock_client):
        """
        Test successful draft data update.

        Verifies:
        - PATCH is called with query parameters (not JSON body)
        - Updated data is returned
        """
        updated_data = create_draft_data(currentpick=50, timer=False)
        mock_client.patch.return_value = updated_data

        result = await service.update_draft_data(
            draft_id=1,
            updates={'currentpick': 50, 'timer': False}
        )

        assert result is not None
        assert result.currentpick == 50
        assert result.timer is False
        mock_client.patch.assert_called_once_with(
            'draftdata',
            {'currentpick': 50, 'timer': False},
            1,
            use_query_params=True
        )

    @pytest.mark.asyncio
    async def test_update_draft_data_failure(self, service, mock_client):
        """
        Test handling of failed update.

        Verifies service returns None when PATCH fails.
        """
        mock_client.patch.return_value = None

        result = await service.update_draft_data(draft_id=1, updates={'timer': True})

        assert result is None

    # -------------------------------------------------------------------------
    # set_timer() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_set_timer_enable(self, service, mock_client):
        """
        Test enabling the draft timer.

        Verifies:
        - Timer is set to True
        - Pick deadline is calculated based on pick_minutes
        """
        # First call gets current draft data for pick_minutes
        current_data = create_draft_data(pick_minutes=3, timer=False)
        mock_client.get.return_value = {'count': 1, 'draftdata': [current_data]}

        # Second call updates the draft data
        updated_data = create_draft_data(timer=True)
        mock_client.patch.return_value = updated_data

        result = await service.set_timer(draft_id=1, active=True)

        assert result is not None
        assert result.timer is True

        # Verify patch was called with timer=True and a pick_deadline
        patch_call = mock_client.patch.call_args
        assert patch_call[0][1]['timer'] is True
        assert 'pick_deadline' in patch_call[0][1]

    @pytest.mark.asyncio
    async def test_set_timer_disable(self, service, mock_client):
        """
        Test disabling the draft timer.

        Verifies:
        - Timer is set to False
        - Pick deadline is set far in the future
        """
        updated_data = create_draft_data(timer=False)
        mock_client.patch.return_value = updated_data

        result = await service.set_timer(draft_id=1, active=False)

        assert result is not None

        # Verify pick_deadline is set far in future (690 days)
        patch_call = mock_client.patch.call_args
        deadline = patch_call[0][1]['pick_deadline']
        assert deadline > datetime.now() + timedelta(days=600)

    @pytest.mark.asyncio
    async def test_set_timer_with_custom_minutes(self, service, mock_client):
        """
        Test setting timer with custom pick_minutes.

        Verifies custom pick_minutes is passed to update.
        """
        updated_data = create_draft_data(timer=True, pick_minutes=10)
        mock_client.patch.return_value = updated_data

        result = await service.set_timer(draft_id=1, active=True, pick_minutes=10)

        patch_call = mock_client.patch.call_args
        assert patch_call[0][1]['pick_minutes'] == 10

    # -------------------------------------------------------------------------
    # advance_pick() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_advance_pick_to_next(self, service, mock_client):
        """
        Test advancing to the next unfilled pick.

        Verifies:
        - Service finds next pick without a player
        - Draft data is updated with new currentpick
        """
        # Mock config at the correct import location (inside the method)
        with patch('config.get_config') as mock_config:
            config = MagicMock()
            config.sba_season = 12
            config.draft_total_picks = 512
            mock_config.return_value = config

            # Mock draft_pick_service at the module level
            with patch('services.draft_pick_service.draft_pick_service') as mock_pick_service:
                unfilled_pick = DraftPick(**create_draft_pick_data(
                    pick_id=26, overall=26, player_id=None, include_nested=False
                ))
                mock_pick_service.get_pick = AsyncMock(return_value=unfilled_pick)

                # Current draft data has timer active
                current_data = create_draft_data(currentpick=25, timer=True, pick_minutes=2)
                mock_client.get.return_value = {'count': 1, 'draftdata': [current_data]}

                # Update returns new state
                updated_data = create_draft_data(currentpick=26)
                mock_client.patch.return_value = updated_data

                result = await service.advance_pick(draft_id=1, current_pick=25)

                assert result is not None
                assert result.currentpick == 26

    @pytest.mark.asyncio
    async def test_advance_pick_skips_filled_picks(self, service, mock_client):
        """
        Test that advance_pick skips over already-filled picks.

        Verifies picks with player_id are skipped until an empty pick is found.
        """
        with patch('config.get_config') as mock_config:
            config = MagicMock()
            config.sba_season = 12
            config.draft_total_picks = 512
            mock_config.return_value = config

            with patch('services.draft_pick_service.draft_pick_service') as mock_pick_service:
                # Picks 26-28 are filled, 29 is empty
                async def get_pick_side_effect(season, overall):
                    if overall <= 28:
                        return DraftPick(**create_draft_pick_data(
                            pick_id=overall, overall=overall, player_id=overall * 10,
                            include_nested=False
                        ))
                    else:
                        return DraftPick(**create_draft_pick_data(
                            pick_id=overall, overall=overall, player_id=None,
                            include_nested=False
                        ))

                mock_pick_service.get_pick = AsyncMock(side_effect=get_pick_side_effect)

                current_data = create_draft_data(currentpick=25, timer=True)
                mock_client.get.return_value = {'count': 1, 'draftdata': [current_data]}

                updated_data = create_draft_data(currentpick=29)
                mock_client.patch.return_value = updated_data

                result = await service.advance_pick(draft_id=1, current_pick=25)

                # Should have jumped to pick 29 (skipping 26, 27, 28)
                patch_call = mock_client.patch.call_args
                assert patch_call[0][1]['currentpick'] == 29

    # -------------------------------------------------------------------------
    # update_channels() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_channels(self, service, mock_client):
        """
        Test updating draft Discord channel configuration.

        Verifies both ping_channel and result_channel can be updated.
        """
        updated_data = create_draft_data()
        mock_client.patch.return_value = updated_data

        result = await service.update_channels(
            draft_id=1,
            ping_channel_id=111111111111111111,
            result_channel_id=222222222222222222
        )

        assert result is not None
        patch_call = mock_client.patch.call_args
        assert patch_call[0][1]['ping_channel'] == 111111111111111111
        assert patch_call[0][1]['result_channel'] == 222222222222222222


# =============================================================================
# DraftPickService Tests
# =============================================================================

class TestDraftPickService:
    """Tests for DraftPickService - draft pick CRUD operations."""

    @pytest.fixture
    def mock_client(self):
        """Create mock API client."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_client):
        """Create DraftPickService with mocked client."""
        svc = DraftPickService()
        svc._client = mock_client
        return svc

    # -------------------------------------------------------------------------
    # get_pick() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_pick_success(self, service, mock_client):
        """
        Test successful retrieval of a specific pick.

        Verifies:
        - Correct query params are sent (season, overall)
        - Pick is parsed into DraftPick model
        """
        # Use include_nested=False to avoid Team validation complexity
        pick_data = create_draft_pick_data(pick_id=42, overall=42, round_num=3, include_nested=False)
        # API returns data under 'draftpicks' key (matches endpoint name)
        mock_client.get.return_value = {'count': 1, 'draftpicks': [pick_data]}

        result = await service.get_pick(season=12, overall=42)

        assert result is not None
        assert isinstance(result, DraftPick)
        assert result.overall == 42
        assert result.round == 3

        mock_client.get.assert_called_once()
        # BaseService calls get(endpoint, params=params)
        call_kwargs = mock_client.get.call_args[1]
        assert 'params' in call_kwargs
        call_params = call_kwargs['params']
        assert ('season', '12') in call_params
        assert ('overall', '42') in call_params

    @pytest.mark.asyncio
    async def test_get_pick_not_found(self, service, mock_client):
        """
        Test handling when pick doesn't exist.

        Verifies service returns None for non-existent picks.
        """
        mock_client.get.return_value = {'count': 0, 'draftpicks': []}

        result = await service.get_pick(season=12, overall=999)

        assert result is None

    # -------------------------------------------------------------------------
    # get_picks_by_team() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_picks_by_team(self, service, mock_client):
        """
        Test retrieving picks owned by a specific team.

        Verifies:
        - Correct filter params: owner_team_id, pick_round_start, pick_round_end
        - Multiple picks are returned as list
        """
        picks_data = [
            create_draft_pick_data(pick_id=i, overall=i, round_num=1, include_nested=False)
            for i in range(1, 4)
        ]
        mock_client.get.return_value = {'count': 3, 'draftpicks': picks_data}

        result = await service.get_picks_by_team(
            season=12, team_id=1, round_start=1, round_end=5
        )

        assert len(result) == 3
        assert all(isinstance(p, DraftPick) for p in result)

        call_params = mock_client.get.call_args[1]['params']
        assert ('owner_team_id', '1') in call_params
        assert ('pick_round_start', '1') in call_params
        assert ('pick_round_end', '5') in call_params
        assert ('sort', 'order-asc') in call_params

    # -------------------------------------------------------------------------
    # get_picks_by_round() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_picks_by_round(self, service, mock_client):
        """
        Test retrieving all picks in a specific round.

        Verifies pick_round_start and pick_round_end are both set to same value.
        """
        picks_data = [
            create_draft_pick_data(pick_id=i, overall=i, round_num=3, include_nested=False)
            for i in range(33, 49)  # Round 3 picks
        ]
        mock_client.get.return_value = {'count': 16, 'draftpicks': picks_data}

        result = await service.get_picks_by_round(season=12, round_num=3)

        assert len(result) == 16

        call_params = mock_client.get.call_args[1]['params']
        assert ('pick_round_start', '3') in call_params
        assert ('pick_round_end', '3') in call_params

    @pytest.mark.asyncio
    async def test_get_picks_by_round_exclude_taken(self, service, mock_client):
        """
        Test filtering out already-taken picks.

        Verifies player_taken=false filter is applied.
        """
        mock_client.get.return_value = {'count': 0, 'draftpicks': []}

        await service.get_picks_by_round(season=12, round_num=3, include_taken=False)

        call_params = mock_client.get.call_args[1]['params']
        assert ('player_taken', 'false') in call_params

    # -------------------------------------------------------------------------
    # get_available_picks() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_available_picks(self, service, mock_client):
        """
        Test retrieving picks that haven't been selected yet.

        Verifies player_taken=false filter is always applied.
        """
        picks_data = [
            create_draft_pick_data(pick_id=i, overall=i, player_id=None, include_nested=False)
            for i in range(50, 55)
        ]
        mock_client.get.return_value = {'count': 5, 'draftpicks': picks_data}

        result = await service.get_available_picks(season=12)

        assert len(result) == 5
        assert all(p.player_id is None for p in result)

        call_params = mock_client.get.call_args[1]['params']
        assert ('player_taken', 'false') in call_params

    @pytest.mark.asyncio
    async def test_get_available_picks_with_range(self, service, mock_client):
        """
        Test filtering available picks by overall range.

        Verifies overall_start and overall_end params are passed.
        """
        mock_client.get.return_value = {'count': 0, 'draftpicks': []}

        await service.get_available_picks(
            season=12, overall_start=100, overall_end=150
        )

        call_params = mock_client.get.call_args[1]['params']
        assert ('overall_start', '100') in call_params
        assert ('overall_end', '150') in call_params

    # -------------------------------------------------------------------------
    # get_recent_picks() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_recent_picks(self, service, mock_client):
        """
        Test retrieving recently made picks.

        Verifies:
        - overall_end is set to current-1 (exclude current pick)
        - player_taken=true (only filled picks)
        - sort=order-desc (most recent first)
        - limit is applied
        """
        picks_data = [
            create_draft_pick_data(pick_id=i, overall=i, player_id=i*10, include_nested=False)
            for i in range(45, 50)
        ]
        mock_client.get.return_value = {'count': 5, 'draftpicks': picks_data}

        result = await service.get_recent_picks(season=12, overall_end=50, limit=5)

        assert len(result) == 5

        call_params = mock_client.get.call_args[1]['params']
        assert ('overall_end', '49') in call_params  # 50 - 1
        assert ('player_taken', 'true') in call_params
        assert ('sort', 'order-desc') in call_params
        assert ('limit', '5') in call_params

    # -------------------------------------------------------------------------
    # get_upcoming_picks() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_upcoming_picks(self, service, mock_client):
        """
        Test retrieving upcoming picks after current.

        Verifies:
        - overall_start is set to current+1 (exclude current pick)
        - sort=order-asc (chronological)
        - limit is applied
        """
        picks_data = [
            create_draft_pick_data(pick_id=i, overall=i, player_id=None, include_nested=False)
            for i in range(51, 56)
        ]
        mock_client.get.return_value = {'count': 5, 'draftpicks': picks_data}

        result = await service.get_upcoming_picks(season=12, overall_start=50, limit=5)

        assert len(result) == 5

        call_params = mock_client.get.call_args[1]['params']
        assert ('overall_start', '51') in call_params  # 50 + 1
        assert ('sort', 'order-asc') in call_params
        assert ('limit', '5') in call_params

    # -------------------------------------------------------------------------
    # update_pick_selection() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_pick_selection_success(self, service, mock_client):
        """
        Test successfully selecting a player for a pick.

        CRITICAL: API requires full DraftPickModel body, not partial update.
        Service must first GET the pick, then send complete model.
        """
        # First call: get_by_id to retrieve current pick (no nested objects)
        current_pick_data = create_draft_pick_data(
            pick_id=42, overall=42, round_num=3, player_id=None, include_nested=False
        )

        # Second call: patch with full model returns updated pick
        updated_pick_data = create_draft_pick_data(
            pick_id=42, overall=42, round_num=3, player_id=999, include_nested=False
        )

        mock_client.get.return_value = current_pick_data
        mock_client.patch.return_value = updated_pick_data

        result = await service.update_pick_selection(pick_id=42, player_id=999)

        assert result is not None
        assert result.player_id == 999

        # Verify PATCH was called with full model (not just player_id)
        patch_call = mock_client.patch.call_args
        patch_data = patch_call[0][1]
        assert patch_data['player_id'] == 999
        assert patch_data['overall'] == 42
        assert patch_data['round'] == 3
        assert patch_data['season'] == 12
        assert patch_data['origowner_id'] == 1
        assert patch_data['owner_id'] == 1

    @pytest.mark.asyncio
    async def test_update_pick_selection_pick_not_found(self, service, mock_client):
        """
        Test handling when pick doesn't exist.

        Verifies service returns None and doesn't attempt PATCH.
        """
        mock_client.get.return_value = None

        result = await service.update_pick_selection(pick_id=999, player_id=100)

        assert result is None
        mock_client.patch.assert_not_called()

    # -------------------------------------------------------------------------
    # clear_pick_selection() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_clear_pick_selection_success(self, service, mock_client):
        """
        Test clearing a player selection from a pick.

        Used for admin wipe operations. Must send full model with player_id=None.
        """
        current_pick_data = create_draft_pick_data(
            pick_id=42, overall=42, round_num=3, player_id=999, include_nested=False
        )
        cleared_pick_data = create_draft_pick_data(
            pick_id=42, overall=42, round_num=3, player_id=None, include_nested=False
        )

        mock_client.get.return_value = current_pick_data
        mock_client.patch.return_value = cleared_pick_data

        result = await service.clear_pick_selection(pick_id=42)

        assert result is not None
        assert result.player_id is None

        # Verify full model sent with player_id=None
        patch_call = mock_client.patch.call_args
        patch_data = patch_call[0][1]
        assert patch_data['player_id'] is None
        assert 'overall' in patch_data  # Full model required

    @pytest.mark.asyncio
    async def test_get_skipped_picks_for_team_success(self, service, mock_client):
        """
        Test retrieving skipped picks for a team.

        Skipped picks are picks before the current overall that have no player selected.
        Returns picks ordered by overall (ascending) so earliest skipped pick is first.
        """
        # Team 5 has two skipped picks (overall 10 and 15) before current pick 25
        skipped_pick_1 = create_draft_pick_data(
            pick_id=10, overall=10, round_num=1, player_id=None,
            owner_team_id=5, include_nested=False
        )
        skipped_pick_2 = create_draft_pick_data(
            pick_id=15, overall=15, round_num=1, player_id=None,
            owner_team_id=5, include_nested=False
        )

        mock_client.get.return_value = {
            'count': 2,
            'picks': [skipped_pick_1, skipped_pick_2]
        }

        result = await service.get_skipped_picks_for_team(
            season=12,
            team_id=5,
            current_overall=25
        )

        # Verify results
        assert len(result) == 2
        assert result[0].overall == 10  # Earliest skipped pick first
        assert result[1].overall == 15
        assert result[0].player_id is None
        assert result[1].player_id is None

        # Verify API call
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        params = call_args[1]['params']
        # Should request picks before current (overall_end=24), owned by team, with no player
        assert ('overall_end', '24') in params
        assert ('owner_team_id', '5') in params
        assert ('player_taken', 'false') in params

    @pytest.mark.asyncio
    async def test_get_skipped_picks_for_team_none_found(self, service, mock_client):
        """
        Test when team has no skipped picks.

        Returns empty list when all prior picks have been made.
        """
        mock_client.get.return_value = {
            'count': 0,
            'picks': []
        }

        result = await service.get_skipped_picks_for_team(
            season=12,
            team_id=5,
            current_overall=25
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_skipped_picks_for_team_api_error(self, service, mock_client):
        """
        Test graceful handling of API errors.

        Returns empty list on error rather than raising exception.
        """
        mock_client.get.side_effect = Exception("API Error")

        result = await service.get_skipped_picks_for_team(
            season=12,
            team_id=5,
            current_overall=25
        )

        # Should return empty list on error, not raise
        assert result == []


# =============================================================================
# DraftListService Tests
# =============================================================================

class TestDraftListService:
    """Tests for DraftListService - auto-draft queue management."""

    @pytest.fixture
    def mock_client(self):
        """Create mock API client."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_client):
        """Create DraftListService with mocked client."""
        svc = DraftListService()
        svc._client = mock_client
        # Also mock get_client to return the same mock for POST/DELETE operations
        svc.get_client = AsyncMock(return_value=mock_client)
        return svc

    # -------------------------------------------------------------------------
    # get_team_list() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_team_list_success(self, service, mock_client):
        """
        Test retrieving a team's draft list.

        Verifies:
        - Correct query params (season, team_id)
        - Results are sorted by rank (client-side since API doesn't support sort)
        """
        list_data = [
            create_draft_list_data(entry_id=3, rank=3, player_id=103),
            create_draft_list_data(entry_id=1, rank=1, player_id=101),
            create_draft_list_data(entry_id=2, rank=2, player_id=102),
        ]
        mock_client.get.return_value = {'count': 3, 'picks': list_data}

        result = await service.get_team_list(season=12, team_id=1)

        assert len(result) == 3
        # Verify sorted by rank (client-side sorting)
        assert result[0].rank == 1
        assert result[1].rank == 2
        assert result[2].rank == 3

        call_params = mock_client.get.call_args[1]['params']
        assert ('season', '12') in call_params
        assert ('team_id', '1') in call_params
        # sort param should NOT be sent (API doesn't support it)
        assert not any(p[0] == 'sort' for p in call_params)

    @pytest.mark.asyncio
    async def test_get_team_list_empty(self, service, mock_client):
        """
        Test handling when team has no draft list.

        Verifies empty list is returned, not None.
        """
        mock_client.get.return_value = {'count': 0, 'picks': []}

        result = await service.get_team_list(season=12, team_id=1)

        assert result == []

    # -------------------------------------------------------------------------
    # add_to_list() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_add_to_list_at_end(self, service, mock_client):
        """
        Test adding a player to end of draft list.

        Verifies:
        - Existing list is fetched first
        - New entry is added with rank = len(current) + 1
        - Full list is POSTed (bulk replacement pattern)
        """
        # Existing list has 2 entries
        existing_list = [
            create_draft_list_data(entry_id=1, rank=1, player_id=101),
            create_draft_list_data(entry_id=2, rank=2, player_id=102),
        ]
        mock_client.get.return_value = {'count': 2, 'picks': existing_list}

        # After POST, return updated list with 3 entries
        updated_list = existing_list + [
            create_draft_list_data(entry_id=3, rank=3, player_id=103)
        ]
        # First get returns existing, second get returns updated (for verification)
        mock_client.get.side_effect = [
            {'count': 2, 'picks': existing_list},
            {'count': 3, 'picks': updated_list}
        ]
        mock_client.post.return_value = "Inserted 3 list values"

        result = await service.add_to_list(
            season=12, team_id=1, player_id=103, rank=None  # rank=None means add to end
        )

        assert result is not None
        assert len(result) == 3

        # Verify POST payload structure
        post_call = mock_client.post.call_args
        payload = post_call[0][1]
        assert 'draft_list' in payload
        assert payload['count'] == 3
        # New entry should have rank 3
        new_entry = [e for e in payload['draft_list'] if e['player_id'] == 103][0]
        assert new_entry['rank'] == 3

    @pytest.mark.asyncio
    async def test_add_to_list_at_position(self, service, mock_client):
        """
        Test adding a player at a specific position.

        Verifies existing entries at/after that position are shifted down.
        """
        existing_list = [
            create_draft_list_data(entry_id=1, rank=1, player_id=101),
            create_draft_list_data(entry_id=2, rank=2, player_id=102),
        ]

        updated_list = [
            create_draft_list_data(entry_id=1, rank=1, player_id=101),
            create_draft_list_data(entry_id=3, rank=2, player_id=103),  # Inserted
            create_draft_list_data(entry_id=2, rank=3, player_id=102),  # Shifted
        ]

        mock_client.get.side_effect = [
            {'count': 2, 'picks': existing_list},
            {'count': 3, 'picks': updated_list}
        ]
        mock_client.post.return_value = "Inserted 3 list values"

        result = await service.add_to_list(
            season=12, team_id=1, player_id=103, rank=2  # Insert at position 2
        )

        assert result is not None

        # Verify ranks were adjusted
        post_call = mock_client.post.call_args
        payload = post_call[0][1]

        entries_by_player = {e['player_id']: e for e in payload['draft_list']}
        assert entries_by_player[101]['rank'] == 1  # Unchanged
        assert entries_by_player[103]['rank'] == 2  # Inserted
        assert entries_by_player[102]['rank'] == 3  # Shifted from 2 to 3

    # -------------------------------------------------------------------------
    # remove_player_from_list() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_remove_player_from_list_success(self, service, mock_client):
        """
        Test removing a player from draft list.

        Verifies:
        - Player is removed
        - Remaining entries have ranks re-normalized (1, 2, 3...)
        """
        existing_list = [
            create_draft_list_data(entry_id=1, rank=1, player_id=101),
            create_draft_list_data(entry_id=2, rank=2, player_id=102),
            create_draft_list_data(entry_id=3, rank=3, player_id=103),
        ]
        mock_client.get.return_value = {'count': 3, 'picks': existing_list}
        mock_client.post.return_value = "Inserted 2 list values"

        result = await service.remove_player_from_list(
            season=12, team_id=1, player_id=102  # Remove middle player
        )

        assert result is True

        # Verify POST payload has player removed and ranks adjusted
        post_call = mock_client.post.call_args
        payload = post_call[0][1]

        assert payload['count'] == 2
        player_ids = [e['player_id'] for e in payload['draft_list']]
        assert 102 not in player_ids

        # Verify ranks are re-normalized
        entries = sorted(payload['draft_list'], key=lambda e: e['rank'])
        assert entries[0]['player_id'] == 101
        assert entries[0]['rank'] == 1
        assert entries[1]['player_id'] == 103
        assert entries[1]['rank'] == 2  # Was 3, now 2

    @pytest.mark.asyncio
    async def test_remove_player_not_found(self, service, mock_client):
        """
        Test removing a player who isn't in the list.

        Verifies False is returned and no POST is made.
        """
        existing_list = [
            create_draft_list_data(entry_id=1, rank=1, player_id=101),
        ]
        mock_client.get.return_value = {'count': 1, 'picks': existing_list}

        result = await service.remove_player_from_list(
            season=12, team_id=1, player_id=999  # Not in list
        )

        assert result is False
        mock_client.post.assert_not_called()

    # -------------------------------------------------------------------------
    # clear_list() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_clear_list_success(self, service, mock_client):
        """
        Test clearing entire draft list for a team.

        Verifies DELETE /draftlist/team/{team_id} is called.
        """
        existing_list = [
            create_draft_list_data(entry_id=i, rank=i, player_id=100+i)
            for i in range(1, 6)
        ]
        mock_client.get.return_value = {'count': 5, 'picks': existing_list}
        mock_client.delete.return_value = "Deleted 5 list values"

        result = await service.clear_list(season=12, team_id=1)

        assert result is True
        mock_client.delete.assert_called_once_with('draftlist/team/1')

    @pytest.mark.asyncio
    async def test_clear_list_already_empty(self, service, mock_client):
        """
        Test clearing an already-empty draft list.

        Verifies DELETE is not called when list is already empty.
        """
        mock_client.get.return_value = {'count': 0, 'picks': []}

        result = await service.clear_list(season=12, team_id=1)

        assert result is True
        mock_client.delete.assert_not_called()

    # -------------------------------------------------------------------------
    # reorder_list() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_reorder_list_success(self, service, mock_client):
        """
        Test reordering draft list to a new order.

        Verifies entries are POSTed with new ranks matching specified order.
        """
        existing_list = [
            create_draft_list_data(entry_id=1, rank=1, player_id=101),
            create_draft_list_data(entry_id=2, rank=2, player_id=102),
            create_draft_list_data(entry_id=3, rank=3, player_id=103),
        ]
        mock_client.get.return_value = {'count': 3, 'picks': existing_list}
        mock_client.post.return_value = "Inserted 3 list values"

        # Reverse the order
        new_order = [103, 102, 101]

        result = await service.reorder_list(season=12, team_id=1, new_order=new_order)

        assert result is True

        post_call = mock_client.post.call_args
        payload = post_call[0][1]

        entries_by_player = {e['player_id']: e for e in payload['draft_list']}
        assert entries_by_player[103]['rank'] == 1  # Was 3
        assert entries_by_player[102]['rank'] == 2  # Unchanged
        assert entries_by_player[101]['rank'] == 3  # Was 1

    # -------------------------------------------------------------------------
    # move_entry_up() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_move_entry_up_success(self, service, mock_client):
        """
        Test moving a player up one position (higher priority).

        Verifies the two affected entries swap ranks.
        """
        existing_list = [
            create_draft_list_data(entry_id=1, rank=1, player_id=101),
            create_draft_list_data(entry_id=2, rank=2, player_id=102),
            create_draft_list_data(entry_id=3, rank=3, player_id=103),
        ]
        mock_client.get.return_value = {'count': 3, 'picks': existing_list}
        mock_client.post.return_value = "Inserted 3 list values"

        result = await service.move_entry_up(season=12, team_id=1, player_id=102)

        assert result is True

        post_call = mock_client.post.call_args
        payload = post_call[0][1]

        entries_by_player = {e['player_id']: e for e in payload['draft_list']}
        assert entries_by_player[102]['rank'] == 1  # Moved up from 2
        assert entries_by_player[101]['rank'] == 2  # Moved down from 1
        assert entries_by_player[103]['rank'] == 3  # Unchanged

    @pytest.mark.asyncio
    async def test_move_entry_up_already_at_top(self, service, mock_client):
        """
        Test moving a player who is already at rank 1.

        Verifies False is returned and no POST is made.
        """
        existing_list = [
            create_draft_list_data(entry_id=1, rank=1, player_id=101),
            create_draft_list_data(entry_id=2, rank=2, player_id=102),
        ]
        mock_client.get.return_value = {'count': 2, 'picks': existing_list}

        result = await service.move_entry_up(season=12, team_id=1, player_id=101)

        assert result is False
        mock_client.post.assert_not_called()

    # -------------------------------------------------------------------------
    # move_entry_down() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_move_entry_down_success(self, service, mock_client):
        """
        Test moving a player down one position (lower priority).

        Verifies the two affected entries swap ranks.
        """
        existing_list = [
            create_draft_list_data(entry_id=1, rank=1, player_id=101),
            create_draft_list_data(entry_id=2, rank=2, player_id=102),
            create_draft_list_data(entry_id=3, rank=3, player_id=103),
        ]
        mock_client.get.return_value = {'count': 3, 'picks': existing_list}
        mock_client.post.return_value = "Inserted 3 list values"

        result = await service.move_entry_down(season=12, team_id=1, player_id=102)

        assert result is True

        post_call = mock_client.post.call_args
        payload = post_call[0][1]

        entries_by_player = {e['player_id']: e for e in payload['draft_list']}
        assert entries_by_player[102]['rank'] == 3  # Moved down from 2
        assert entries_by_player[103]['rank'] == 2  # Moved up from 3
        assert entries_by_player[101]['rank'] == 1  # Unchanged

    @pytest.mark.asyncio
    async def test_move_entry_down_already_at_bottom(self, service, mock_client):
        """
        Test moving a player who is already at the bottom.

        Verifies False is returned and no POST is made.
        """
        existing_list = [
            create_draft_list_data(entry_id=1, rank=1, player_id=101),
            create_draft_list_data(entry_id=2, rank=2, player_id=102),
        ]
        mock_client.get.return_value = {'count': 2, 'picks': existing_list}

        result = await service.move_entry_down(season=12, team_id=1, player_id=102)

        assert result is False
        mock_client.post.assert_not_called()


# =============================================================================
# DraftList Response Parsing Tests
# =============================================================================

class TestDraftListResponseParsing:
    """
    Tests for DraftListService response parsing quirks.

    The draftlist GET endpoint returns items under 'picks' key (not 'draftlist'),
    which requires custom parsing logic.
    """

    @pytest.fixture
    def mock_client(self):
        """Create mock API client."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_client):
        """Create DraftListService with mocked client."""
        svc = DraftListService()
        svc._client = mock_client
        return svc

    @pytest.mark.asyncio
    async def test_response_uses_picks_key(self, service, mock_client):
        """
        Test that response with 'picks' key is correctly parsed.

        API quirk: GET /draftlist returns items under 'picks', not 'draftlist'.
        """
        # Response uses 'picks' key
        response_data = {
            'count': 2,
            'picks': [
                create_draft_list_data(entry_id=1, rank=1, player_id=101),
                create_draft_list_data(entry_id=2, rank=2, player_id=102),
            ]
        }
        mock_client.get.return_value = response_data

        result = await service.get_team_list(season=12, team_id=1)

        assert len(result) == 2
        assert all(isinstance(entry, DraftList) for entry in result)


# =============================================================================
# Global Service Instance Tests
# =============================================================================

class TestGlobalServiceInstances:
    """Tests for global service singleton instances."""

    def test_draft_service_instance_exists(self):
        """Verify global draft_service instance is available."""
        assert draft_service is not None
        assert isinstance(draft_service, DraftService)
        assert draft_service.endpoint == 'draftdata'

    def test_draft_pick_service_instance_exists(self):
        """Verify global draft_pick_service instance is available."""
        assert draft_pick_service is not None
        assert isinstance(draft_pick_service, DraftPickService)
        assert draft_pick_service.endpoint == 'draftpicks'

    def test_draft_list_service_instance_exists(self):
        """Verify global draft_list_service instance is available."""
        assert draft_list_service is not None
        assert isinstance(draft_list_service, DraftListService)
        assert draft_list_service.endpoint == 'draftlist'


# =============================================================================
# Draft Model Tests
# =============================================================================

class TestDraftDataModel:
    """Tests for DraftData Pydantic model."""

    def test_create_draft_data(self):
        """Test basic DraftData model creation."""
        data = DraftData(
            id=1,
            currentpick=25,
            timer=True,
            pick_minutes=2
        )
        assert data.currentpick == 25
        assert data.timer is True
        assert data.pick_minutes == 2

    def test_channel_id_string_to_int_conversion(self):
        """
        Test that channel IDs are converted from string to int.

        Database stores channel IDs as strings, model converts to int.
        """
        data = DraftData(
            id=1,
            currentpick=1,
            timer=False,
            pick_minutes=2,
            result_channel='123456789012345678',
            ping_channel='987654321098765432'
        )
        assert data.result_channel == 123456789012345678
        assert data.ping_channel == 987654321098765432

    def test_is_draft_active_property(self):
        """Test is_draft_active property."""
        active = DraftData(id=1, currentpick=1, timer=True, pick_minutes=2)
        inactive = DraftData(id=1, currentpick=1, timer=False, pick_minutes=2)

        assert active.is_draft_active is True
        assert inactive.is_draft_active is False

    def test_is_pick_expired_property(self):
        """Test is_pick_expired property."""
        # Expired deadline
        expired = DraftData(
            id=1, currentpick=1, timer=True, pick_minutes=2,
            pick_deadline=datetime.now() - timedelta(minutes=5)
        )
        assert expired.is_pick_expired is True

        # Future deadline
        not_expired = DraftData(
            id=1, currentpick=1, timer=True, pick_minutes=2,
            pick_deadline=datetime.now() + timedelta(minutes=5)
        )
        assert not_expired.is_pick_expired is False

        # No deadline
        no_deadline = DraftData(id=1, currentpick=1, timer=False, pick_minutes=2)
        assert no_deadline.is_pick_expired is False


class TestDraftPickModel:
    """Tests for DraftPick Pydantic model."""

    def test_create_draft_pick_minimal(self):
        """Test DraftPick with minimal required fields."""
        pick = DraftPick(
            id=1,
            season=12,
            overall=42,
            round=3,
            origowner_id=1
        )
        assert pick.overall == 42
        assert pick.round == 3
        assert pick.player_id is None

    def test_create_draft_pick_with_player(self):
        """Test DraftPick with player selected."""
        pick = DraftPick(
            id=1,
            season=12,
            overall=42,
            round=3,
            origowner_id=1,
            owner_id=1,
            player_id=999
        )
        assert pick.player_id == 999
        assert pick.is_selected is True

    def test_is_traded_property(self):
        """Test is_traded property."""
        traded = DraftPick(
            id=1, season=12, overall=1, round=1,
            origowner_id=1, owner_id=2  # Different owners
        )
        not_traded = DraftPick(
            id=2, season=12, overall=2, round=1,
            origowner_id=1, owner_id=1  # Same owner
        )

        assert traded.is_traded is True
        assert not_traded.is_traded is False

    def test_is_selected_property(self):
        """Test is_selected property."""
        selected = DraftPick(
            id=1, season=12, overall=1, round=1,
            origowner_id=1, player_id=100
        )
        not_selected = DraftPick(
            id=2, season=12, overall=2, round=1,
            origowner_id=1, player_id=None
        )

        assert selected.is_selected is True
        assert not_selected.is_selected is False


class TestDraftListModel:
    """Tests for DraftList Pydantic model."""

    def test_create_draft_list_entry(self):
        """Test DraftList model creation with nested objects."""
        team = Team(**create_team_data(1, 'WV'))
        player = Player(**create_player_data(100, 'Target Player'))

        entry = DraftList(
            id=1,
            season=12,
            rank=1,
            team=team,
            player=player
        )

        assert entry.rank == 1
        assert entry.team_id == 1
        assert entry.player_id == 100

    def test_team_id_property(self):
        """Test team_id property extracts ID from nested team."""
        team = Team(**create_team_data(42, 'TST'))
        player = Player(**create_player_data(100))

        entry = DraftList(id=1, season=12, rank=1, team=team, player=player)

        assert entry.team_id == 42

    def test_player_id_property(self):
        """Test player_id property extracts ID from nested player."""
        team = Team(**create_team_data(1))
        player = Player(**create_player_data(999, 'Star Player'))

        entry = DraftList(id=1, season=12, rank=1, team=team, player=player)

        assert entry.player_id == 999

    def test_is_top_ranked_property(self):
        """Test is_top_ranked property."""
        team = Team(**create_team_data(1))
        player = Player(**create_player_data(100))

        top = DraftList(id=1, season=12, rank=1, team=team, player=player)
        not_top = DraftList(id=2, season=12, rank=5, team=team, player=player)

        assert top.is_top_ranked is True
        assert not_top.is_top_ranked is False
