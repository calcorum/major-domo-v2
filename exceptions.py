"""
Custom exceptions for Discord Bot v2.0

Uses modern error handling patterns with discord.py's built-in error handling.
No decorators - rely on global error handlers and explicit try/catch blocks.
"""


class BotException(Exception):
    """Base exception for all bot-related errors."""
    pass


class APIException(BotException):
    """Exception for API-related errors."""
    pass


class PlayerNotFoundError(BotException):
    """Raised when a requested player cannot be found."""
    pass


class TeamNotFoundError(BotException):
    """Raised when a requested team cannot be found."""
    pass


class DraftException(BotException):
    """Exception for draft-related errors."""
    pass


class ValidationException(BotException):
    """Exception for data validation errors."""
    pass


class ConfigurationException(BotException):
    """Exception for configuration-related errors."""
    pass