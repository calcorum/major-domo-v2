"""
Tests for the logging decorator utility
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
import discord

from utils.decorators import logged_command
from utils.logging import get_contextual_logger


class MockInteraction:
    """Mock Discord interaction for testing"""
    def __init__(self, user_id="123456", guild_id="987654", guild_name="Test Guild", channel_id="555666"):
        self.user = Mock()
        self.user.id = user_id
        self.guild = Mock()
        self.guild.id = guild_id
        self.guild.name = guild_name
        self.channel = Mock()
        self.channel.id = channel_id


class MockCog:
    """Mock command class for testing decorator"""
    def __init__(self):
        self.logger = get_contextual_logger(f'{__name__}.MockCog')
    
    @logged_command("/test-command")
    async def test_command(self, interaction, param1: str, param2: int = 5):
        """Test command for decorator"""
        return f"Success: {param1}-{param2}"
    
    @logged_command("/error-command")
    async def error_command(self, interaction, param1: str):
        """Test command that raises an error"""
        raise ValueError("Test error")


@pytest.fixture
def mock_interaction():
    """Create a mock Discord interaction"""
    return MockInteraction()


@pytest.fixture
def mock_cog():
    """Create a mock cog instance"""
    return MockCog()


class TestLoggedCommandDecorator:
    """Test the logged_command decorator"""
    
    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self, mock_cog):
        """Test that decorator preserves function name, docstring, etc."""
        assert mock_cog.test_command.__name__ == "test_command"
        assert "Test command for decorator" in mock_cog.test_command.__doc__
    
    @pytest.mark.asyncio
    async def test_decorator_preserves_signature(self, mock_cog):
        """Test that decorator preserves function signature for Discord.py"""
        import inspect
        sig = inspect.signature(mock_cog.test_command)
        param_names = list(sig.parameters.keys())
        
        # For bound methods, 'self' won't appear in the signature
        # Discord.py cares about the interaction and command parameters
        assert "interaction" in param_names
        assert "param1" in param_names
        assert "param2" in param_names
        
        # Check parameter details
        assert sig.parameters['param1'].annotation == str
        assert sig.parameters['param2'].annotation == int
        assert sig.parameters['param2'].default == 5
    
    @pytest.mark.asyncio
    async def test_successful_command_execution(self, mock_cog, mock_interaction):
        """Test that decorator allows successful command execution"""
        with patch('utils.decorators.set_discord_context') as mock_context:
            result = await mock_cog.test_command(mock_interaction, "test", 10)
            
            # Should return the expected result
            assert result == "Success: test-10"
            
            # Should have set Discord context
            mock_context.assert_called_once()
            call_args = mock_context.call_args
            assert call_args[1]['command'] == "/test-command"
            assert call_args[1]['param_param1'] == "test"
            assert call_args[1]['param_param2'] == 10
    
    @pytest.mark.asyncio
    async def test_command_with_exception(self, mock_cog, mock_interaction):
        """Test that decorator handles exceptions properly"""
        with patch('utils.decorators.set_discord_context'):
            with pytest.raises(ValueError, match="Test error"):
                await mock_cog.error_command(mock_interaction, "test")
    
    @pytest.mark.asyncio
    async def test_logging_integration(self, mock_cog, mock_interaction):
        """Test that decorator integrates with logging system"""
        with patch('utils.decorators.set_discord_context') as mock_context:
            with patch.object(mock_cog.logger, 'start_operation', return_value="trace123") as mock_start:
                with patch.object(mock_cog.logger, 'end_operation') as mock_end:
                    with patch.object(mock_cog.logger, 'info') as mock_info:
                        
                        result = await mock_cog.test_command(mock_interaction, "test", 7)
                        
                        # Verify logging calls
                        mock_start.assert_called_once_with("test_command_command")
                        mock_end.assert_called_once_with("trace123", "completed")
                        
                        # Should log start and completion
                        assert mock_info.call_count == 2
                        info_calls = [call[0][0] for call in mock_info.call_args_list]
                        assert "/test-command command started" in info_calls
                        assert "/test-command command completed successfully" in info_calls
    
    @pytest.mark.asyncio
    async def test_error_logging(self, mock_cog, mock_interaction):
        """Test that decorator logs errors properly"""
        with patch('utils.decorators.set_discord_context'):
            with patch.object(mock_cog.logger, 'start_operation', return_value="trace123") as mock_start:
                with patch.object(mock_cog.logger, 'end_operation') as mock_end:
                    with patch.object(mock_cog.logger, 'error') as mock_error:
                        with patch.object(mock_cog.logger, 'info') as mock_info:
                            
                            with pytest.raises(ValueError):
                                await mock_cog.error_command(mock_interaction, "test")
                            
                            # Verify error logging
                            mock_start.assert_called_once_with("error_command_command")
                            mock_end.assert_called_once_with("trace123", "failed")
                            mock_error.assert_called_once()
                            
                            # Should log start but not completion
                            mock_info.assert_called_once()
                            assert "/error-command command started" in mock_info.call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_parameter_exclusion(self, mock_interaction):
        """Test that sensitive parameters can be excluded from logging"""
        class TestCogWithExclusion:
            def __init__(self):
                self.logger = get_contextual_logger(f'{__name__}.TestCogWithExclusion')
            
            @logged_command("/secure-command", exclude_params=["password"])
            async def secure_command(self, interaction, username: str, password: str):
                return f"Login: {username}"
        
        cog = TestCogWithExclusion()
        
        with patch('utils.decorators.set_discord_context') as mock_context:
            await cog.secure_command(mock_interaction, "user123", "secret123")
            
            call_args = mock_context.call_args[1]
            assert call_args['param_username'] == "user123"
            # Password should not be in the logged parameters
            assert 'param_password' not in call_args
    
    @pytest.mark.asyncio
    async def test_auto_command_name_detection(self, mock_interaction):
        """Test that command names are auto-detected from function names"""
        class TestCogAutoName:
            def __init__(self):
                self.logger = get_contextual_logger(f'{__name__}.TestCogAutoName')
            
            @logged_command()  # No explicit command name
            async def player_info_command(self, interaction, player_name: str):
                return f"Player: {player_name}"
        
        cog = TestCogAutoName()
        
        with patch('utils.decorators.set_discord_context') as mock_context:
            await cog.player_info_command(mock_interaction, "Mike Trout")
            
            call_args = mock_context.call_args[1]
            # Should convert function name to command format
            assert call_args['command'] == "/player-info-command"
    
    @pytest.mark.asyncio
    async def test_logger_fallback(self, mock_interaction):
        """Test that decorator creates logger if class doesn't have one"""
        class TestCogNoLogger:
            # No logger attribute
            
            @logged_command("/fallback-command")
            async def test_command(self, interaction, param: str):
                return f"Result: {param}"
        
        cog = TestCogNoLogger()
        
        with patch('utils.decorators.set_discord_context'):
            with patch('utils.decorators.get_contextual_logger') as mock_get_logger:
                mock_logger = Mock()
                mock_logger.start_operation.return_value = "trace123"
                mock_get_logger.return_value = mock_logger
                
                result = await cog.test_command(mock_interaction, "test")
                
                # Should create a logger when none exists
                mock_get_logger.assert_called_once_with(f'{TestCogNoLogger.__module__}.{TestCogNoLogger.__name__}')
                assert result == "Result: test"


class TestDecoratorEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.mark.asyncio
    async def test_decorator_with_default_parameters(self, mock_interaction):
        """Test decorator behavior with function default parameters"""
        class TestCogDefaults:
            def __init__(self):
                self.logger = get_contextual_logger(f'{__name__}.TestCogDefaults')
            
            @logged_command("/default-test")
            async def command_with_defaults(self, interaction, required: str, optional: str = "default"):
                return f"{required}-{optional}"
        
        cog = TestCogDefaults()
        
        with patch('utils.decorators.set_discord_context') as mock_context:
            # Test with default parameter
            result = await cog.command_with_defaults(mock_interaction, "test")
            
            call_args = mock_context.call_args[1]
            assert call_args['param_required'] == "test"
            # Default parameter should not appear in args since it wasn't passed
            assert 'param_optional' not in call_args
            assert result == "test-default"
    
    @pytest.mark.asyncio
    async def test_decorator_parameter_logging_disabled(self, mock_interaction):
        """Test decorator with parameter logging disabled"""
        class TestCogNoParams:
            def __init__(self):
                self.logger = get_contextual_logger(f'{__name__}.TestCogNoParams')
            
            @logged_command("/no-params", log_params=False)
            async def command_no_param_logging(self, interaction, sensitive_data: str):
                return f"Processed: {len(sensitive_data)} chars"
        
        cog = TestCogNoParams()
        
        with patch('utils.decorators.set_discord_context') as mock_context:
            await cog.command_no_param_logging(mock_interaction, "secret_data")
            
            call_args = mock_context.call_args[1]
            assert call_args['command'] == "/no-params"
            # No parameter logging should occur
            assert 'param_sensitive_data' not in call_args