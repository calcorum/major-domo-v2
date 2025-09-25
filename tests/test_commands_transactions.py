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
        return interaction
    
    @pytest.fixture
    def mock_team(self):
        """Create mock team data."""
        return Team.from_api_data({
            'id': 499,
            'abbrev': 'WV',
            'sname': 'Black Bears',
            'lname': 'West Virginia Black Bears',
            'season': 12,
            'thumbnail': 'https://example.com/thumbnail.png'
        })
    
    @pytest.fixture
    def mock_transactions(self):
        """Create mock transaction list."""
        base_data = {
            'season': 12,
            'player': {
                'id': 12472,
                'name': 'Test Player',
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
        
        with patch('commands.transactions.management.team_service') as mock_team_service:
            with patch('commands.transactions.management.transaction_service') as mock_tx_service:
                
                # Mock service responses
                mock_team_service.get_teams_by_owner = AsyncMock(return_value=[mock_team])
                mock_tx_service.get_pending_transactions = AsyncMock(return_value=pending_tx)
                mock_tx_service.get_frozen_transactions = AsyncMock(return_value=frozen_tx)
                mock_tx_service.get_processed_transactions = AsyncMock(return_value=[])
                
                # Execute command
                await commands_cog.my_moves.callback(commands_cog, mock_interaction, show_cancelled=False)
                
                # Verify interaction flow
                mock_interaction.response.defer.assert_called_once()
                mock_interaction.followup.send.assert_called_once()
                
                # Verify service calls
                mock_team_service.get_teams_by_owner.assert_called_once_with(
                    mock_interaction.user.id, 12
                )
                mock_tx_service.get_pending_transactions.assert_called_once_with('WV', 12)
                mock_tx_service.get_frozen_transactions.assert_called_once_with('WV', 12)
                mock_tx_service.get_processed_transactions.assert_called_once_with('WV', 12)
                
                # Check embed was sent
                embed_call = mock_interaction.followup.send.call_args
                assert 'embed' in embed_call.kwargs
    
    @pytest.mark.asyncio
    async def test_my_moves_with_cancelled(self, commands_cog, mock_interaction, mock_team, mock_transactions):
        """Test /mymoves command with cancelled transactions shown."""
        cancelled_tx = [tx for tx in mock_transactions if tx.is_cancelled]
        
        with patch('commands.transactions.management.team_service') as mock_team_service:
            with patch('commands.transactions.management.transaction_service') as mock_tx_service:
                
                mock_team_service.get_teams_by_owner = AsyncMock(return_value=[mock_team])
                mock_tx_service.get_pending_transactions = AsyncMock(return_value=[])
                mock_tx_service.get_frozen_transactions = AsyncMock(return_value=[])
                mock_tx_service.get_processed_transactions = AsyncMock(return_value=[])
                mock_tx_service.get_team_transactions = AsyncMock(return_value=cancelled_tx)
                
                await commands_cog.my_moves.callback(commands_cog, mock_interaction, show_cancelled=True)
                
                # Verify cancelled transactions were requested
                mock_tx_service.get_team_transactions.assert_called_once_with(
                    'WV', 12, cancelled=True
                )
    
    @pytest.mark.asyncio
    async def test_my_moves_no_team(self, commands_cog, mock_interaction):
        """Test /mymoves command when user has no team."""
        with patch('commands.transactions.management.team_service') as mock_team_service:
            mock_team_service.get_teams_by_owner = AsyncMock(return_value=[])
            
            await commands_cog.my_moves.callback(commands_cog, mock_interaction)
            
            # Should send error message
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            assert "don't appear to own a team" in call_args.args[0]
            assert call_args.kwargs.get('ephemeral') is True
    
    @pytest.mark.asyncio
    async def test_my_moves_api_error(self, commands_cog, mock_interaction, mock_team):
        """Test /mymoves command with API error."""
        with patch('commands.transactions.management.team_service') as mock_team_service:
            with patch('commands.transactions.management.transaction_service') as mock_tx_service:
                
                mock_team_service.get_teams_by_owner = AsyncMock(return_value=[mock_team])
                mock_tx_service.get_pending_transactions.side_effect = APIException("API Error")
                
                # Should raise the exception (logged_command decorator handles it)
                with pytest.raises(APIException):
                    await commands_cog.my_moves.callback(commands_cog, mock_interaction)
    
    @pytest.mark.asyncio
    async def test_legal_command_success(self, commands_cog, mock_interaction, mock_team):
        """Test successful /legal command execution."""
        # Mock roster data
        mock_current_roster = TeamRoster.from_api_data({
            'team_id': 499,
            'team_abbrev': 'WV',
            'season': 12,
            'week': 10,
            'players': []
        })
        
        mock_next_roster = TeamRoster.from_api_data({
            'team_id': 499,
            'team_abbrev': 'WV',
            'season': 12, 
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
        
        with patch('commands.transactions.management.team_service') as mock_team_service:
            with patch('commands.transactions.management.roster_service') as mock_roster_service:
                
                # Mock service responses
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
    async def test_legal_command_with_team_param(self, commands_cog, mock_interaction):
        """Test /legal command with explicit team parameter."""
        target_team = Team.from_api_data({
            'id': 508,
            'abbrev': 'NYD',
            'sname': 'Diamonds',
            'lname': 'New York Diamonds',
            'season': 12
        })
        
        with patch('commands.transactions.management.team_service') as mock_team_service:
            with patch('commands.transactions.management.roster_service') as mock_roster_service:
                
                mock_team_service.get_team_by_abbrev = AsyncMock(return_value=target_team)
                mock_roster_service.get_current_roster = AsyncMock(return_value=None)
                mock_roster_service.get_next_roster = AsyncMock(return_value=None)
                
                await commands_cog.legal.callback(commands_cog, mock_interaction, team='NYD')
                
                # Verify team lookup by abbreviation
                mock_team_service.get_team_by_abbrev.assert_called_once_with('NYD', 12)
                mock_roster_service.get_current_roster.assert_called_once_with(508)
    
    @pytest.mark.asyncio
    async def test_legal_command_team_not_found(self, commands_cog, mock_interaction):
        """Test /legal command with invalid team abbreviation."""
        with patch('commands.transactions.management.team_service') as mock_team_service:
            mock_team_service.get_team_by_abbrev = AsyncMock(return_value=None)
            
            await commands_cog.legal.callback(commands_cog, mock_interaction, team='INVALID')
            
            # Should send error message
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            assert "Could not find team 'INVALID'" in call_args.args[0]
    
    @pytest.mark.asyncio
    async def test_legal_command_no_roster_data(self, commands_cog, mock_interaction, mock_team):
        """Test /legal command when roster data is unavailable."""
        with patch('commands.transactions.management.team_service') as mock_team_service:
            with patch('commands.transactions.management.roster_service') as mock_roster_service:
                
                mock_team_service.get_teams_by_owner = AsyncMock(return_value=[mock_team])
                mock_roster_service.get_current_roster = AsyncMock(return_value=None)
                mock_roster_service.get_next_roster = AsyncMock(return_value=None)
                
                await commands_cog.legal.callback(commands_cog, mock_interaction)
                
                # Should send error about no roster data
                mock_interaction.followup.send.assert_called_once()
                call_args = mock_interaction.followup.send.call_args
                assert "Could not retrieve roster data" in call_args.args[0]
    
    @pytest.mark.asyncio
    async def test_create_my_moves_embed(self, commands_cog, mock_team, mock_transactions):
        """Test embed creation for /mymoves command."""
        pending_tx = [tx for tx in mock_transactions if tx.is_pending]
        frozen_tx = [tx for tx in mock_transactions if tx.is_frozen]
        processed_tx = []
        cancelled_tx = [tx for tx in mock_transactions if tx.is_cancelled]
        
        embed = await commands_cog._create_my_moves_embed(
            mock_team, pending_tx, frozen_tx, processed_tx, cancelled_tx
        )
        
        assert isinstance(embed, discord.Embed)
        assert embed.title == "📋 Transaction Status - WV"
        assert "West Virginia Black Bears • Season 12" in embed.description
        
        # Check that fields are created for each transaction type
        field_names = [field.name for field in embed.fields]
        assert "⏳ Pending Transactions" in field_names
        assert "❄️ Scheduled for Processing" in field_names
        assert "❌ Cancelled Transactions" in field_names
        assert "Summary" in field_names
        
        # Verify thumbnail is set
        assert embed.thumbnail.url == mock_team.thumbnail
    
    @pytest.mark.asyncio
    async def test_create_my_moves_embed_no_transactions(self, commands_cog, mock_team):
        """Test embed creation with no transactions."""
        embed = await commands_cog._create_my_moves_embed(
            mock_team, [], [], [], []
        )
        
        # Find the pending transactions field
        pending_field = next(f for f in embed.fields if "Pending" in f.name)
        assert pending_field.value == "No pending transactions"
        
        # Summary should show no active transactions
        summary_field = next(f for f in embed.fields if f.name == "Summary")
        assert summary_field.value == "No active transactions"
    
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
        mock_interaction.user.id = 258104532423147520
        
        # Create realistic transaction volumes
        pending_transactions = []
        for i in range(15):  # 15 pending transactions
            tx_data = {
                'id': i,
                'week': 10 + (i % 3),
                'season': 12,
                'moveid': f'move_{i}',
                'player': {'id': i, 'name': f'Player {i}', 'wara': 2.0 + (i % 10) * 0.1, 'season': 12, 'pos_1': 'LF'},
                'oldteam': {'id': 508, 'abbrev': 'NYD', 'sname': 'Diamonds', 'lname': 'New York Diamonds', 'season': 12},
                'newteam': {'id': 499, 'abbrev': 'WV', 'sname': 'Black Bears', 'lname': 'West Virginia Black Bears', 'season': 12},
                'cancelled': False,
                'frozen': False
            }
            pending_transactions.append(Transaction.from_api_data(tx_data))
        
        mock_team = Team.from_api_data({
            'id': 499,
            'abbrev': 'WV',
            'sname': 'Black Bears',
            'lname': 'West Virginia Black Bears',
            'season': 12
        })
        
        with patch('commands.transactions.management.team_service') as mock_team_service:
            with patch('commands.transactions.management.transaction_service') as mock_tx_service:
                
                mock_team_service.get_teams_by_owner = AsyncMock(return_value=[mock_team])
                mock_tx_service.get_pending_transactions = AsyncMock(return_value=pending_transactions)
                mock_tx_service.get_frozen_transactions = AsyncMock(return_value=[])
                mock_tx_service.get_processed_transactions = AsyncMock(return_value=[])
                
                await commands_cog.my_moves.callback(commands_cog, mock_interaction, show_cancelled=False)
                
                # Verify embed was created and sent
                mock_interaction.followup.send.assert_called_once()
                embed_call = mock_interaction.followup.send.call_args
                embed = embed_call.kwargs['embed']
                
                # Check that only last 5 pending transactions are shown
                pending_field = next(f for f in embed.fields if "Pending" in f.name)
                lines = pending_field.value.split('\n')
                assert len(lines) == 5  # Should show only last 5
                
                # Verify summary shows correct count
                summary_field = next(f for f in embed.fields if f.name == "Summary")
                assert "15 pending" in summary_field.value
    
    @pytest.mark.asyncio
    async def test_concurrent_command_execution(self, commands_cog):
        """Test that commands can handle concurrent execution."""
        import asyncio
        
        # Create multiple mock interactions
        interactions = []
        for i in range(5):
            mock_interaction = AsyncMock()
            mock_interaction.user.id = 258104532423147520 + i
            interactions.append(mock_interaction)
        
        mock_team = Team.from_api_data({
            'id': 499,
            'abbrev': 'WV',
            'sname': 'Black Bears',
            'lname': 'West Virginia Black Bears',
            'season': 12
        })
        
        with patch('commands.transactions.management.team_service') as mock_team_service:
            with patch('commands.transactions.management.transaction_service') as mock_tx_service:
                
                mock_team_service.get_teams_by_owner = AsyncMock(return_value=[mock_team])
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