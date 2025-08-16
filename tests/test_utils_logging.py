"""
Tests for enhanced logging utilities

Tests contextual logging, operation tracing, and Discord context management.
"""
import pytest
import time
from unittest.mock import Mock, patch
from typing import Dict, Any

from utils.logging import (
    get_contextual_logger, 
    set_discord_context, 
    clear_context,
    ContextualLogger,
    JSONFormatter,
    log_context
)


class TestContextualLogger:
    """Test contextual logger functionality."""
    
    @pytest.fixture
    def logger(self) -> ContextualLogger:
        """Create a test contextual logger."""
        return get_contextual_logger('test_logger')
    
    def test_start_operation(self, logger):
        """Test operation start tracking."""
        trace_id = logger.start_operation('test_operation')
        
        assert trace_id is not None
        assert len(trace_id) == 8  # UUID truncated to 8 chars
        assert logger._start_time is not None
        
        # Check that context was set
        context = log_context.get({})
        assert 'trace_id' in context
        assert context['trace_id'] == trace_id
        assert context['operation'] == 'test_operation'
    
    def test_start_operation_no_name(self, logger):
        """Test operation start without operation name."""
        # Clear any existing context first
        clear_context()
        
        trace_id = logger.start_operation()
        
        assert trace_id is not None
        assert logger._start_time is not None
        
        context = log_context.get({})
        assert 'trace_id' in context
        assert context['trace_id'] == trace_id
        assert 'operation' not in context
    
    def test_end_operation_success(self, logger):
        """Test successful operation end tracking."""
        trace_id = logger.start_operation('test_operation')
        time.sleep(0.01)  # Small delay to ensure duration > 0
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.end_operation(trace_id, 'completed')
            
            # Verify info was called with correct parameters
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert 'Operation completed' in call_args[0][0]
            
            # Check extra parameters
            extra = call_args[1]['extra']
            assert 'trace_id' in extra
            assert 'final_duration_ms' in extra
            assert extra['final_duration_ms'] > 0
            assert extra['operation_result'] == 'completed'
        
        # Verify context was cleared
        assert logger._start_time is None
    
    def test_end_operation_without_start(self, logger):
        """Test end_operation called without start_operation."""
        with patch.object(logger, 'warning') as mock_warning:
            logger.end_operation('fake_trace_id', 'completed')
            
            mock_warning.assert_called_once_with(
                "end_operation called without corresponding start_operation"
            )
    
    def test_end_operation_clears_context(self, logger):
        """Test that end_operation properly clears context."""
        trace_id = logger.start_operation('test_operation')
        
        # Verify context is set
        context_before = log_context.get({})
        assert 'trace_id' in context_before
        assert 'operation' in context_before
        
        logger.end_operation(trace_id, 'completed')
        
        # Verify context was cleared
        context_after = log_context.get({})
        assert 'trace_id' not in context_after or context_after.get('trace_id') != trace_id
        assert 'operation' not in context_after
    
    def test_duration_tracking(self, logger):
        """Test that duration is tracked correctly."""
        logger.start_operation('test_operation')
        time.sleep(0.01)
        
        duration_ms = logger._get_duration_ms()
        assert duration_ms is not None
        assert duration_ms > 0
        assert duration_ms < 1000  # Should be less than 1 second
    
    def test_logging_methods_with_duration(self, logger):
        """Test that logging methods include duration when operation is active."""
        trace_id = logger.start_operation('test_operation')
        time.sleep(0.01)
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.info('test message', extra_param='value')
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            
            assert call_args[0][0] == 'test message'
            extra = call_args[1]['extra']
            assert 'duration_ms' in extra
            assert extra['duration_ms'] > 0
            assert extra['extra_param'] == 'value'
    
    def test_error_logging_with_exception(self, logger):
        """Test error logging with exception object."""
        logger.start_operation('test_operation')
        test_exception = ValueError("Test error")
        
        with patch.object(logger.logger, 'error') as mock_error:
            logger.error('Error occurred', error=test_exception, context='test')
            
            mock_error.assert_called_once()
            call_args = mock_error.call_args
            
            assert call_args[0][0] == 'Error occurred'
            assert call_args[1]['exc_info'] is True
            
            extra = call_args[1]['extra']
            assert 'error' in extra
            assert extra['error']['type'] == 'ValueError'
            assert extra['error']['message'] == 'Test error'
            assert extra['context'] == 'test'
    
    def test_error_logging_without_exception(self, logger):
        """Test error logging without exception object."""
        with patch.object(logger.logger, 'error') as mock_error:
            logger.error('Error occurred', context='test')
            
            mock_error.assert_called_once()
            call_args = mock_error.call_args
            
            assert call_args[0][0] == 'Error occurred'
            assert 'exc_info' not in call_args[1]
            
            extra = call_args[1]['extra']
            assert 'error' not in extra
            assert extra['context'] == 'test'


class TestDiscordContext:
    """Test Discord context management."""
    
    def setUp(self):
        """Clear context before each test."""
        clear_context()
    
    def test_set_discord_context_with_interaction(self):
        """Test setting context from Discord interaction."""
        # Mock interaction object
        mock_interaction = Mock()
        mock_interaction.user.id = 123456789
        mock_interaction.guild.id = 987654321
        mock_interaction.guild.name = "Test Guild"
        mock_interaction.channel.id = 555666777
        mock_interaction.command.name = "test"
        
        set_discord_context(interaction=mock_interaction, command="/test")
        
        context = log_context.get({})
        assert context['user_id'] == '123456789'
        assert context['guild_id'] == '987654321'
        assert context['guild_name'] == "Test Guild"
        assert context['channel_id'] == '555666777'
        assert context['command'] == '/test'
    
    def test_set_discord_context_explicit_params(self):
        """Test setting context with explicit parameters."""
        set_discord_context(
            user_id=123456789,
            guild_id=987654321,
            channel_id=555666777,
            command='/explicit',
            custom_field='custom_value'
        )
        
        context = log_context.get({})
        assert context['user_id'] == '123456789'
        assert context['guild_id'] == '987654321'
        assert context['channel_id'] == '555666777'
        assert context['command'] == '/explicit'
        assert context['custom_field'] == 'custom_value'
    
    def test_set_discord_context_override(self):
        """Test that explicit parameters override interaction values."""
        mock_interaction = Mock()
        mock_interaction.user.id = 111111111
        mock_interaction.guild.id = 222222222
        mock_interaction.channel.id = 333333333
        
        set_discord_context(
            interaction=mock_interaction,
            user_id=999999999,  # Override
            command='/override'
        )
        
        context = log_context.get({})
        assert context['user_id'] == '999999999'  # Overridden value
        assert context['guild_id'] == '222222222'  # From interaction
        assert context['command'] == '/override'
    
    def test_clear_context(self):
        """Test context clearing."""
        set_discord_context(user_id=123, command='/test')
        
        # Verify context is set
        context_before = log_context.get({})
        assert len(context_before) > 0
        
        clear_context()
        
        # Verify context is cleared
        context_after = log_context.get({})
        assert len(context_after) == 0


class TestJSONFormatter:
    """Test JSON formatter functionality."""
    
    @pytest.fixture
    def formatter(self) -> JSONFormatter:
        """Create a JSON formatter instance."""
        return JSONFormatter()
    
    def test_json_formatter_basic(self, formatter):
        """Test basic JSON formatting."""
        import logging
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        result = formatter.format(record)
        
        # Should be valid JSON
        import json
        data = json.loads(result)
        
        assert data['message'] == 'Test message'
        assert data['level'] == 'INFO'
        assert data['logger'] == 'test_logger'
        assert 'timestamp' in data
    
    def test_json_formatter_with_extra(self, formatter):
        """Test JSON formatting with extra fields."""
        import logging
        record = logging.LogRecord(
            name='test_logger',
            level=logging.ERROR,
            pathname='test.py',
            lineno=10,
            msg='Error message',
            args=(),
            exc_info=None
        )
        
        # Add extra fields
        record.user_id = '123456789'
        record.trace_id = 'abc123'
        record.duration_ms = 150
        
        result = formatter.format(record)
        
        import json
        data = json.loads(result)
        
        assert data['message'] == 'Error message'
        assert data['level'] == 'ERROR'
        # trace_id comes from context, duration_ms goes back to extra
        assert 'extra' in data
        assert data['extra']['user_id'] == '123456789'
        assert data['extra']['trace_id'] == 'abc123'  # This will be in extra since not set via context
        assert data['extra']['duration_ms'] == 150
    
    def test_json_formatter_with_context_trace_id(self, formatter):
        """Test JSON formatting with trace_id from context."""
        import logging
        from utils.logging import log_context
        
        # Set trace_id in context
        log_context.set({'trace_id': 'context123', 'operation': 'test_op'})
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=15,
            msg='Context message',
            args=(),
            exc_info=None
        )
        
        result = formatter.format(record)
        
        import json
        data = json.loads(result)
        
        assert data['message'] == 'Context message'
        assert data['level'] == 'INFO'
        # trace_id should be promoted to standard key from context
        assert data['trace_id'] == 'context123'
        # context should still be present
        assert 'context' in data
        assert data['context']['trace_id'] == 'context123'
        assert data['context']['operation'] == 'test_op'
        
        # Clean up context
        log_context.set({})


class TestLoggerFactory:
    """Test logger factory functions."""
    
    def test_get_contextual_logger(self):
        """Test contextual logger factory."""
        logger = get_contextual_logger('test.module')
        
        assert isinstance(logger, ContextualLogger)
        assert logger.logger.name == 'test.module'
    
    def test_get_contextual_logger_unique_instances(self):
        """Test that each call returns a new instance."""
        logger1 = get_contextual_logger('test1')
        logger2 = get_contextual_logger('test2')
        
        assert logger1 is not logger2
        assert logger1.logger.name == 'test1'
        assert logger2.logger.name == 'test2'