"""
Enhanced Logging Utilities

Provides structured logging with contextual information for Discord bot debugging.
Implements hybrid approach: human-readable console + structured JSON files.
"""
import contextvars
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Union

# Context variable for request tracking across async calls
log_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar('log_context', default={})

logger = logging.getLogger(f'{__name__}.logging_utils')

JSONValue = Union[
    str,
    int,
    float,
    bool,
    None,
    dict[str, Any],   # nested object
    list[Any]         # arrays
]


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured file logging."""
    
    def format(self, record) -> str:
        """Format log record as JSON with context information."""
        # Base log object
        log_obj: dict[str, JSONValue] = {
            'timestamp': datetime.now().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage()
        }
        
        # Add function/line info if available
        if hasattr(record, 'funcName') and record.funcName:
            log_obj['function'] = record.funcName
        if hasattr(record, 'lineno') and record.lineno:
            log_obj['line'] = record.lineno
        
        # Add exception info if present
        if record.exc_info:
            log_obj['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else 'Unknown',
                'message': str(record.exc_info[1]) if record.exc_info[1] else 'No message',
                'traceback': self.formatException(record.exc_info)
            }
        
        # Add context from contextvars
        context = log_context.get({})
        if context:
            log_obj['context'] = context.copy()
            
            # Promote trace_id to standard key if available in context
            if 'trace_id' in context:
                log_obj['trace_id'] = context['trace_id']
        
        # Add custom fields from extra parameter
        excluded_keys = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
            'filename', 'module', 'lineno', 'funcName', 'created', 
            'msecs', 'relativeCreated', 'thread', 'threadName', 
            'processName', 'process', 'getMessage', 'exc_info', 
            'exc_text', 'stack_info'
        }
        
        extra_data = {}
        for key, value in record.__dict__.items():
            if key not in excluded_keys:
                # Ensure JSON serializable
                try:
                    json.dumps(value)
                    extra_data[key] = value
                except (TypeError, ValueError):
                    extra_data[key] = str(value)
        
        if extra_data:
            log_obj['extra'] = extra_data
        
        return json.dumps(log_obj, ensure_ascii=False) + '\n'


class ContextualLogger:
    """
    Logger wrapper that provides contextual information and structured logging.
    
    Automatically includes Discord context (user, guild, command) in all log messages.
    """
    
    def __init__(self, logger_name: str):
        """
        Initialize contextual logger.
        
        Args:
            logger_name: Name for the underlying logger
        """
        self.logger = logging.getLogger(logger_name)
        self._start_time: Optional[float] = None
    
    def start_operation(self, operation_name: Optional[str] = None) -> str:
        """
        Start timing an operation and generate a trace ID.
        
        Args:
            operation_name: Optional name for the operation being tracked
            
        Returns:
            Generated trace ID for this operation
        """
        self._start_time = time.time()
        trace_id = str(uuid.uuid4())[:8]
        
        # Add trace_id to context
        current_context = log_context.get({})
        current_context['trace_id'] = trace_id
        if operation_name:
            current_context['operation'] = operation_name
        log_context.set(current_context)
        
        return trace_id
    
    def end_operation(self, trace_id: str, operation_result: str = "completed") -> None:
        """
        End an operation and log the final duration.
        
        Args:
            trace_id: The trace ID returned by start_operation
            operation_result: Result status (e.g., "completed", "failed", "cancelled")
        """
        if self._start_time is None:
            self.warning("end_operation called without corresponding start_operation")
            return
        
        duration_ms = int((time.time() - self._start_time) * 1000)
        
        # Get current context
        current_context = log_context.get({})
        
        # Log operation completion
        self.info(f"Operation {operation_result}", 
                 trace_id=trace_id,
                 final_duration_ms=duration_ms,
                 operation_result=operation_result)
        
        # Clear operation-specific context
        if 'operation' in current_context:
            current_context.pop('operation', None)
        if 'trace_id' in current_context and current_context['trace_id'] == trace_id:
            current_context.pop('trace_id', None)
        log_context.set(current_context)
        
        # Reset start time
        self._start_time = None
    
    def _get_duration_ms(self) -> Optional[int]:
        """Get operation duration in milliseconds if start_operation was called."""
        if self._start_time:
            return int((time.time() - self._start_time) * 1000)
        return None
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        duration = self._get_duration_ms()
        if duration is not None:
            kwargs['duration_ms'] = duration
        self.logger.debug(message, extra=kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        duration = self._get_duration_ms()
        if duration is not None:
            kwargs['duration_ms'] = duration
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        duration = self._get_duration_ms()
        if duration is not None:
            kwargs['duration_ms'] = duration
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """
        Log error message with context and exception information.
        
        Args:
            message: Error message
            error: Optional exception object
            **kwargs: Additional context
        """
        duration = self._get_duration_ms()
        if duration is not None:
            kwargs['duration_ms'] = duration
            
        if error:
            kwargs['error'] = {
                'type': type(error).__name__,
                'message': str(error)
            }
            self.logger.error(message, exc_info=True, extra=kwargs)
        else:
            self.logger.error(message, extra=kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with full traceback and context."""
        duration = self._get_duration_ms()
        if duration is not None:
            kwargs['duration_ms'] = duration
        self.logger.exception(message, extra=kwargs)


def set_discord_context(
    interaction: Optional[Any] = None,
    user_id: Optional[Union[str, int]] = None,
    guild_id: Optional[Union[str, int]] = None,
    channel_id: Optional[Union[str, int]] = None,
    command: Optional[str] = None,
    **additional_context
):
    """
    Set Discord-specific context for logging.
    
    Args:
        interaction: Discord interaction object (will extract user/guild/channel)
        user_id: Discord user ID
        guild_id: Discord guild ID  
        channel_id: Discord channel ID
        command: Command name (e.g., '/player')
        **additional_context: Any additional context to include
    """
    context = log_context.get({}).copy()
    
    # Extract from interaction if provided
    if interaction:
        context['user_id'] = str(interaction.user.id)
        if interaction.guild:
            context['guild_id'] = str(interaction.guild.id)
            context['guild_name'] = interaction.guild.name
        if interaction.channel:
            context['channel_id'] = str(interaction.channel.id)
        if hasattr(interaction, 'command') and interaction.command:
            context['command'] = f"/{interaction.command.name}"
    
    # Override with explicit parameters
    if user_id:
        context['user_id'] = str(user_id)
    if guild_id:
        context['guild_id'] = str(guild_id)
    if channel_id:
        context['channel_id'] = str(channel_id)
    if command:
        context['command'] = command
    
    # Add any additional context
    context.update(additional_context)
    
    log_context.set(context)


def clear_context():
    """Clear the current logging context."""
    log_context.set({})


def get_contextual_logger(logger_name: str) -> ContextualLogger:
    """
    Get a contextual logger instance.
    
    Args:
        logger_name: Name for the logger (typically __name__)
        
    Returns:
        ContextualLogger instance
    """
    return ContextualLogger(logger_name)