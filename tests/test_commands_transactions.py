"""
Tests for Transaction Commands (Discord interactions)

Validates Discord command functionality, embed creation, and user interaction flows.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord

from commands.transactions.management import TransactionCommands
from models.transaction import Transaction, RosterValidation
from models.team import Team
from models.roster import TeamRoster
from exceptions import APIException


class TestTransactionCommands:
    """Test TransactionCommands Discord command functionality."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create mock Discord bot."""
        bot = MagicMock()
        bot.user = MagicMock()
        bot.user.id = 123456789
        return bot
    
    @pytest.fixture
    def commands_cog(self, mock_bot):
        """Create TransactionCommands cog instance."""
        return TransactionCommands(mock_bot)
    
    @pytest.fixture
    def mock_interaction(self):
        """Create mock Discord interaction."""
        interaction = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 258104532423147520  # Test user ID
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        # Guild mock required for @league_only decorator
        interaction.guild = MagicMock()
        interaction.guild.id = 669356687294988350  # SBA league server ID from config
        return interaction
    
    @pytest.fixture
    def mock_team(self):
        """Create mock team data."""
        return Team.from_api_data({
            'id': 499,
            'abbrev': 'WV',
            'sname': 'Black Bears',
            'lname': 'West Virginia Black Bears',
            'season': 13,
            'thumbnail': 'https://example.com/thumbnail.png'
        })
    
    @pytest.fixture
    def mock_transactions(self):
        """Create mock transaction list."""
        base_data = {
            'season': 13,
            'player': {
                'id': 12472,
                'name': 'Test Player',
                'wara': 2.47,
                'season': 13,
                'pos_1': 'LF'
            },
            'oldteam': {
                'id': 508,
                'abbrev': 'NYD',
                'sname': 'Diamonds',
                'lname': 'New York Diamonds',
                'season': 13
            },
            'newteam': {
                'id': 499,
                'abbrev': 'WV',
                'sname': 'Black Bears',
                'lname': 'West Virginia Black Bears',
                'season': 13
            }
        }
        
        return [
            Transaction.from_api_data({
                **base_data,
                'id': 1,
                'week': 10,
                'moveid': 'move1',
                'cancelled': False,
                'frozen': False
            }),
            Transaction.from_api_data({
                **base_data,
                'id': 2,
                'week': 11,
                'moveid': 'move2',
                'cancelled': False,
                'frozen': True
            }),
            Transaction.from_api_data({
                **base_data,
                'id': 3,
                'week': 9,
                'moveid': 'move3',
                'cancelled': True,
                'frozen': False
            })
        ]
    
    @pytest.mark.asyncio
    async def test_my_moves_success(self, commands_cog, mock_interaction, mock_team, mock_transactions):
        """Test successful /mymoves command execution."""
        pending_tx = [tx for tx in mock_transactions if tx.is_pending]
        frozen_tx = [tx for tx in mock_transactions if tx.is_frozen]
        cancelled_tx = [tx for tx in mock_transactions if tx.is_cancelled]

        with patch('utils.permissions.get_user_team') as mock_get_user_team:
            with patch('commands.transactions.management.get_user_major_league_team') as mock_get_ml_team:
                with patch('commands.transactions.management.transaction_service') as mock_tx_service:

                    # Mock service responses - @requires_team decorator
                    mock_get_user_team.return_value = mock_team
                    # Mock for the command itself
                    mock_get_ml_team.return_value = mock_team
                    mock_tx_service.get_pending_transactions = AsyncMock(return_value=pending_tx)
                    mock_tx_service.get_frozen_transactions = AsyncMock(return_value=frozen_tx)
                    mock_tx_service.get_processed_transactions = AsyncMock(return_value=[])

                    # Execute command
                    await commands_cog.my_moves.callback(commands_cog, mock_interaction, show_cancelled=False)

                    # Verify interaction flow
                    mock_interaction.response.defer.assert_called_once()
                    mock_interaction.followup.send.assert_called_once()

                    # Verify service calls
                    mock_tx_service.get_pending_transactions.assert_called_once_with('WV', 13)
                    mock_tx_service.get_frozen_transactions.assert_called_once_with('WV', 13)
                    mock_tx_service.get_processed_transactions.assert_called_once_with('WV', 13)

                    # Check embed was sent
                    embed_call = mock_interaction.followup.send.call_args
                    assert 'embed' in embed_call.kwargs
    
    @pytest.mark.asyncio
    async def test_my_moves_with_cancelled(self, commands_cog, mock_interaction, mock_team, mock_transactions):
        """Test /mymoves command with cancelled transactions shown."""
        cancelled_tx = [tx for tx in mock_transactions if tx.is_cancelled]

        with patch('utils.permissions.get_user_team') as mock_get_user_team:
            with patch('commands.transactions.management.get_user_major_league_team') as mock_get_ml_team:
                with patch('commands.transactions.management.transaction_service') as mock_tx_service:

                    # Mock decorator lookup - @requires_team
                    mock_get_user_team.return_value = {
                        'id': mock_team.id, 'name': mock_team.lname,
                        'abbrev': mock_team.abbrev, 'season': mock_team.season
                    }
                    # Mock command's team lookup
                    mock_get_ml_team.return_value = mock_team
                    mock_tx_service.get_pending_transactions = AsyncMock(return_value=[])
                    mock_tx_service.get_frozen_transactions = AsyncMock(return_value=[])
                    mock_tx_service.get_processed_transactions = AsyncMock(return_value=[])
                    mock_tx_service.get_team_transactions = AsyncMock(return_value=cancelled_tx)

                    await commands_cog.my_moves.callback(commands_cog, mock_interaction, show_cancelled=True)

                    # Verify cancelled transactions were requested
                    mock_tx_service.get_team_transactions.assert_called_once_with(
                        'WV', 13, cancelled=True
                    )
    
    @pytest.mark.asyncio
    async def test_my_moves_no_team(self, commands_cog, mock_interaction):
        """Test /mymoves command when user has no team.

        The @requires_team decorator intercepts the command and sends an error message
        directly via interaction.response.send_message (not interaction.followup.send)
        when the user doesn't have a team.
        """
        with patch('utils.permissions.get_user_team') as mock_get_user_team:
            # User has no team - decorator should intercept
            mock_get_user_team.return_value = None

            await commands_cog.my_moves.callback(commands_cog, mock_interaction)

            # Decorator sends via response.send_message, not followup
            mock_interaction.response.send_message.assert_called_once()
            call_args = mock_interaction.response.send_message.call_args
            assert "requires you to have a team" in call_args.args[0]
            assert call_args.kwargs.get('ephemeral') is True
    
    @pytest.mark.asyncio
    async def test_my_moves_api_error(self, commands_cog, mock_interaction, mock_team):
        """Test /mymoves command with API error.

        When an API error occurs inside the command, the @requires_team decorator
        catches the exception and sends an error message to the user via
        interaction.response.send_message (not raising the exception).
        """
        with patch('utils.permissions.get_user_team') as mock_get_user_team:
            with patch('commands.transactions.management.get_user_major_league_team') as mock_get_ml_team:
                with patch('commands.transactions.management.transaction_service') as mock_tx_service:

                    # Mock decorator lookup - @requires_team
                    mock_get_user_team.return_value = {
                        'id': mock_team.id, 'name': mock_team.lname,
                        'abbrev': mock_team.abbrev, 'season': mock_team.season
                    }
                    mock_get_ml_team.return_value = mock_team
                    mock_tx_service.get_pending_transactions = AsyncMock(side_effect=APIException("API Error"))

                    # The @requires_team decorator catches the exception and sends error message
                    await commands_cog.my_moves.callback(commands_cog, mock_interaction)

                    # Decorator sends error message via response.send_message
                    mock_interaction.response.send_message.assert_called_once()
                    call_args = mock_interaction.response.send_message.call_args
                    assert "temporary error" in call_args.args[0]
                    assert call_args.kwargs.get('ephemeral') is True
    
    @pytest.mark.asyncio
    async def test_legal_command_success(self, commands_cog, mock_interaction, mock_team):
        """Test successful /legal command execution."""
        # Mock roster data
        mock_current_roster = TeamRoster.from_api_data({
            'team_id': 499,
            'team_abbrev': 'WV',
            'season': 13,
            'week': 10,
            'players': []
        })

        mock_next_roster = TeamRoster.from_api_data({
            'team_id': 499,
            'team_abbrev': 'WV',
            'season': 13,
            'week': 11,
            'players': []
        })

        # Mock validation results
        mock_current_validation = RosterValidation(
            is_legal=True,
            total_players=25,
            active_players=25,
            il_players=0,
            total_sWAR=125.5
        )

        mock_next_validation = RosterValidation(
            is_legal=True,
            total_players=25,
            active_players=25,
            il_players=0,
            total_sWAR=126.0
        )

        with patch('utils.permissions.get_user_team') as mock_get_user_team:
            with patch('commands.transactions.management.team_service') as mock_team_service:
                with patch('commands.transactions.management.roster_service') as mock_roster_service:

                    # Mock decorator lookup - @requires_team
                    mock_get_user_team.return_value = {
                        'id': mock_team.id, 'name': mock_team.lname,
                        'abbrev': mock_team.abbrev, 'season': mock_team.season
                    }
                    # Mock the command's team_service.get_teams_by_owner call
                    mock_team_service.get_teams_by_owner = AsyncMock(return_value=[mock_team])
                    mock_roster_service.get_current_roster = AsyncMock(return_value=mock_current_roster)
                    mock_roster_service.get_next_roster = AsyncMock(return_value=mock_next_roster)
                    mock_roster_service.validate_roster = AsyncMock(side_effect=[
                        mock_current_validation,
                        mock_next_validation
                    ])

                    await commands_cog.legal.callback(commands_cog, mock_interaction)

                    # Verify service calls
                    mock_roster_service.get_current_roster.assert_called_once_with(499)
                    mock_roster_service.get_next_roster.assert_called_once_with(499)

                    # Verify validation calls
                    assert mock_roster_service.validate_roster.call_count == 2

                    # Verify response
                    mock_interaction.followup.send.assert_called_once()
                    embed_call = mock_interaction.followup.send.call_args
                    assert 'embed' in embed_call.kwargs
    
    @pytest.mark.asyncio
    async def test_legal_command_with_team_param(self, commands_cog, mock_interaction, mock_team):
        """Test /legal command with explicit team parameter."""
        target_team = Team.from_api_data({
            'id': 508,
            'abbrev': 'NYD',
            'sname': 'Diamonds',
            'lname': 'New York Diamonds',
            'season': 13
        })

        with patch('utils.permissions.get_user_team') as mock_get_user_team:
            with patch('commands.transactions.management.team_service') as mock_team_service:
                with patch('commands.transactions.management.roster_service') as mock_roster_service:

                    # Mock decorator lookup - @requires_team
                    mock_get_user_team.return_value = {
                        'id': mock_team.id, 'name': mock_team.lname,
                        'abbrev': mock_team.abbrev, 'season': mock_team.season
                    }
                    mock_team_service.get_team_by_abbrev = AsyncMock(return_value=target_team)
                    mock_roster_service.get_current_roster = AsyncMock(return_value=None)
                    mock_roster_service.get_next_roster = AsyncMock(return_value=None)

                    await commands_cog.legal.callback(commands_cog, mock_interaction, team='NYD')

                    # Verify team lookup by abbreviation
                    mock_team_service.get_team_by_abbrev.assert_called_once_with('NYD', 13)
                    mock_roster_service.get_current_roster.assert_called_once_with(508)
    
    @pytest.mark.asyncio
    async def test_legal_command_team_not_found(self, commands_cog, mock_interaction, mock_team):
        """Test /legal command with invalid team abbreviation."""
        with patch('utils.permissions.get_user_team') as mock_get_user_team:
            with patch('commands.transactions.management.team_service') as mock_team_service:

                # Mock decorator lookup - @requires_team
                mock_get_user_team.return_value = {
                    'id': mock_team.id, 'name': mock_team.lname,
                    'abbrev': mock_team.abbrev, 'season': mock_team.season
                }
                mock_team_service.get_team_by_abbrev = AsyncMock(return_value=None)

                await commands_cog.legal.callback(commands_cog, mock_interaction, team='INVALID')

                # Should send error message
                mock_interaction.followup.send.assert_called_once()
                call_args = mock_interaction.followup.send.call_args
                assert "Could not find team 'INVALID'" in call_args.args[0]
    
    @pytest.mark.asyncio
    async def test_legal_command_no_roster_data(self, commands_cog, mock_interaction, mock_team):
        """Test /legal command when roster data is unavailable."""
        with patch('utils.permissions.get_user_team') as mock_get_user_team:
            with patch('commands.transactions.management.team_service') as mock_team_service:
                with patch('commands.transactions.management.roster_service') as mock_roster_service:

                    # Mock decorator lookup - @requires_team
                    mock_get_user_team.return_value = {
                        'id': mock_team.id, 'name': mock_team.lname,
                        'abbrev': mock_team.abbrev, 'season': mock_team.season
                    }
                    # Mock the command's team_service.get_teams_by_owner call
                    mock_team_service.get_teams_by_owner = AsyncMock(return_value=[mock_team])
                    mock_roster_service.get_current_roster = AsyncMock(return_value=None)
                    mock_roster_service.get_next_roster = AsyncMock(return_value=None)

                    await commands_cog.legal.callback(commands_cog, mock_interaction)

                    # Should send error about no roster data
                    mock_interaction.followup.send.assert_called_once()
                    call_args = mock_interaction.followup.send.call_args
                    assert "Could not retrieve roster data" in call_args.args[0]
    
    @pytest.mark.asyncio
    async def test_create_my_moves_pages(self, commands_cog, mock_team, mock_transactions):
        """Test paginated embed creation for /mymoves command."""
        pending_tx = [tx for tx in mock_transactions if tx.is_pending]
        frozen_tx = [tx for tx in mock_transactions if tx.is_frozen]
        processed_tx = []
        cancelled_tx = [tx for tx in mock_transactions if tx.is_cancelled]

        pages = commands_cog._create_my_moves_pages(
            mock_team, pending_tx, frozen_tx, processed_tx, cancelled_tx
        )

        assert len(pages) > 0
        first_page = pages[0]
        assert isinstance(first_page, discord.Embed)
        assert first_page.title == "📋 Transaction Status - WV"
        assert "West Virginia Black Bears • Season 13" in first_page.description

        # Check that fields are created for transaction types
        field_names = [field.name for field in first_page.fields]
        assert any("Pending Transactions" in name for name in field_names)

        # Verify thumbnail is set
        assert first_page.thumbnail.url == mock_team.thumbnail

        # Verify emoji is NOT in individual transaction lines
        for page in pages:
            for field in page.fields:
                if "Pending" in field.name or "Scheduled" in field.name or "Cancelled" in field.name:
                    # Check that emojis (⏳, ❄️, ❌) are NOT in the field value
                    assert "⏳" not in field.value
                    assert "❄️" not in field.value
                    assert "✅" not in field.value
    
    @pytest.mark.asyncio
    async def test_create_my_moves_pages_no_transactions(self, commands_cog, mock_team):
        """Test paginated embed creation with no transactions."""
        pages = commands_cog._create_my_moves_pages(
            mock_team, [], [], [], []
        )

        assert len(pages) == 1  # Should have single page
        embed = pages[0]

        # Find the pending transactions field
        pending_field = next(f for f in embed.fields if "Pending" in f.name)
        assert pending_field.value == "No pending transactions"

        # Summary should show no active transactions
        summary_field = next(f for f in embed.fields if f.name == "Summary")
        assert summary_field.value == "No active transactions"

    @pytest.mark.asyncio
    async def test_transaction_pagination_view_with_move_ids(self, commands_cog, mock_interaction, mock_team, mock_transactions):
        """Test that TransactionPaginationView is created with move IDs button."""
        from commands.transactions.management import TransactionPaginationView

        pending_tx = [tx for tx in mock_transactions if tx.is_pending]

        with patch('utils.permissions.get_user_team') as mock_get_user_team:
            with patch('commands.transactions.management.get_user_major_league_team') as mock_get_ml_team:
                with patch('commands.transactions.management.transaction_service') as mock_tx_service:

                    # Mock decorator lookup - @requires_team
                    mock_get_user_team.return_value = {
                        'id': mock_team.id, 'name': mock_team.lname,
                        'abbrev': mock_team.abbrev, 'season': mock_team.season
                    }
                    mock_get_ml_team.return_value = mock_team
                    mock_tx_service.get_pending_transactions = AsyncMock(return_value=pending_tx)
                    mock_tx_service.get_frozen_transactions = AsyncMock(return_value=[])
                    mock_tx_service.get_processed_transactions = AsyncMock(return_value=[])

                    await commands_cog.my_moves.callback(commands_cog, mock_interaction, show_cancelled=False)

                    # Verify TransactionPaginationView was created
                    mock_interaction.followup.send.assert_called_once()
                    call_args = mock_interaction.followup.send.call_args
                    view = call_args.kwargs.get('view')

                    assert view is not None
                    assert isinstance(view, TransactionPaginationView)
                    assert len(view.all_transactions) == len(pending_tx)

    @pytest.mark.asyncio
    async def test_show_move_ids_handles_long_lists(self, mock_team, mock_transactions):
        """Test that Show Move IDs button properly chunks very long transaction lists."""
        from commands.transactions.management import TransactionPaginationView

        # Create 100 transactions to simulate a very long list
        base_data = {
            'season': 12,
            'player': {
                'id': 12472,
                'name': 'Very Long Player Name That Takes Up Space',
                'wara': 2.47,
                'season': 12,
                'pos_1': 'LF'
            },
            'oldteam': {
                'id': 508,
                'abbrev': 'NYD',
                'sname': 'Diamonds',
                'lname': 'New York Diamonds',
                'season': 12
            },
            'newteam': {
                'id': 499,
                'abbrev': 'WV',
                'sname': 'Black Bears',
                'lname': 'West Virginia Black Bears',
                'season': 12
            }
        }

        many_transactions = []
        for i in range(100):
            tx_data = {
                **base_data,
                'id': i,
                'week': 10 + (i % 5),
                'moveid': f'Season-012-Week-{10 + (i % 5)}-Move-{i:03d}',
                'cancelled': False,
                'frozen': False
            }
            many_transactions.append(Transaction.from_api_data(tx_data))

        # Create view with many transactions
        pages = [discord.Embed(title="Test")]
        view = TransactionPaginationView(
            pages=pages,
            all_transactions=many_transactions,
            user_id=258104532423147520,
            timeout=300.0,
            show_page_numbers=True
        )

        # Create mock interaction
        mock_interaction = AsyncMock()
        mock_button = MagicMock()

        # Find the show_move_ids button and call its callback directly
        show_move_ids_button = None
        for item in view.children:
            if hasattr(item, 'label') and item.label == "Show Move IDs":
                show_move_ids_button = item
                break

        assert show_move_ids_button is not None, "Show Move IDs button not found"

        # Call the button's callback
        await show_move_ids_button.callback(mock_interaction)

        # Verify response was sent
        mock_interaction.response.send_message.assert_called_once()

        # Get the message that was sent
        call_args = mock_interaction.response.send_message.call_args
        first_message = call_args.args[0]

        # Verify first message is under 2000 characters
        assert len(first_message) < 2000, f"First message is {len(first_message)} characters (exceeds 2000 limit)"

        # If there were followup messages, verify they're also under 2000 chars
        if mock_interaction.followup.send.called:
            for call in mock_interaction.followup.send.call_args_list:
                followup_message = call.args[0]
                assert len(followup_message) < 2000, f"Followup message is {len(followup_message)} characters (exceeds 2000 limit)"
    
    @pytest.mark.asyncio
    async def test_create_legal_embed_all_legal(self, commands_cog, mock_team):
        """Test legal embed creation when all rosters are legal."""
        current_validation = RosterValidation(
            is_legal=True,
            active_players=25,
            il_players=0,
            total_sWAR=125.5
        )
        
        next_validation = RosterValidation(
            is_legal=True,
            active_players=25,
            il_players=0,
            total_sWAR=126.0
        )
        
        # Create mock roster objects to pass with validation
        mock_current_roster = TeamRoster.from_api_data({
            'team_id': 499, 'team_abbrev': 'WV', 'season': 12, 'week': 10, 'players': []
        })
        mock_next_roster = TeamRoster.from_api_data({
            'team_id': 499, 'team_abbrev': 'WV', 'season': 12, 'week': 11, 'players': []
        })
        
        embed = await commands_cog._create_legal_embed(
            mock_team, mock_current_roster, mock_next_roster, current_validation, next_validation
        )
        
        assert isinstance(embed, discord.Embed)
        assert "✅ Roster Check - WV" in embed.title
        assert embed.color.value == 0x28a745  # EmbedColors.SUCCESS
        
        # Check status fields
        field_names = [field.name for field in embed.fields]
        assert "✅ Current Week" in field_names
        assert "✅ Next Week" in field_names
        assert "Overall Status" in field_names
        
        # Overall status should be positive
        overall_field = next(f for f in embed.fields if f.name == "Overall Status")
        assert "All rosters are legal" in overall_field.value
    
    @pytest.mark.asyncio
    async def test_create_legal_embed_with_errors(self, commands_cog, mock_team):
        """Test legal embed creation with roster violations."""
        current_validation = RosterValidation(
            is_legal=False,
            errors=['Too many players on roster', 'Invalid position assignment'],
            warnings=['Low WARA total'],
            active_players=28,
            il_players=2,
            total_sWAR=95.2
        )
        
        next_validation = RosterValidation(
            is_legal=True,
            active_players=25,
            il_players=0,
            total_sWAR=120.0
        )
        
        # Create mock roster objects to pass with validation
        mock_current_roster = TeamRoster.from_api_data({
            'team_id': 499, 'team_abbrev': 'WV', 'season': 12, 'week': 10, 'players': []
        })
        mock_next_roster = TeamRoster.from_api_data({
            'team_id': 499, 'team_abbrev': 'WV', 'season': 12, 'week': 11, 'players': []
        })
        
        embed = await commands_cog._create_legal_embed(
            mock_team, mock_current_roster, mock_next_roster, current_validation, next_validation
        )
        
        assert "❌ Roster Check - WV" in embed.title
        assert embed.color.value == 0xdc3545  # EmbedColors.ERROR
        
        # Check that errors are displayed
        current_field = next(f for f in embed.fields if "Current Week" in f.name)
        assert "**❌ Errors:** 2" in current_field.value
        assert "Too many players on roster" in current_field.value
        assert "**⚠️ Warnings:** 1" in current_field.value
        
        # Overall status should indicate violations
        overall_field = next(f for f in embed.fields if f.name == "Overall Status")
        assert "violations found" in overall_field.value
    
    @pytest.mark.asyncio
    async def test_create_legal_embed_no_roster_data(self, commands_cog, mock_team):
        """Test legal embed creation when roster data is unavailable."""
        embed = await commands_cog._create_legal_embed(
            mock_team, None, None, None, None
        )
        
        # Should show "data not available" messages
        field_names = [field.name for field in embed.fields]
        assert "❓ Current Week" in field_names
        assert "❓ Next Week" in field_names
        
        current_field = next(f for f in embed.fields if "Current Week" in f.name)
        assert "Roster data not available" in current_field.value


class TestTransactionCommandsIntegration:
    """Integration tests for transaction commands with realistic scenarios."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create mock Discord bot for integration tests."""
        bot = MagicMock()
        return bot
    
    @pytest.fixture
    def commands_cog(self, mock_bot):
        """Create TransactionCommands cog for integration tests."""
        return TransactionCommands(mock_bot)
    
    @pytest.mark.asyncio
    async def test_full_my_moves_workflow(self, commands_cog):
        """Test complete /mymoves workflow with realistic data volumes."""
        mock_interaction = AsyncMock()
        mock_interaction.user = MagicMock()
        mock_interaction.user.id = 258104532423147520
        mock_interaction.response = AsyncMock()
        mock_interaction.followup = AsyncMock()
        mock_interaction.guild = MagicMock()
        mock_interaction.guild.id = 669356687294988350

        # Create realistic transaction volumes
        pending_transactions = []
        for i in range(15):  # 15 pending transactions
            tx_data = {
                'id': i,
                'week': 10 + (i % 3),
                'season': 13,
                'moveid': f'move_{i}',
                'player': {'id': i, 'name': f'Player {i}', 'wara': 2.0 + (i % 10) * 0.1, 'season': 13, 'pos_1': 'LF'},
                'oldteam': {'id': 508, 'abbrev': 'NYD', 'sname': 'Diamonds', 'lname': 'New York Diamonds', 'season': 13},
                'newteam': {'id': 499, 'abbrev': 'WV', 'sname': 'Black Bears', 'lname': 'West Virginia Black Bears', 'season': 13},
                'cancelled': False,
                'frozen': False
            }
            pending_transactions.append(Transaction.from_api_data(tx_data))

        mock_team = Team.from_api_data({
            'id': 499,
            'abbrev': 'WV',
            'sname': 'Black Bears',
            'lname': 'West Virginia Black Bears',
            'season': 13
        })

        with patch('utils.permissions.get_user_team') as mock_get_user_team:
            with patch('commands.transactions.management.get_user_major_league_team') as mock_get_ml_team:
                with patch('commands.transactions.management.transaction_service') as mock_tx_service:

                    # Mock decorator lookup - @requires_team
                    mock_get_user_team.return_value = {
                        'id': mock_team.id, 'name': mock_team.lname,
                        'abbrev': mock_team.abbrev, 'season': mock_team.season
                    }
                    mock_get_ml_team.return_value = mock_team
                    mock_tx_service.get_pending_transactions = AsyncMock(return_value=pending_transactions)
                    mock_tx_service.get_frozen_transactions = AsyncMock(return_value=[])
                    mock_tx_service.get_processed_transactions = AsyncMock(return_value=[])

                    await commands_cog.my_moves.callback(commands_cog, mock_interaction, show_cancelled=False)

                    # Verify embed was created and sent
                    mock_interaction.followup.send.assert_called_once()
                    embed_call = mock_interaction.followup.send.call_args
                    embed = embed_call.kwargs['embed']

                    # With 15 transactions, should show 10 per page
                    pending_field = next(f for f in embed.fields if "Pending" in f.name)
                    lines = pending_field.value.split('\n')
                    assert len(lines) == 10  # Should show 10 per page

                    # Verify summary shows correct count
                    summary_field = next(f for f in embed.fields if f.name == "Summary")
                    assert "15 pending" in summary_field.value

                    # Verify pagination view was created
                    from commands.transactions.management import TransactionPaginationView
                    view = embed_call.kwargs.get('view')
                    assert view is not None
                    assert isinstance(view, TransactionPaginationView)
                    assert len(view.all_transactions) == 15
    
    @pytest.mark.asyncio
    async def test_concurrent_command_execution(self, commands_cog):
        """Test that commands can handle concurrent execution."""
        import asyncio

        mock_team = Team.from_api_data({
            'id': 499,
            'abbrev': 'WV',
            'sname': 'Black Bears',
            'lname': 'West Virginia Black Bears',
            'season': 13
        })

        # Create multiple mock interactions with proper setup
        interactions = []
        for i in range(5):
            mock_interaction = AsyncMock()
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 258104532423147520 + i
            mock_interaction.response = AsyncMock()
            mock_interaction.followup = AsyncMock()
            mock_interaction.guild = MagicMock()
            mock_interaction.guild.id = 669356687294988350
            interactions.append(mock_interaction)

        with patch('utils.permissions.get_user_team') as mock_get_user_team:
            with patch('commands.transactions.management.get_user_major_league_team') as mock_get_ml_team:
                with patch('commands.transactions.management.transaction_service') as mock_tx_service:

                    # Mock decorator lookup - @requires_team
                    mock_get_user_team.return_value = {
                        'id': mock_team.id, 'name': mock_team.lname,
                        'abbrev': mock_team.abbrev, 'season': mock_team.season
                    }
                    mock_get_ml_team.return_value = mock_team
                    mock_tx_service.get_pending_transactions = AsyncMock(return_value=[])
                    mock_tx_service.get_frozen_transactions = AsyncMock(return_value=[])
                    mock_tx_service.get_processed_transactions = AsyncMock(return_value=[])

                    # Execute commands concurrently
                    tasks = [commands_cog.my_moves.callback(commands_cog, interaction) for interaction in interactions]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # All should complete successfully
                    assert len([r for r in results if not isinstance(r, Exception)]) == 5

                    # All interactions should have received responses
                    for interaction in interactions:
                        interaction.followup.send.assert_called_once()