"""
Tests for Transaction Embed Views

Validates Discord UI components, modals, and interactive elements.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord

from views.transaction_embed import (
    TransactionEmbedView,
    RemoveMoveView,
    RemoveMoveSelect,
    SubmitConfirmationModal,
    create_transaction_embed
)
from services.transaction_builder import (
    TransactionBuilder,
    TransactionMove,
    RosterValidationResult
)
from models.team import Team, RosterType
from models.player import Player


class TestTransactionEmbedView:
    """Test TransactionEmbedView Discord UI component."""
    
    @pytest.fixture
    def mock_builder(self):
        """Create mock TransactionBuilder."""
        team = Team(id=499, abbrev='WV', sname='Black Bears', lname='West Virginia Black Bears', season=12)
        builder = MagicMock(spec=TransactionBuilder)
        builder.team = team
        builder.user_id = 123456789
        builder.season = 12
        builder.is_empty = False
        builder.move_count = 2
        builder.moves = []
        builder.created_at = MagicMock()
        builder.created_at.strftime.return_value = "10:30:15"
        return builder
    
    # Don't create view as fixture - create in test methods to ensure event loop is running
    
    @pytest.fixture
    def mock_interaction(self):
        """Create mock Discord interaction."""
        interaction = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 123456789
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.client = MagicMock()
        interaction.channel = MagicMock()
        return interaction
    
    @pytest.mark.asyncio
    async def test_interaction_check_correct_user(self, mock_builder, mock_interaction):
        """Test interaction check passes for correct user."""
        view = TransactionEmbedView(mock_builder, user_id=123456789)
        result = await view.interaction_check(mock_interaction)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_interaction_check_wrong_user(self, mock_builder, mock_interaction):
        """Test interaction check fails for wrong user."""
        view = TransactionEmbedView(mock_builder, user_id=123456789)
        mock_interaction.user.id = 999999999  # Different user
        
        result = await view.interaction_check(mock_interaction)
        
        assert result is False
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "don't have permission" in call_args[0][0]
        assert call_args[1]['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_remove_move_button_empty_builder(self, mock_builder, mock_interaction):
        """Test remove move button with empty builder."""
        view = TransactionEmbedView(mock_builder, user_id=123456789)
        view.builder.is_empty = True
        
        await view.remove_move_button.callback(mock_interaction)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "No moves to remove" in call_args[0][0]
        assert call_args[1]['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_remove_move_button_with_moves(self, mock_builder, mock_interaction):
        """Test remove move button with moves available."""
        view = TransactionEmbedView(mock_builder, user_id=123456789)
        view.builder.is_empty = False
        
        with patch('views.transaction_embed.create_transaction_embed') as mock_create_embed:
            mock_create_embed.return_value = MagicMock()
            
            await view.remove_move_button.callback(mock_interaction)
            
            mock_interaction.response.edit_message.assert_called_once()
            
            # Check that view is RemoveMoveView
            call_args = mock_interaction.response.edit_message.call_args
            view_arg = call_args[1]['view']
            assert isinstance(view_arg, RemoveMoveView)
    
    @pytest.mark.asyncio
    async def test_submit_button_empty_builder(self, mock_builder, mock_interaction):
        """Test submit button with empty builder."""
        view = TransactionEmbedView(mock_builder, user_id=123456789)
        view.builder.is_empty = True
        
        await view.submit_button.callback(mock_interaction)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "Cannot submit empty transaction" in call_args[0][0]
        assert call_args[1]['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_submit_button_illegal_transaction(self, mock_builder, mock_interaction):
        """Test submit button with illegal transaction."""
        view = TransactionEmbedView(mock_builder, user_id=123456789)
        view.builder.is_empty = False
        view.builder.validate_transaction = AsyncMock(return_value=RosterValidationResult(
            is_legal=False,
            major_league_count=26,
            minor_league_count=10,
            warnings=[],
            errors=["Too many players"],
            suggestions=["Drop 1 player"]
        ))
        
        await view.submit_button.callback(mock_interaction)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        message = call_args[0][0]
        assert "Cannot submit illegal transaction" in message
        assert "Too many players" in message
        assert "Drop 1 player" in message
        assert call_args[1]['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_submit_button_legal_transaction(self, mock_builder, mock_interaction):
        """Test submit button with legal transaction."""
        view = TransactionEmbedView(mock_builder, user_id=123456789)
        view.builder.is_empty = False
        view.builder.validate_transaction = AsyncMock(return_value=RosterValidationResult(
            is_legal=True,
            major_league_count=25,
            minor_league_count=10,
            warnings=[],
            errors=[],
            suggestions=[]
        ))
        
        await view.submit_button.callback(mock_interaction)
        
        # Should send confirmation modal
        mock_interaction.response.send_modal.assert_called_once()
        modal_arg = mock_interaction.response.send_modal.call_args[0][0]
        assert isinstance(modal_arg, SubmitConfirmationModal)
    
    @pytest.mark.asyncio
    async def test_cancel_button(self, mock_builder, mock_interaction):
        """Test cancel button clears moves and disables view."""
        view = TransactionEmbedView(mock_builder, user_id=123456789)
        with patch('views.transaction_embed.create_transaction_embed') as mock_create_embed:
            mock_create_embed.return_value = MagicMock()
            
            await view.cancel_button.callback(mock_interaction)
            
            # Should clear moves
            view.builder.clear_moves.assert_called_once()
            
            # Should edit message with disabled view
            mock_interaction.response.edit_message.assert_called_once()
            call_args = mock_interaction.response.edit_message.call_args
            assert "Transaction cancelled" in call_args[1]['content']




class TestSubmitConfirmationModal:
    """Test SubmitConfirmationModal functionality."""
    
    @pytest.fixture
    def mock_builder(self):
        """Create mock TransactionBuilder."""
        team = Team(id=499, abbrev='WV', sname='Black Bears', lname='West Virginia Black Bears', season=12)
        builder = MagicMock(spec=TransactionBuilder)
        builder.team = team
        builder.moves = []
        return builder
    
    @pytest.fixture
    def modal(self, mock_builder):
        """Create SubmitConfirmationModal instance."""
        return SubmitConfirmationModal(mock_builder)
    
    @pytest.fixture
    def mock_interaction(self):
        """Create mock Discord interaction."""
        interaction = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 123456789
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.client = MagicMock()
        interaction.channel = MagicMock()
        
        # Mock message history
        mock_message = MagicMock()
        mock_message.author = interaction.client.user
        mock_message.embeds = [MagicMock()]
        mock_message.embeds[0].title = "📋 Transaction Builder"
        mock_message.edit = AsyncMock()
        
        interaction.channel.history.return_value.__aiter__ = AsyncMock(return_value=iter([mock_message]))
        
        return interaction
    
    @pytest.mark.asyncio
    async def test_modal_submit_wrong_confirmation(self, mock_builder, mock_interaction):
        """Test modal submission with wrong confirmation text."""
        modal = SubmitConfirmationModal(mock_builder)
        # Mock the TextInput values
        modal.confirmation = MagicMock()
        modal.confirmation.value = 'WRONG'
        
        await modal.on_submit(mock_interaction)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "must type 'CONFIRM' exactly" in call_args[0][0]
        assert call_args[1]['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_modal_submit_correct_confirmation(self, mock_builder, mock_interaction):
        """Test modal submission with correct confirmation."""
        modal = SubmitConfirmationModal(mock_builder)
        # Mock the TextInput values
        modal.confirmation = MagicMock()
        modal.confirmation.value = 'CONFIRM'

        mock_transaction = MagicMock()
        mock_transaction.moveid = 'Season-012-Week-11-123456789'
        mock_transaction.week = 11
        mock_transaction.frozen = False  # Will be set to True

        with patch('services.league_service.league_service') as mock_league_service:
            mock_current_state = MagicMock()
            mock_current_state.week = 10
            mock_league_service.get_current_state = AsyncMock(return_value=mock_current_state)

            modal.builder.submit_transaction = AsyncMock(return_value=[mock_transaction])

            with patch('services.transaction_service.transaction_service') as mock_transaction_service:
                # Mock the create_transaction_batch call
                mock_transaction_service.create_transaction_batch = AsyncMock(return_value=[mock_transaction])

                with patch('utils.transaction_logging.post_transaction_to_log') as mock_post_log:
                    mock_post_log.return_value = AsyncMock()

                    with patch('services.transaction_builder.clear_transaction_builder') as mock_clear:
                        await modal.on_submit(mock_interaction)

                        # Should defer response
                        mock_interaction.response.defer.assert_called_once_with(ephemeral=True)

                        # Should get current state
                        mock_league_service.get_current_state.assert_called_once()

                        # Should submit transaction for next week
                        modal.builder.submit_transaction.assert_called_once_with(week=11)

                        # Should mark transaction as frozen
                        assert mock_transaction.frozen is True

                        # Should POST to database
                        mock_transaction_service.create_transaction_batch.assert_called_once()

                        # Should clear builder
                        mock_clear.assert_called_once_with(123456789)

                        # Should send success message
                        mock_interaction.followup.send.assert_called_once()
                        call_args = mock_interaction.followup.send.call_args
                        assert "Transaction Submitted Successfully" in call_args[0][0]
                        assert mock_transaction.moveid in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_modal_submit_no_current_state(self, mock_builder, mock_interaction):
        """Test modal submission when current state unavailable."""
        modal = SubmitConfirmationModal(mock_builder)
        # Mock the TextInput values
        modal.confirmation = MagicMock()
        modal.confirmation.value = 'CONFIRM'

        with patch('services.league_service.league_service') as mock_league_service:
            mock_league_service.get_current_state = AsyncMock(return_value=None)

            await modal.on_submit(mock_interaction)

            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            assert "Could not get current league state" in call_args[0][0]
            assert call_args[1]['ephemeral'] is True


class TestEmbedCreation:
    """Test embed creation functions."""
    
    @pytest.fixture
    def mock_builder_empty(self):
        """Create empty mock TransactionBuilder."""
        team = Team(id=499, abbrev='WV', sname='Black Bears', lname='West Virginia Black Bears', season=12)
        builder = MagicMock(spec=TransactionBuilder)
        builder.team = team
        builder.is_empty = True
        builder.move_count = 0
        builder.moves = []
        builder.created_at = MagicMock()
        builder.created_at.strftime.return_value = "10:30:15"
        builder.validate_transaction = AsyncMock(return_value=RosterValidationResult(
            is_legal=True,
            major_league_count=24,
            minor_league_count=10,
            warnings=[],
            errors=[],
            suggestions=["Add player moves to build your transaction"]
        ))
        return builder
    
    @pytest.fixture
    def mock_builder_with_moves(self):
        """Create mock TransactionBuilder with moves."""
        team = Team(id=499, abbrev='WV', sname='Black Bears', lname='West Virginia Black Bears', season=12)
        builder = MagicMock(spec=TransactionBuilder)
        builder.team = team
        builder.is_empty = False
        builder.move_count = 2
        
        mock_moves = []
        for i in range(2):
            move = MagicMock()
            move.description = f"Move {i+1}: Player → Team"
            mock_moves.append(move)
        builder.moves = mock_moves
        
        builder.created_at = MagicMock()
        builder.created_at.strftime.return_value = "10:30:15"
        builder.validate_transaction = AsyncMock(return_value=RosterValidationResult(
            is_legal=False,
            major_league_count=26,
            minor_league_count=10,
            warnings=["Warning message"],
            errors=["Error message"],
            suggestions=["Suggestion message"]
        ))
        return builder
    
    @pytest.mark.asyncio
    async def test_create_transaction_embed_empty(self, mock_builder_empty):
        """Test creating embed for empty transaction."""
        embed = await create_transaction_embed(mock_builder_empty)
        
        assert isinstance(embed, discord.Embed)
        assert "Transaction Builder - WV" in embed.title
        assert "📋" in embed.title
        
        # Should have fields for empty state
        field_names = [field.name for field in embed.fields]
        assert "Current Moves" in field_names
        assert "Roster Status" in field_names
        assert "Suggestions" in field_names
        
        # Check empty moves message
        moves_field = next(field for field in embed.fields if field.name == "Current Moves")
        assert "No moves yet" in moves_field.value

        # Check for Add More Moves instruction field
        field_names = [field.name for field in embed.fields]
        assert "➕ Add More Moves" in field_names
        add_moves_field = next(field for field in embed.fields if field.name == "➕ Add More Moves")
        assert "/dropadd" in add_moves_field.value
    
    @pytest.mark.asyncio
    async def test_create_transaction_embed_with_moves(self, mock_builder_with_moves):
        """Test creating embed for transaction with moves."""
        embed = await create_transaction_embed(mock_builder_with_moves)
        
        assert isinstance(embed, discord.Embed)
        assert "Transaction Builder - WV" in embed.title
        
        # Should have all fields
        field_names = [field.name for field in embed.fields]
        assert "Current Moves (2)" in field_names
        assert "Roster Status" in field_names
        assert "❌ Errors" in field_names
        assert "Suggestions" in field_names
        
        # Check moves content
        moves_field = next(field for field in embed.fields if "Current Moves" in field.name)
        assert "Move 1: Player → Team" in moves_field.value
        assert "Move 2: Player → Team" in moves_field.value

        # Check for Add More Moves instruction field
        field_names = [field.name for field in embed.fields]
        assert "➕ Add More Moves" in field_names
        add_moves_field = next(field for field in embed.fields if field.name == "➕ Add More Moves")
        assert "/dropadd" in add_moves_field.value
    