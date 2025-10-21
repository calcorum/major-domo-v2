"""
Tests for Transaction Freeze/Thaw Tasks in Discord Bot v2.0

Validates the automated weekly freeze system for transactions, including:
- Freeze/thaw scheduling logic
- Contested transaction resolution
- Priority calculation using team standings
- GM notifications
- Transaction processing
"""
import pytest
from datetime import datetime, timezone, UTC
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call
from typing import List

from tasks.transaction_freeze import (
    TransactionFreezeTask,
    resolve_contested_transactions,
    TransactionPriority
)
from models.transaction import Transaction
from models.current import Current
from models.team import Team
from models.player import Player
from models.standings import TeamStandings
from tests.factories import (
    PlayerFactory,
    TeamFactory,
    CurrentFactory
)


@pytest.fixture
def mock_bot():
    """Fixture providing a mock Discord bot."""
    bot = AsyncMock()
    bot.wait_until_ready = AsyncMock()

    # Mock guild
    mock_guild = MagicMock()
    mock_guild.id = 12345
    mock_guild.text_channels = []
    bot.get_guild.return_value = mock_guild

    # Mock application info for owner notifications
    app_info = MagicMock()
    app_info.owner = AsyncMock()
    bot.application_info = AsyncMock(return_value=app_info)

    return bot


@pytest.fixture
def current_state() -> Current:
    """Fixture providing current league state."""
    return CurrentFactory.create(
        week=10,
        season=12,
        freeze=False,
        trade_deadline=14,
        playoffs_begin=19
    )


@pytest.fixture
def frozen_state() -> Current:
    """Fixture providing frozen league state."""
    return CurrentFactory.create(
        week=10,
        season=12,
        freeze=True,
        trade_deadline=14,
        playoffs_begin=19
    )


@pytest.fixture
def sample_team_wv() -> Team:
    """Fixture providing West Virginia team."""
    return TeamFactory.west_virginia(
        id=499,
        gmid=111111,
        gmid2=222222
    )


@pytest.fixture
def sample_team_ny() -> Team:
    """Fixture providing New York team."""
    return TeamFactory.new_york(
        id=500,
        gmid=333333,
        gmid2=None
    )


@pytest.fixture
def sample_player() -> Player:
    """Fixture providing a test player."""
    return PlayerFactory.mike_trout(
        id=12472,
        team_id=None,  # Free agent
        wara=2.5
    )


@pytest.fixture
def sample_transaction(sample_player, sample_team_wv) -> Transaction:
    """Fixture providing a sample transaction."""
    fa_team = TeamFactory.create(
        id=999,
        abbrev="FA",
        sname="Free Agents",
        lname="Free Agents",
        season=12
    )

    return Transaction(
        id=27787,
        week=10,
        season=12,
        moveid='Season-012-Week-10-19-13:04:41',
        player=sample_player,
        oldteam=fa_team,
        newteam=sample_team_wv,
        cancelled=False,
        frozen=True
    )


@pytest.fixture
def contested_transactions(sample_player, sample_team_wv, sample_team_ny) -> List[Transaction]:
    """Fixture providing contested transactions (two teams want same player)."""
    fa_team = TeamFactory.create(
        id=999,
        abbrev="FA",
        sname="Free Agents",
        lname="Free Agents",
        season=12
    )

    # Transaction 1: WV wants the player
    tx1 = Transaction(
        id=27787,
        week=10,
        season=12,
        moveid='Season-012-Week-10-WV-13:04:41',
        player=sample_player,
        oldteam=fa_team,
        newteam=sample_team_wv,
        cancelled=False,
        frozen=True
    )

    # Transaction 2: NY wants the same player
    tx2 = Transaction(
        id=27788,
        week=10,
        season=12,
        moveid='Season-012-Week-10-NY-13:05:00',
        player=sample_player,
        oldteam=fa_team,
        newteam=sample_team_ny,
        cancelled=False,
        frozen=True
    )

    return [tx1, tx2]


@pytest.fixture
def mil_transaction(sample_player, sample_team_wv) -> Transaction:
    """Fixture providing a MiL team transaction."""
    fa_team = TeamFactory.create(
        id=999,
        abbrev="FA",
        sname="Free Agents",
        lname="Free Agents",
        season=12
    )

    mil_team = TeamFactory.create(
        id=501,
        abbrev="WVMiL",
        sname="Black Bears MiL",
        lname="West Virginia Black Bears MiL",
        season=12
    )

    return Transaction(
        id=27789,
        week=10,
        season=12,
        moveid='Season-012-Week-10-WVMiL-14:00:00',
        player=sample_player,
        oldteam=fa_team,
        newteam=mil_team,
        cancelled=False,
        frozen=True
    )


@pytest.fixture
def sample_standings_wv() -> TeamStandings:
    """Fixture providing standings for WV (bad team - higher priority)."""
    # Create a minimal team for standings
    team_wv = TeamFactory.west_virginia(id=499)

    return TeamStandings(
        id=1,
        team=team_wv,
        wins=30,
        losses=70,
        run_diff=-200,
        div_gb=None,
        div_e_num=None,
        wc_gb=None,
        wc_e_num=None,
        home_wins=15,
        home_losses=35,
        away_wins=15,
        away_losses=35,
        last8_wins=2,
        last8_losses=6,
        streak_wl="l",
        streak_num=3,
        one_run_wins=8,
        one_run_losses=12,
        pythag_wins=28,
        pythag_losses=72,
        div1_wins=8,
        div1_losses=12,
        div2_wins=7,
        div2_losses=13,
        div3_wins=8,
        div3_losses=12,
        div4_wins=7,
        div4_losses=13
    )


@pytest.fixture
def sample_standings_ny() -> TeamStandings:
    """Fixture providing standings for NY (good team - lower priority)."""
    # Create a minimal team for standings
    team_ny = TeamFactory.new_york(id=500)

    return TeamStandings(
        id=2,
        team=team_ny,
        wins=70,
        losses=30,
        run_diff=200,
        div_gb=None,
        div_e_num=None,
        wc_gb=None,
        wc_e_num=None,
        home_wins=35,
        home_losses=15,
        away_wins=35,
        away_losses=15,
        last8_wins=6,
        last8_losses=2,
        streak_wl="w",
        streak_num=4,
        one_run_wins=12,
        one_run_losses=8,
        pythag_wins=72,
        pythag_losses=28,
        div1_wins=12,
        div1_losses=8,
        div2_wins=13,
        div2_losses=7,
        div3_wins=12,
        div3_losses=8,
        div4_wins=13,
        div4_losses=7
    )


class TestTransactionPriority:
    """Test TransactionPriority data class."""

    def test_priority_initialization(self, sample_transaction):
        """Test TransactionPriority initialization."""
        priority = TransactionPriority(
            transaction=sample_transaction,
            team_win_percentage=0.500,
            tiebreaker=0.50012345
        )

        assert priority.transaction == sample_transaction
        assert priority.team_win_percentage == 0.500
        assert priority.tiebreaker == 0.50012345

    def test_priority_sorting_by_tiebreaker(self, sample_transaction):
        """Test that priorities sort correctly by tiebreaker (lowest first)."""
        priority1 = TransactionPriority(
            transaction=sample_transaction,
            team_win_percentage=0.300,
            tiebreaker=0.30012345
        )

        priority2 = TransactionPriority(
            transaction=sample_transaction,
            team_win_percentage=0.700,
            tiebreaker=0.70012345
        )

        priorities = [priority2, priority1]
        priorities.sort()

        # Lower tiebreaker should come first (worst teams get priority)
        assert priorities[0].tiebreaker == 0.30012345
        assert priorities[1].tiebreaker == 0.70012345

    def test_priority_comparison(self, sample_transaction):
        """Test priority comparison operators."""
        priority_low = TransactionPriority(
            transaction=sample_transaction,
            team_win_percentage=0.300,
            tiebreaker=0.300
        )

        priority_high = TransactionPriority(
            transaction=sample_transaction,
            team_win_percentage=0.700,
            tiebreaker=0.700
        )

        assert priority_low < priority_high
        assert not priority_high < priority_low


class TestResolveContestedTransactions:
    """Test resolve_contested_transactions function."""

    @pytest.mark.asyncio
    async def test_no_contested_transactions(self, sample_transaction):
        """Test with no contested transactions (single team wants player)."""
        transactions = [sample_transaction]

        with patch('tasks.transaction_freeze.standings_service') as mock_standings:
            mock_standings.get_team_standings = AsyncMock(return_value=None)

            winning_ids, losing_ids = await resolve_contested_transactions(transactions, 12)

            # Single transaction should win automatically
            assert sample_transaction.moveid in winning_ids
            assert len(losing_ids) == 0

    @pytest.mark.asyncio
    async def test_contested_transaction_resolution(
        self,
        contested_transactions,
        sample_standings_wv,
        sample_standings_ny
    ):
        """Test contested transaction resolution with priority."""
        with patch('tasks.transaction_freeze.standings_service') as mock_standings:
            async def get_standings(team_abbrev, season):
                if team_abbrev == "WV":
                    return sample_standings_wv  # 0.300 win%
                elif team_abbrev == "NY":
                    return sample_standings_ny  # 0.700 win%
                return None

            mock_standings.get_team_standings = AsyncMock(side_effect=get_standings)

            # Mock random for deterministic testing
            with patch('tasks.transaction_freeze.random.randint', return_value=50000):
                winning_ids, losing_ids = await resolve_contested_transactions(
                    contested_transactions, 12
                )

                # WV should win (lower win% = higher priority)
                assert len(winning_ids) == 1
                assert len(losing_ids) == 1

                # Find which transaction won
                wv_tx = next(tx for tx in contested_transactions if tx.newteam.abbrev == "WV")
                ny_tx = next(tx for tx in contested_transactions if tx.newteam.abbrev == "NY")

                assert wv_tx.moveid in winning_ids
                assert ny_tx.moveid in losing_ids

    @pytest.mark.asyncio
    async def test_mil_team_uses_parent_standings(self, sample_player, sample_standings_wv):
        """Test that MiL team transactions use parent ML team standings."""
        # Create MiL team transaction that WILL be contested
        fa_team = TeamFactory.create(
            id=999,
            abbrev="FA",
            sname="Free Agents",
            lname="Free Agents",
            season=12
        )

        mil_team = TeamFactory.create(
            id=501,
            abbrev="WVMiL",
            sname="Black Bears MiL",
            lname="West Virginia Black Bears MiL",
            season=12
        )

        # Create TWO transactions for the same player to trigger contest resolution
        mil_transaction = Transaction(
            id=27789,
            week=10,
            season=12,
            moveid='Season-012-Week-10-WVMiL-14:00:00',
            player=sample_player,
            oldteam=fa_team,
            newteam=mil_team,
            cancelled=False,
            frozen=True
        )

        # Second transaction to create a contest
        ny_team = TeamFactory.new_york(id=500)
        ny_transaction = Transaction(
            id=27790,
            week=10,
            season=12,
            moveid='Season-012-Week-10-NY-14:01:00',
            player=sample_player,
            oldteam=fa_team,
            newteam=ny_team,
            cancelled=False,
            frozen=True
        )

        transactions = [mil_transaction, ny_transaction]

        with patch('tasks.transaction_freeze.standings_service') as mock_standings:
            # Should request standings for "WV" (parent), not "WVMiL"
            mock_standings.get_team_standings = AsyncMock(return_value=sample_standings_wv)

            # Mock random for deterministic testing
            with patch('tasks.transaction_freeze.random.randint', return_value=50000):
                winning_ids, losing_ids = await resolve_contested_transactions(transactions, 12)

                # Should have called with "WV" (stripped "MiL" suffix)
                # Will be called twice (once for WVMiL, once for NY)
                calls = mock_standings.get_team_standings.call_args_list
                assert any(call[0] == ("WV", 12) for call in calls), \
                    f"Expected call with ('WV', 12), got {calls}"

                # Should have resolved (one winner, one loser)
                assert len(winning_ids) == 1
                assert len(losing_ids) == 1

    @pytest.mark.asyncio
    async def test_fa_drops_not_contested(self, sample_player, sample_team_wv):
        """Test that FA drops are not considered for contests."""
        fa_team = TeamFactory.create(
            id=999,
            abbrev="FA",
            sname="Free Agents",
            lname="Free Agents",
            season=12
        )

        # Drop to FA (not an acquisition)
        drop_tx = Transaction(
            id=27790,
            week=10,
            season=12,
            moveid='Season-012-Week-10-DROP-15:00:00',
            player=sample_player,
            oldteam=sample_team_wv,
            newteam=fa_team,  # Dropping to FA
            cancelled=False,
            frozen=True
        )

        transactions = [drop_tx]

        winning_ids, losing_ids = await resolve_contested_transactions(transactions, 12)

        # FA drops are not winners or losers (they're not acquisitions)
        assert len(winning_ids) == 0
        assert len(losing_ids) == 0

    @pytest.mark.asyncio
    async def test_standings_error_fallback(self, contested_transactions):
        """Test that standings errors result in 0.0 priority."""
        with patch('tasks.transaction_freeze.standings_service') as mock_standings:
            # Simulate standings service error
            mock_standings.get_team_standings = AsyncMock(side_effect=Exception("API Error"))

            # Mock random for deterministic testing
            with patch('tasks.transaction_freeze.random.randint', return_value=50000):
                winning_ids, losing_ids = await resolve_contested_transactions(
                    contested_transactions, 12
                )

                # Should still resolve (one wins, one loses)
                assert len(winning_ids) == 1
                assert len(losing_ids) == 1

    @pytest.mark.asyncio
    async def test_three_way_contest(self, sample_player):
        """Test contest with three teams wanting same player."""
        fa_team = TeamFactory.create(
            id=999,
            abbrev="FA",
            sname="Free Agents",
            lname="Free Agents",
            season=12
        )

        team1 = TeamFactory.create(id=1, abbrev="T1", sname="Team 1", lname="Team 1", season=12)
        team2 = TeamFactory.create(id=2, abbrev="T2", sname="Team 2", lname="Team 2", season=12)
        team3 = TeamFactory.create(id=3, abbrev="T3", sname="Team 3", lname="Team 3", season=12)

        tx1 = Transaction(
            id=1, week=10, season=12, moveid='move-1', player=sample_player,
            oldteam=fa_team, newteam=team1, cancelled=False, frozen=True
        )
        tx2 = Transaction(
            id=2, week=10, season=12, moveid='move-2', player=sample_player,
            oldteam=fa_team, newteam=team2, cancelled=False, frozen=True
        )
        tx3 = Transaction(
            id=3, week=10, season=12, moveid='move-3', player=sample_player,
            oldteam=fa_team, newteam=team3, cancelled=False, frozen=True
        )

        transactions = [tx1, tx2, tx3]

        with patch('tasks.transaction_freeze.standings_service') as mock_standings:
            async def get_standings(team_abbrev, season):
                # Create minimal team objects for standings
                standings_map = {
                    "T1": TeamStandings(
                        id=1, team=team1, wins=20, losses=80, run_diff=0,
                        home_wins=10, home_losses=40, away_wins=10, away_losses=40,
                        last8_wins=1, last8_losses=7, streak_wl="l", streak_num=5,
                        one_run_wins=5, one_run_losses=10, pythag_wins=22, pythag_losses=78,
                        div1_wins=5, div1_losses=15, div2_wins=5, div2_losses=15,
                        div3_wins=5, div3_losses=15, div4_wins=5, div4_losses=15
                    ),
                    "T2": TeamStandings(
                        id=2, team=team2, wins=50, losses=50, run_diff=0,
                        home_wins=25, home_losses=25, away_wins=25, away_losses=25,
                        last8_wins=4, last8_losses=4, streak_wl="w", streak_num=2,
                        one_run_wins=10, one_run_losses=10, pythag_wins=50, pythag_losses=50,
                        div1_wins=12, div1_losses=13, div2_wins=13, div2_losses=12,
                        div3_wins=12, div3_losses=13, div4_wins=13, div4_losses=12
                    ),
                    "T3": TeamStandings(
                        id=3, team=team3, wins=80, losses=20, run_diff=0,
                        home_wins=40, home_losses=10, away_wins=40, away_losses=10,
                        last8_wins=7, last8_losses=1, streak_wl="w", streak_num=8,
                        one_run_wins=15, one_run_losses=5, pythag_wins=78, pythag_losses=22,
                        div1_wins=20, div1_losses=5, div2_wins=20, div2_losses=5,
                        div3_wins=20, div3_losses=5, div4_wins=20, div4_losses=5
                    ),
                }
                return standings_map.get(team_abbrev)

            mock_standings.get_team_standings = AsyncMock(side_effect=get_standings)

            with patch('tasks.transaction_freeze.random.randint', return_value=50000):
                winning_ids, losing_ids = await resolve_contested_transactions(transactions, 12)

                # Only one winner
                assert len(winning_ids) == 1
                # Two losers
                assert len(losing_ids) == 2

                # T1 should win (worst record = 0.200)
                assert tx1.moveid in winning_ids
                assert tx2.moveid in losing_ids
                assert tx3.moveid in losing_ids


class TestTransactionFreezeTaskInitialization:
    """Test TransactionFreezeTask initialization and setup."""

    def test_task_initialization(self, mock_bot):
        """Test task initialization."""
        with patch.object(TransactionFreezeTask, 'weekly_loop') as mock_loop:
            task = TransactionFreezeTask(mock_bot)

            assert task.bot == mock_bot
            assert task.logger is not None
            assert task.weekly_warning_sent is False
            mock_loop.start.assert_called_once()

    def test_cog_unload(self, mock_bot):
        """Test that cog_unload cancels the task."""
        with patch.object(TransactionFreezeTask, 'weekly_loop') as mock_loop:
            task = TransactionFreezeTask(mock_bot)

            task.cog_unload()

            mock_loop.cancel.assert_called_once()


class TestFreezeBeginLogic:
    """Test freeze begin logic."""

    @pytest.mark.asyncio
    async def test_begin_freeze_increments_week(self, mock_bot, current_state):
        """Test that freeze begin increments week and sets freeze flag."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            with patch('tasks.transaction_freeze.league_service') as mock_league:
                # Mock the update call
                updated_state = CurrentFactory.create(
                    week=11,  # Incremented
                    season=12,
                    freeze=True  # Set to True
                )
                mock_league.update_current_state = AsyncMock(return_value=updated_state)

                # Mock other methods
                task._run_transactions = AsyncMock()
                task._send_freeze_announcement = AsyncMock()
                task._post_weekly_info = AsyncMock()

                await task._begin_freeze(current_state)

                # Verify week was incremented and freeze set
                mock_league.update_current_state.assert_called_once_with(
                    week=11,
                    freeze=True
                )

                # Verify freeze announcement was sent
                task._send_freeze_announcement.assert_called_once_with(11, is_beginning=True)

    @pytest.mark.asyncio
    async def test_begin_freeze_runs_transactions(self, mock_bot, current_state):
        """Test that freeze begin runs regular transactions."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            with patch('tasks.transaction_freeze.league_service') as mock_league:
                updated_state = CurrentFactory.create(week=11, season=12, freeze=True)
                mock_league.update_current_state = AsyncMock(return_value=updated_state)

                task._run_transactions = AsyncMock()
                task._send_freeze_announcement = AsyncMock()
                task._post_weekly_info = AsyncMock()

                await task._begin_freeze(current_state)

                # Verify transactions were run
                task._run_transactions.assert_called_once()

    @pytest.mark.asyncio
    async def test_begin_freeze_posts_weekly_info_weeks_1_18(self, mock_bot, current_state):
        """Test that weekly info is posted for weeks 1-18."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            with patch('tasks.transaction_freeze.league_service') as mock_league:
                # Week 5 (within 1-18 range)
                updated_state = CurrentFactory.create(week=5, season=12, freeze=True)
                mock_league.update_current_state = AsyncMock(return_value=updated_state)

                task._run_transactions = AsyncMock()
                task._send_freeze_announcement = AsyncMock()
                task._post_weekly_info = AsyncMock()

                current_state.week = 4  # Starting at week 4
                await task._begin_freeze(current_state)

                # Verify weekly info was posted
                task._post_weekly_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_begin_freeze_skips_weekly_info_after_week_18(self, mock_bot, current_state):
        """Test that weekly info is NOT posted after week 18."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            with patch('tasks.transaction_freeze.league_service') as mock_league:
                # Week 19 (playoffs)
                updated_state = CurrentFactory.create(week=19, season=12, freeze=True)
                mock_league.update_current_state = AsyncMock(return_value=updated_state)

                task._run_transactions = AsyncMock()
                task._send_freeze_announcement = AsyncMock()
                task._post_weekly_info = AsyncMock()

                current_state.week = 18  # Starting at week 18
                await task._begin_freeze(current_state)

                # Verify weekly info was NOT posted
                task._post_weekly_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_begin_freeze_error_handling(self, mock_bot, current_state):
        """Test that errors in freeze begin are raised."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            with patch('tasks.transaction_freeze.league_service') as mock_league:
                mock_league.update_current_state = AsyncMock(
                    side_effect=Exception("Database error")
                )

                # Patch logger to avoid exc_info conflict
                with patch.object(task.logger, 'error'):
                    with pytest.raises(Exception, match="Database error"):
                        await task._begin_freeze(current_state)


class TestFreezeEndLogic:
    """Test freeze end logic."""

    @pytest.mark.asyncio
    async def test_end_freeze_processes_transactions(self, mock_bot, frozen_state):
        """Test that freeze end processes frozen transactions."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            with patch('tasks.transaction_freeze.league_service') as mock_league:
                updated_state = CurrentFactory.create(week=10, season=12, freeze=False)
                mock_league.update_current_state = AsyncMock(return_value=updated_state)

                task._process_frozen_transactions = AsyncMock()
                task._send_freeze_announcement = AsyncMock()

                await task._end_freeze(frozen_state)

                # Verify transactions were processed
                task._process_frozen_transactions.assert_called_once_with(frozen_state)

    @pytest.mark.asyncio
    async def test_end_freeze_sets_freeze_false(self, mock_bot, frozen_state):
        """Test that freeze end sets freeze flag to False."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            with patch('tasks.transaction_freeze.league_service') as mock_league:
                updated_state = CurrentFactory.create(week=10, season=12, freeze=False)
                mock_league.update_current_state = AsyncMock(return_value=updated_state)

                task._process_frozen_transactions = AsyncMock()
                task._send_freeze_announcement = AsyncMock()

                await task._end_freeze(frozen_state)

                # Verify freeze was set to False
                mock_league.update_current_state.assert_called_once_with(freeze=False)

    @pytest.mark.asyncio
    async def test_end_freeze_sends_announcement(self, mock_bot, frozen_state):
        """Test that freeze end sends thaw announcement."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            with patch('tasks.transaction_freeze.league_service') as mock_league:
                updated_state = CurrentFactory.create(week=10, season=12, freeze=False)
                mock_league.update_current_state = AsyncMock(return_value=updated_state)

                task._process_frozen_transactions = AsyncMock()
                task._send_freeze_announcement = AsyncMock()

                await task._end_freeze(frozen_state)

                # Verify thaw announcement was sent
                task._send_freeze_announcement.assert_called_once_with(10, is_beginning=False)

    @pytest.mark.asyncio
    async def test_end_freeze_error_handling(self, mock_bot, frozen_state):
        """Test that errors in freeze end are raised."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            with patch('tasks.transaction_freeze.league_service') as mock_league:
                mock_league.update_current_state = AsyncMock(
                    side_effect=Exception("Database error")
                )

                task._process_frozen_transactions = AsyncMock()

                # Patch logger to avoid exc_info conflict
                with patch.object(task.logger, 'error'):
                    with pytest.raises(Exception, match="Database error"):
                        await task._end_freeze(frozen_state)


class TestProcessFrozenTransactions:
    """Test frozen transaction processing."""

    @pytest.mark.asyncio
    async def test_process_frozen_transactions_basic(
        self,
        mock_bot,
        frozen_state,
        sample_transaction
    ):
        """Test basic frozen transaction processing."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            with patch('tasks.transaction_freeze.transaction_service') as mock_tx_service:
                mock_tx_service.get_frozen_transactions_by_week = AsyncMock(
                    return_value=[sample_transaction]
                )
                mock_tx_service.unfreeze_transaction = AsyncMock(return_value=True)

                with patch('tasks.transaction_freeze.resolve_contested_transactions') as mock_resolve:
                    mock_resolve.return_value = ([sample_transaction.moveid], [])

                    task._post_transaction_to_log = AsyncMock()

                    await task._process_frozen_transactions(frozen_state)

                    # Verify transaction was unfrozen
                    mock_tx_service.unfreeze_transaction.assert_called_once_with(
                        sample_transaction.id
                    )

                    # Verify transaction was posted to log
                    task._post_transaction_to_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_frozen_transactions_with_cancellations(
        self,
        mock_bot,
        frozen_state,
        contested_transactions
    ):
        """Test processing with contested transactions and cancellations."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            tx1, tx2 = contested_transactions

            with patch('tasks.transaction_freeze.transaction_service') as mock_tx_service:
                mock_tx_service.get_frozen_transactions_by_week = AsyncMock(
                    return_value=contested_transactions
                )
                mock_tx_service.cancel_transaction = AsyncMock(return_value=True)
                mock_tx_service.unfreeze_transaction = AsyncMock(return_value=True)

                with patch('tasks.transaction_freeze.resolve_contested_transactions') as mock_resolve:
                    # tx1 wins, tx2 loses
                    mock_resolve.return_value = ([tx1.moveid], [tx2.moveid])

                    task._post_transaction_to_log = AsyncMock()
                    task._notify_gm_of_cancellation = AsyncMock()

                    await task._process_frozen_transactions(frozen_state)

                    # Verify losing transaction was cancelled
                    mock_tx_service.cancel_transaction.assert_called_once_with(str(tx2.id))

                    # Verify GM was notified
                    task._notify_gm_of_cancellation.assert_called_once()

                    # Verify winning transaction was unfrozen
                    mock_tx_service.unfreeze_transaction.assert_called_once_with(tx1.id)

    @pytest.mark.asyncio
    async def test_process_frozen_no_transactions(self, mock_bot, frozen_state):
        """Test processing when no frozen transactions exist."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            with patch('tasks.transaction_freeze.transaction_service') as mock_tx_service:
                mock_tx_service.get_frozen_transactions_by_week = AsyncMock(return_value=None)

                # Should not raise error
                await task._process_frozen_transactions(frozen_state)

    @pytest.mark.asyncio
    async def test_process_frozen_transaction_error_recovery(
        self,
        mock_bot,
        frozen_state,
        sample_transaction
    ):
        """Test that processing continues despite individual transaction errors."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            with patch('tasks.transaction_freeze.transaction_service') as mock_tx_service:
                mock_tx_service.get_frozen_transactions_by_week = AsyncMock(
                    return_value=[sample_transaction]
                )
                # Simulate unfreeze failure
                mock_tx_service.unfreeze_transaction = AsyncMock(return_value=False)

                with patch('tasks.transaction_freeze.resolve_contested_transactions') as mock_resolve:
                    mock_resolve.return_value = ([sample_transaction.moveid], [])

                    task._post_transaction_to_log = AsyncMock()

                    # Should not raise error
                    await task._process_frozen_transactions(frozen_state)

                    # Post should still be attempted
                    task._post_transaction_to_log.assert_called_once()


class TestNotificationsAndEmbeds:
    """Test notification and embed creation."""

    @pytest.mark.asyncio
    async def test_send_freeze_announcement_begin(self, mock_bot, current_state):
        """Test freeze begin announcement."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            # Mock guild and channel
            mock_guild = MagicMock()
            mock_channel = AsyncMock()
            mock_guild.text_channels = [mock_channel]
            mock_channel.name = 'transaction-log'

            with patch('tasks.transaction_freeze.get_config') as mock_config:
                config = MagicMock()
                config.guild_id = 12345
                mock_config.return_value = config

                with patch('tasks.transaction_freeze.discord.utils.get', return_value=mock_channel):
                    task.bot.get_guild.return_value = mock_guild

                    await task._send_freeze_announcement(10, is_beginning=True)

                    # Verify message was sent
                    mock_channel.send.assert_called_once()

                    # Verify message content
                    call_args = mock_channel.send.call_args
                    message = call_args[0][0] if call_args[0] else call_args[1]['content']
                    assert 'Week 10' in message
                    assert 'Freeze Period Begins' in message

    @pytest.mark.asyncio
    async def test_send_freeze_announcement_end(self, mock_bot, current_state):
        """Test freeze end (thaw) announcement."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            mock_guild = MagicMock()
            mock_channel = AsyncMock()
            mock_guild.text_channels = [mock_channel]
            mock_channel.name = 'transaction-log'

            with patch('tasks.transaction_freeze.get_config') as mock_config:
                config = MagicMock()
                config.guild_id = 12345
                mock_config.return_value = config

                with patch('tasks.transaction_freeze.discord.utils.get', return_value=mock_channel):
                    task.bot.get_guild.return_value = mock_guild

                    await task._send_freeze_announcement(10, is_beginning=False)

                    # Verify message was sent
                    mock_channel.send.assert_called_once()

                    # Verify message content
                    call_args = mock_channel.send.call_args
                    message = call_args[0][0] if call_args[0] else call_args[1]['content']
                    assert 'Week 10' in message
                    assert 'Freeze Period Ends' in message

    @pytest.mark.asyncio
    async def test_notify_gm_of_cancellation(
        self,
        mock_bot,
        sample_transaction,
        sample_team_wv
    ):
        """Test GM notification of cancelled transaction."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            # Mock guild members
            mock_guild = MagicMock()
            mock_gm1 = AsyncMock()
            mock_gm2 = AsyncMock()

            mock_guild.get_member.side_effect = lambda id: {
                111111: mock_gm1,
                222222: mock_gm2
            }.get(id)

            with patch('tasks.transaction_freeze.get_config') as mock_config:
                config = MagicMock()
                config.guild_id = 12345
                mock_config.return_value = config

                task.bot.get_guild.return_value = mock_guild

                await task._notify_gm_of_cancellation(sample_transaction, sample_team_wv)

                # Verify both GMs were sent messages
                mock_gm1.send.assert_called_once()
                mock_gm2.send.assert_called_once()

                # Verify message content
                message = mock_gm1.send.call_args[0][0]
                assert sample_transaction.player.name in message
                assert 'cancelled' in message.lower()


class TestOffseasonMode:
    """Test offseason mode behavior."""

    @pytest.mark.asyncio
    async def test_weekly_loop_skips_during_offseason(self, mock_bot, current_state):
        """Test that weekly loop skips operations when offseason_flag is True."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            with patch('tasks.transaction_freeze.get_config') as mock_config:
                config = MagicMock()
                config.offseason_flag = True  # Offseason enabled
                mock_config.return_value = config

                with patch('tasks.transaction_freeze.league_service') as mock_league:
                    mock_league.get_current_state = AsyncMock(return_value=current_state)

                    task._begin_freeze = AsyncMock()
                    task._end_freeze = AsyncMock()

                    # Manually call the loop logic
                    await task.weekly_loop()

                    # Verify no freeze/thaw operations occurred
                    task._begin_freeze.assert_not_called()
                    task._end_freeze.assert_not_called()


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery."""

    @pytest.mark.asyncio
    async def test_weekly_loop_error_sends_owner_notification(self, mock_bot):
        """Test that weekly loop errors send owner notifications."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            with patch('tasks.transaction_freeze.get_config') as mock_config:
                config = MagicMock()
                config.offseason_flag = False
                mock_config.return_value = config

                with patch('tasks.transaction_freeze.league_service') as mock_league:
                    # Simulate error getting current state
                    mock_league.get_current_state = AsyncMock(
                        side_effect=Exception("Database connection failed")
                    )

                    task._send_owner_notification = AsyncMock()

                    # Manually call the loop logic
                    await task.weekly_loop()

                    # Verify owner was notified
                    task._send_owner_notification.assert_called_once()

                    # Verify warning flag was set
                    assert task.weekly_warning_sent is True

    @pytest.mark.asyncio
    async def test_owner_notification_prevents_duplicates(self, mock_bot):
        """Test that duplicate owner notifications are prevented."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)
            task.weekly_warning_sent = True  # Already sent

            with patch('tasks.transaction_freeze.get_config') as mock_config:
                config = MagicMock()
                config.offseason_flag = False
                mock_config.return_value = config

                with patch('tasks.transaction_freeze.league_service') as mock_league:
                    mock_league.get_current_state = AsyncMock(
                        side_effect=Exception("Another error")
                    )

                    task._send_owner_notification = AsyncMock()

                    await task.weekly_loop()

                    # Verify owner was NOT notified again
                    task._send_owner_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_owner_notification(self, mock_bot):
        """Test sending owner notification."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            await task._send_owner_notification("Test error message")

            # Verify application_info was called
            mock_bot.application_info.assert_called_once()

            # Verify owner was sent message
            app_info = await mock_bot.application_info()
            app_info.owner.send.assert_called_once_with("Test error message")


class TestWeeklyScheduleTiming:
    """Test weekly schedule timing logic."""

    @pytest.mark.asyncio
    async def test_freeze_triggers_monday_midnight(self, mock_bot, current_state):
        """Test that freeze triggers on Monday at 00:00."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            # Mock datetime to be Monday (weekday=0) at 00:00
            mock_now = MagicMock()
            mock_now.weekday.return_value = 0  # Monday
            mock_now.hour = 0

            with patch('tasks.transaction_freeze.datetime') as mock_datetime:
                mock_datetime.now.return_value = mock_now

                with patch('tasks.transaction_freeze.get_config') as mock_config:
                    config = MagicMock()
                    config.offseason_flag = False
                    mock_config.return_value = config

                    with patch('tasks.transaction_freeze.league_service') as mock_league:
                        mock_league.get_current_state = AsyncMock(return_value=current_state)

                        task._begin_freeze = AsyncMock()
                        task._end_freeze = AsyncMock()

                        await task.weekly_loop()

                        # Verify freeze began
                        task._begin_freeze.assert_called_once_with(current_state)
                        task._end_freeze.assert_not_called()

    @pytest.mark.asyncio
    async def test_thaw_triggers_saturday_midnight(self, mock_bot, frozen_state):
        """Test that thaw triggers on Saturday at 00:00."""
        with patch.object(TransactionFreezeTask, 'weekly_loop'):
            task = TransactionFreezeTask(mock_bot)

            # Mock datetime to be Saturday (weekday=5) at 00:00
            mock_now = MagicMock()
            mock_now.weekday.return_value = 5  # Saturday
            mock_now.hour = 0

            with patch('tasks.transaction_freeze.datetime') as mock_datetime:
                mock_datetime.now.return_value = mock_now

                with patch('tasks.transaction_freeze.get_config') as mock_config:
                    config = MagicMock()
                    config.offseason_flag = False
                    mock_config.return_value = config

                    with patch('tasks.transaction_freeze.league_service') as mock_league:
                        mock_league.get_current_state = AsyncMock(return_value=frozen_state)

                        task._begin_freeze = AsyncMock()
                        task._end_freeze = AsyncMock()

                        await task.weekly_loop()

                        # Verify freeze ended
                        task._end_freeze.assert_called_once_with(frozen_state)
                        task._begin_freeze.assert_not_called()
