"""
Tests for custom exceptions

Ensures exception hierarchy and behavior work correctly.
"""
import pytest

from exceptions import (
    BotException,
    APIException,
    PlayerNotFoundError,
    TeamNotFoundError,
    DraftException,
    ValidationException,
    ConfigurationException
)


class TestExceptionHierarchy:
    """Test that exceptions inherit correctly."""
    
    def test_all_exceptions_inherit_from_bot_exception(self):
        """Test that all custom exceptions inherit from BotException."""
        assert issubclass(APIException, BotException)
        assert issubclass(PlayerNotFoundError, BotException)
        assert issubclass(TeamNotFoundError, BotException)
        assert issubclass(DraftException, BotException)
        assert issubclass(ValidationException, BotException)
        assert issubclass(ConfigurationException, BotException)
    
    def test_bot_exception_inherits_from_exception(self):
        """Test that BotException inherits from built-in Exception."""
        assert issubclass(BotException, Exception)
    
    def test_exceptions_can_be_instantiated(self):
        """Test that all exceptions can be created with messages."""
        message = "Test error message"
        
        exceptions = [
            BotException(message),
            APIException(message),
            PlayerNotFoundError(message),
            TeamNotFoundError(message),
            DraftException(message),
            ValidationException(message),
            ConfigurationException(message)
        ]
        
        for exc in exceptions:
            assert str(exc) == message
            assert isinstance(exc, Exception)
    
    def test_exceptions_can_be_raised_and_caught(self):
        """Test that exceptions can be raised and caught properly."""
        # Test specific exception catching
        with pytest.raises(PlayerNotFoundError):
            raise PlayerNotFoundError("Player not found")
        
        # Test catching by parent class
        with pytest.raises(BotException):
            raise APIException("API error")
        
        # Test catching by base Exception
        with pytest.raises(Exception):
            raise ValidationException("Validation error")


class TestExceptionMessages:
    """Test exception message handling."""
    
    def test_exceptions_with_no_message(self):
        """Test that exceptions work without explicit messages."""
        exc = APIException()
        assert isinstance(exc, APIException)
        # Should not raise when converted to string
        str(exc)
    
    def test_exceptions_preserve_message(self):
        """Test that exception messages are preserved correctly."""
        message = "Detailed error description"
        exc = PlayerNotFoundError(message)
        assert str(exc) == message
    
    def test_exceptions_with_formatting(self):
        """Test exceptions with formatted messages."""
        player_name = "John Doe"
        exc = PlayerNotFoundError(f"Player '{player_name}' was not found")
        assert "John Doe" in str(exc)
        assert "not found" in str(exc)


class TestSpecificExceptions:
    """Test specific exception use cases."""
    
    def test_player_not_found_error(self):
        """Test PlayerNotFoundError for missing players."""
        with pytest.raises(PlayerNotFoundError) as exc_info:
            raise PlayerNotFoundError("Player 'Mike Trout' not found")
        
        assert "Mike Trout" in str(exc_info.value)
    
    def test_team_not_found_error(self):
        """Test TeamNotFoundError for missing teams."""
        with pytest.raises(TeamNotFoundError) as exc_info:
            raise TeamNotFoundError("Team 'LAA' not found")
        
        assert "LAA" in str(exc_info.value)
    
    def test_api_exception(self):
        """Test APIException for API-related errors."""
        with pytest.raises(APIException) as exc_info:
            raise APIException("Database connection failed")
        
        assert "Database connection failed" in str(exc_info.value)
    
    def test_draft_exception(self):
        """Test DraftException for draft-related errors."""
        with pytest.raises(DraftException) as exc_info:
            raise DraftException("Draft is not currently active")
        
        assert "Draft is not currently active" in str(exc_info.value)