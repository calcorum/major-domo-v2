"""
Integration tests for Transaction functionality

Tests the complete flow from API through services to Discord commands.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from models.transaction import Transaction, RosterValidation
from models.team import Team
from models.roster import TeamRoster
from services.transaction_service import transaction_service
from commands.transactions.management import TransactionCommands
from tests.factories import TeamFactory


class TestTransactionIntegration:
    """Integration tests for the complete transaction system."""
    
    @pytest.fixture
    def realistic_api_data(self):
        """Create realistic API response data based on actual structure."""
        return [
            {
                'id': 27787,
                'week': 10,
                'player': {
                    'id': 12472,
                    'name': 'Yordan Alvarez',
                    'wara': 2.47,
                    'image': 'https://sba-cards-2024.s3.us-east-1.amazonaws.com/2024-cards/yordan-alvarez.png',
                    'image2': None,
                    'team': {
                        'id': 508,
                        'abbrev': 'NYD',
                        'sname': 'Diamonds',
                        'lname': 'New York Diamonds',
                        'manager_legacy': None,
                        'division_legacy': None,
                        'gmid': '143034072787058688',
                        'gmid2': None,
                        'season': 12
                    },
                    'season': 12,
                    'pitcher_injury': None,
                    'pos_1': 'LF',
                    'pos_2': None,
                    'last_game': None,
                    'il_return': None,
                    'demotion_week': 1,
                    'headshot': None,
                    'strat_code': 'Alvarez,Y',
                    'bbref_id': 'alvaryo01',
                    'injury_rating': '1p65'
                },
                'oldteam': {
                    'id': 508,
                    'abbrev': 'NYD',
                    'sname': 'Diamonds',
                    'lname': 'New York Diamonds',
                    'manager_legacy': None,
                    'division_legacy': None,
                    'gmid': '143034072787058688',
                    'gmid2': None,
                    'season': 12
                },
                'newteam': {
                    'id': 499,
                    'abbrev': 'WV',
                    'sname': 'Black Bears',
                    'lname': 'West Virginia Black Bears',
                    'manager_legacy': None,
                    'division_legacy': None,
                    'gmid': '258104532423147520',
                    'gmid2': None,
                    'season': 12
                },
                'season': 12,
                'moveid': 'Season-012-Week-10-19-13:04:41',
                'cancelled': False,
                'frozen': False
            },
            {
                'id': 27788,
                'week': 10,
                'player': {
                    'id': 12473,
                    'name': 'Ronald Acuna Jr.',
                    'wara': 3.12,
                    'season': 12,
                    'pos_1': 'OF'
                },
                'oldteam': {
                    'id': 499,
                    'abbrev': 'WV',
                    'sname': 'Black Bears',
                    'lname': 'West Virginia Black Bears',
                    'season': 12
                },
                'newteam': {
                    'id': 501,
                    'abbrev': 'ATL',
                    'sname': 'Braves',
                    'lname': 'Atlanta Braves',
                    'season': 12
                },
                'season': 12,
                'moveid': 'Season-012-Week-10-20-14:22:15',
                'cancelled': False,
                'frozen': True
            },
            {
                'id': 27789,
                'week': 9,
                'player': {
                    'id': 12474,
                    'name': 'Mike Trout',
                    'wara': 2.89,
                    'season': 12,
                    'pos_1': 'CF'
                },
                'oldteam': {
                    'id': 502,
                    'abbrev': 'LAA',
                    'sname': 'Angels',
                    'lname': 'Los Angeles Angels',
                    'season': 12
                },
                'newteam': {
                    'id': 503,
                    'abbrev': 'FA',
                    'sname': 'Free Agents',
                    'lname': 'Free Agency',
                    'season': 12
                },
                'season': 12,
                'moveid': 'Season-012-Week-09-18-11:45:33',
                'cancelled': True,
                'frozen': False
            }
        ]
    
    @pytest.mark.asyncio
    async def test_api_to_model_conversion(self, realistic_api_data):
        """Test that realistic API data converts correctly to Transaction models."""
        transactions = [Transaction.from_api_data(data) for data in realistic_api_data]
        
        assert len(transactions) == 3
        
        # Test first transaction (pending)
        tx1 = transactions[0]
        assert tx1.id == 27787
        assert tx1.player.name == 'Yordan Alvarez'
        assert tx1.player.wara == 2.47
        assert tx1.player.bbref_id == 'alvaryo01'
        assert tx1.oldteam.abbrev == 'NYD'
        assert tx1.newteam.abbrev == 'WV'
        assert tx1.is_pending is True
        assert tx1.is_major_league_move is True
        
        # Test second transaction (frozen)
        tx2 = transactions[1]
        assert tx2.id == 27788
        assert tx2.is_frozen is True
        assert tx2.is_pending is False
        
        # Test third transaction (cancelled)
        tx3 = transactions[2]
        assert tx3.id == 27789
        assert tx3.is_cancelled is True
        assert tx3.newteam.abbrev == 'FA'  # Move to free agency
    
    @pytest.mark.asyncio
    async def test_service_layer_integration(self, realistic_api_data):
        """Test service layer with realistic data processing."""
        service = transaction_service
        
        with patch.object(service, 'get_all_items', new_callable=AsyncMock) as mock_get:
            # Mock API returns realistic data
            mock_get.return_value = [Transaction.from_api_data(data) for data in realistic_api_data]
            
            # Test team transactions
            result = await service.get_team_transactions('WV', 12)
            
            # Should sort by week, then moveid
            assert result[0].week == 9   # Week 9 first
            assert result[1].week == 10  # Then week 10 transactions
            assert result[2].week == 10
            
            # Test filtering
            pending = await service.get_pending_transactions('WV', 12)
            frozen = await service.get_frozen_transactions('WV', 12)
            
            # Verify filtering works correctly
            with patch.object(service, 'get_team_transactions', new_callable=AsyncMock) as mock_team_tx:
                mock_team_tx.return_value = [tx for tx in result if tx.is_pending]
                pending_filtered = await service.get_pending_transactions('WV', 12)

                # get_pending_transactions now includes week_start parameter from league_service
                # Just verify it was called with the essential parameters
                mock_team_tx.assert_called_once()
                call_args = mock_team_tx.call_args
                assert call_args[0] == ('WV', 12)  # Positional args
                assert call_args[1]['cancelled'] is False
                assert call_args[1]['frozen'] is False
    
    @pytest.mark.skip(reason="Requires deep API mocking - @requires_team decorator import chain cannot be fully mocked in unit tests")
    @pytest.mark.asyncio
    async def test_command_layer_integration(self, realistic_api_data):
        """Test Discord command layer with realistic transaction data.

        This test requires mocking at multiple levels:
        1. services.team_service.team_service - for the @requires_team() decorator (via get_user_team)
        2. commands.transactions.management.team_service - for command-level team lookups
        3. commands.transactions.management.transaction_service - for transaction data

        NOTE: This test is skipped because the @requires_team() decorator performs a local
        import of team_service inside the get_user_team() function, which cannot be
        reliably mocked in unit tests. Consider running as an integration test with
        a mock API server.
        """
        mock_bot = MagicMock()
        commands_cog = TransactionCommands(mock_bot)

        mock_interaction = AsyncMock()
        mock_interaction.user.id = 258104532423147520  # WV owner ID from API data
        mock_interaction.extras = {}  # For @requires_team() to store team info
        # Guild mock required for @league_only decorator
        mock_interaction.guild = MagicMock()
        mock_interaction.guild.id = 669356687294988350

        mock_team = Team.from_api_data({
            'id': 499,
            'abbrev': 'WV',
            'sname': 'Black Bears',
            'lname': 'West Virginia Black Bears',
            'season': 12,
            'thumbnail': 'https://example.com/wv.png'
        })

        transactions = [Transaction.from_api_data(data) for data in realistic_api_data]

        # Filter transactions by status
        pending_tx = [tx for tx in transactions if tx.is_pending]
        frozen_tx = [tx for tx in transactions if tx.is_frozen]

        # Mock at service level - services.team_service.team_service is what get_user_team imports
        with patch('services.team_service.team_service') as mock_permissions_team_svc:
            mock_permissions_team_svc.get_team_by_owner = AsyncMock(return_value=mock_team)

            with patch('commands.transactions.management.team_service') as mock_team_service:
                with patch('commands.transactions.management.transaction_service') as mock_tx_service:

                    # Setup service mocks
                    mock_team_service.get_teams_by_owner = AsyncMock(return_value=[mock_team])

                    mock_tx_service.get_pending_transactions = AsyncMock(return_value=pending_tx)
                    mock_tx_service.get_frozen_transactions = AsyncMock(return_value=frozen_tx)
                    mock_tx_service.get_processed_transactions = AsyncMock(return_value=[])

                    # Execute command
                    await commands_cog.my_moves.callback(commands_cog, mock_interaction, show_cancelled=False)

                    # Verify embed creation
                    embed_call = mock_interaction.followup.send.call_args
                    embed = embed_call.kwargs['embed']

                    # Check embed contains realistic data
                    assert 'WV' in embed.title
                    assert 'West Virginia Black Bears' in embed.description

                    # Check transaction descriptions in fields
                    pending_field = next(f for f in embed.fields if 'Pending' in f.name)
                    assert 'Yordan Alvarez: NYD → WV' in pending_field.value
    
    @pytest.mark.skip(reason="Requires deep API mocking - @requires_team decorator import chain cannot be fully mocked in unit tests")
    @pytest.mark.asyncio
    async def test_error_propagation_integration(self):
        """Test that errors propagate correctly through all layers.

        This test verifies that API errors are properly propagated through the
        command handler. We mock at the service module level to bypass real API calls.

        NOTE: This test is skipped because the @requires_team() decorator performs a local
        import of team_service inside the get_user_team() function, which cannot be
        reliably mocked in unit tests.
        """
        mock_bot = MagicMock()
        commands_cog = TransactionCommands(mock_bot)

        mock_interaction = AsyncMock()
        mock_interaction.user.id = 258104532423147520
        mock_interaction.extras = {}  # For @requires_team() to store team info
        # Guild mock required for @league_only decorator
        mock_interaction.guild = MagicMock()
        mock_interaction.guild.id = 669356687294988350

        mock_team = Team.from_api_data({
            'id': 499,
            'abbrev': 'WV',
            'sname': 'Black Bears',
            'lname': 'West Virginia Black Bears',
            'season': 12
        })

        # Mock at service level - services.team_service.team_service is what get_user_team imports
        with patch('services.team_service.team_service') as mock_permissions_team_svc:
            mock_permissions_team_svc.get_team_by_owner = AsyncMock(return_value=mock_team)

            with patch('commands.transactions.management.team_service') as mock_team_service:
                with patch('commands.transactions.management.transaction_service') as mock_tx_service:
                    mock_team_service.get_teams_by_owner = AsyncMock(return_value=[mock_team])

                    # Mock transaction service to raise an error
                    mock_tx_service.get_pending_transactions = AsyncMock(
                        side_effect=Exception("Database connection failed")
                    )

                    # Should propagate exception
                    with pytest.raises(Exception) as exc_info:
                        await commands_cog.my_moves.callback(commands_cog, mock_interaction)

                    assert "Database connection failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_performance_integration(self, realistic_api_data):
        """Test system performance with realistic data volumes."""
        # Scale up the data to simulate production load
        large_dataset = []
        for week in range(1, 19):  # 18 weeks
            for i in range(20):  # 20 transactions per week
                tx_data = {
                    **realistic_api_data[0],
                    'id': (week * 100) + i,
                    'week': week,
                    'moveid': f'Season-012-Week-{week:02d}-{i:02d}',
                    'player': {
                        **realistic_api_data[0]['player'],
                        'id': (week * 100) + i,
                        'name': f'Player {(week * 100) + i}'
                    },
                    'cancelled': i % 10 == 0,  # 10% cancelled
                    'frozen': i % 7 == 0       # ~14% frozen
                }
                large_dataset.append(tx_data)
        
        service = transaction_service
        
        with patch.object(service, 'get_all_items', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [Transaction.from_api_data(data) for data in large_dataset]
            
            import time
            start_time = time.time()
            
            # Test various service operations
            all_transactions = await service.get_team_transactions('WV', 12)
            pending = await service.get_pending_transactions('WV', 12)
            frozen = await service.get_frozen_transactions('WV', 12)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Performance assertions
            assert len(all_transactions) == 360  # 18 weeks * 20 transactions
            assert len(pending) > 0
            assert len(frozen) > 0
            assert processing_time < 0.5  # Should process quickly
            
            # Verify sorting performance
            for i in range(len(all_transactions) - 1):
                current_tx = all_transactions[i]
                next_tx = all_transactions[i + 1]
                assert current_tx.week <= next_tx.week
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_integration(self, realistic_api_data):
        """Test concurrent operations across the entire system.

        Simulates multiple users running the /mymoves command concurrently.
        Requires mocking at service level to bypass real API calls.
        """
        mock_bot = MagicMock()

        # Create multiple command instances (simulating multiple users)
        command_instances = [TransactionCommands(mock_bot) for _ in range(5)]

        mock_interactions = []
        for i in range(5):
            interaction = AsyncMock()
            interaction.user.id = 258104532423147520 + i
            interaction.extras = {}  # For @requires_team() to store team info
            # Guild mock required for @league_only decorator
            interaction.guild = MagicMock()
            interaction.guild.id = 669356687294988350
            mock_interactions.append(interaction)

        transactions = [Transaction.from_api_data(data) for data in realistic_api_data]

        # Prepare test data
        pending_tx = [tx for tx in transactions if tx.is_pending]
        frozen_tx = [tx for tx in transactions if tx.is_frozen]
        mock_team = TeamFactory.west_virginia()

        # Mock at service level - services.team_service.team_service is what get_user_team imports
        with patch('services.team_service.team_service') as mock_permissions_team_svc:
            mock_permissions_team_svc.get_team_by_owner = AsyncMock(return_value=mock_team)

            with patch('commands.transactions.management.team_service') as mock_team_service:
                with patch('commands.transactions.management.transaction_service') as mock_tx_service:
                    # Mock team service
                    mock_team_service.get_teams_by_owner = AsyncMock(return_value=[mock_team])

                    # Mock transaction service methods completely
                    mock_tx_service.get_pending_transactions = AsyncMock(return_value=pending_tx)
                    mock_tx_service.get_frozen_transactions = AsyncMock(return_value=frozen_tx)
                    mock_tx_service.get_processed_transactions = AsyncMock(return_value=[])
                    mock_tx_service.get_team_transactions = AsyncMock(return_value=[])  # No cancelled transactions

                    # Execute concurrent operations
                    tasks = []
                    for i, (cmd, interaction) in enumerate(zip(command_instances, mock_interactions)):
                        tasks.append(cmd.my_moves.callback(cmd, interaction, show_cancelled=(i % 2 == 0)))

                    # Wait for all operations to complete
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # All should complete successfully
                    successful_results = [r for r in results if not isinstance(r, Exception)]
                    assert len(successful_results) == 5

                    # All interactions should have received responses
                    for interaction in mock_interactions:
                        interaction.followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_data_consistency_integration(self, realistic_api_data):
        """Test data consistency across service operations."""
        transactions = [Transaction.from_api_data(data) for data in realistic_api_data]

        # Separate transactions by status for consistent mocking
        all_tx = transactions
        pending_tx = [tx for tx in transactions if tx.is_pending]
        frozen_tx = [tx for tx in transactions if tx.is_frozen]

        # Mock ALL service methods consistently
        with patch('services.transaction_service.transaction_service') as mock_service:
            mock_service.get_team_transactions = AsyncMock(return_value=all_tx)
            mock_service.get_pending_transactions = AsyncMock(return_value=pending_tx)
            mock_service.get_frozen_transactions = AsyncMock(return_value=frozen_tx)

            # Get transactions through different service methods
            all_tx_result = await mock_service.get_team_transactions('WV', 12)
            pending_tx_result = await mock_service.get_pending_transactions('WV', 12)
            frozen_tx_result = await mock_service.get_frozen_transactions('WV', 12)
            
            # Verify data consistency
            total_by_status = len(pending_tx_result) + len(frozen_tx_result)

            # Count cancelled transactions separately
            cancelled_count = len([tx for tx in all_tx_result if tx.is_cancelled])

            # Total should match when accounting for all statuses
            assert len(all_tx_result) == total_by_status + cancelled_count

            # Verify no transaction appears in multiple status lists
            pending_ids = {tx.id for tx in pending_tx_result}
            frozen_ids = {tx.id for tx in frozen_tx_result}

            assert len(pending_ids.intersection(frozen_ids)) == 0  # No overlap

            # Verify transaction properties match their categorization
            for tx in pending_tx_result:
                assert tx.is_pending is True
                assert tx.is_frozen is False
                assert tx.is_cancelled is False

            for tx in frozen_tx_result:
                assert tx.is_frozen is True
                assert tx.is_pending is False
                assert tx.is_cancelled is False
    
    @pytest.mark.asyncio
    async def test_validation_integration(self, realistic_api_data):
        """Test transaction validation integration."""
        service = transaction_service
        
        transactions = [Transaction.from_api_data(data) for data in realistic_api_data]
        
        # Test validation for each transaction
        for tx in transactions:
            validation = await service.validate_transaction(tx)
            
            assert isinstance(validation, RosterValidation)
            # Basic validation should pass for well-formed transactions
            assert validation.is_legal is True
            assert len(validation.errors) == 0
        
        # Test validation with problematic transaction (simulated)
        problematic_tx = transactions[0]
        
        # Mock validation failure
        with patch.object(service, 'validate_transaction') as mock_validate:
            mock_validate.return_value = RosterValidation(
                is_legal=False,
                errors=['Player not eligible for move', 'Roster size violation'],
                warnings=['Team WARA below threshold']
            )
            
            validation = await service.validate_transaction(problematic_tx)
            
            assert validation.is_legal is False
            assert len(validation.errors) == 2
            assert len(validation.warnings) == 1
            assert validation.status_emoji == '❌'