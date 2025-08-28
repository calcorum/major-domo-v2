"""
Tests for configuration management

Ensures configuration loading, validation, and environment handling work correctly.
"""
import os
import pytest
from unittest.mock import patch

from config import BotConfig
from exceptions import ConfigurationException


class TestBotConfig:
    """Test configuration loading and validation."""
    
    def test_config_loads_required_fields(self):
        """Test that config loads all required fields from environment."""
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_bot_token',
            'GUILD_ID': '123456789',
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com'
        }):
            config = BotConfig()
            assert config.bot_token == 'test_bot_token'
            assert config.guild_id == 123456789
            assert config.api_token == 'test_api_token'
            assert config.db_url == 'https://api.example.com'
    
    def test_config_has_default_values(self):
        """Test that config provides sensible defaults."""
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_bot_token',
            'GUILD_ID': '123456789',
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com'
        }, clear=True):
            # Create config with disabled env file to test true defaults
            config = BotConfig(_env_file=None)
            assert config.sba_season == 12
            assert config.pd_season == 9
            assert config.fa_lock_week == 14
            assert config.sba_color == "a6ce39"
            assert config.log_level == "INFO"
            assert config.environment == "development"
            assert config.testing is False
    
    def test_config_overrides_defaults_from_env(self):
        """Test that environment variables override default values."""
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_bot_token',
            'GUILD_ID': '123456789',
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com',
            'SBA_SEASON': '15',
            'LOG_LEVEL': 'DEBUG',
            'ENVIRONMENT': 'production',
            'TESTING': 'true'
        }):
            config = BotConfig()
            assert config.sba_season == 15
            assert config.log_level == "DEBUG"
            assert config.environment == "production"
            assert config.testing is True
    
    def test_config_ignores_extra_env_vars(self):
        """Test that extra environment variables are ignored."""
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_bot_token',
            'GUILD_ID': '123456789',
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com',
            'RANDOM_EXTRA_VAR': 'should_be_ignored',
            'ANOTHER_RANDOM_VAR': 'also_ignored'
        }):
            # Should not raise validation error
            config = BotConfig()
            assert config.bot_token == 'test_bot_token'
            
            # Extra vars should not be accessible
            assert not hasattr(config, 'random_extra_var')
            assert not hasattr(config, 'another_random_var')
    
    def test_config_converts_string_to_int(self):
        """Test that guild_id is properly converted from string to int."""
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_bot_token',
            'GUILD_ID': '987654321',  # String input
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com'
        }):
            config = BotConfig()
            assert config.guild_id == 987654321
            assert isinstance(config.guild_id, int)
    
    def test_config_converts_string_to_bool(self):
        """Test that boolean fields are properly converted."""
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_bot_token',
            'GUILD_ID': '123456789',
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com',
            'TESTING': 'false'
        }):
            config = BotConfig()
            assert config.testing is False
            assert isinstance(config.testing, bool)
        
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_bot_token',
            'GUILD_ID': '123456789',
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com',
            'TESTING': '1'
        }):
            config = BotConfig()
            assert config.testing is True
    
    def test_config_case_insensitive(self):
        """Test that environment variables are case insensitive."""
        with patch.dict(os.environ, {
            'bot_token': 'test_bot_token',  # lowercase
            'GUILD_ID': '123456789',        # uppercase
            'Api_Token': 'test_api_token',  # mixed case
            'db_url': 'https://api.example.com'
        }):
            config = BotConfig()
            assert config.bot_token == 'test_bot_token'
            assert config.api_token == 'test_api_token'
            assert config.db_url == 'https://api.example.com'
    
    def test_is_development_property(self):
        """Test the is_development property."""
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_bot_token',
            'GUILD_ID': '123456789',
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com',
            'ENVIRONMENT': 'development'
        }):
            config = BotConfig()
            assert config.is_development is True
        
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_bot_token',
            'GUILD_ID': '123456789',
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com',
            'ENVIRONMENT': 'production'
        }):
            config = BotConfig()
            assert config.is_development is False
    
    def test_is_testing_property(self):
        """Test the is_testing property."""
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_bot_token',
            'GUILD_ID': '123456789',
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com',
            'TESTING': 'true'
        }):
            config = BotConfig()
            assert config.is_testing is True
        
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_bot_token',
            'GUILD_ID': '123456789',
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com',
            'TESTING': 'false'
        }):
            config = BotConfig()
            assert config.is_testing is False


class TestConfigValidation:
    """Test configuration validation and error handling."""
    
    def test_missing_required_field_raises_error(self):
        """Test that missing required fields raise validation errors."""
        # Missing BOT_TOKEN
        with patch.dict(os.environ, {
            'GUILD_ID': '123456789',
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com'
        }, clear=True):
            with pytest.raises(Exception):  # Pydantic ValidationError
                BotConfig(_env_file=None)
        
        # Missing GUILD_ID
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_bot_token',
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com'
        }, clear=True):
            with pytest.raises(Exception):  # Pydantic ValidationError
                BotConfig(_env_file=None)
    
    def test_invalid_guild_id_raises_error(self):
        """Test that invalid guild_id values raise validation errors."""
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_bot_token',
            'GUILD_ID': 'not_a_number',
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com'
        }):
            with pytest.raises(Exception):  # Pydantic ValidationError
                BotConfig()
    
    def test_empty_required_field_is_allowed(self):
        """Test that empty required fields are allowed (Pydantic default behavior)."""
        with patch.dict(os.environ, {
            'BOT_TOKEN': '',  # Empty string
            'GUILD_ID': '123456789',
            'API_TOKEN': 'test_api_token',
            'DB_URL': 'https://api.example.com'
        }):
            # Should not raise - Pydantic allows empty strings by default
            config = BotConfig()
            assert config.bot_token == ''


@pytest.fixture
def valid_config():
    """Provide a valid configuration for testing."""
    with patch.dict(os.environ, {
        'BOT_TOKEN': 'test_bot_token',
        'GUILD_ID': '123456789',
        'API_TOKEN': 'test_api_token',
        'DB_URL': 'https://api.example.com'
    }):
        return BotConfig()


def test_config_fixture(valid_config):
    """Test that the valid_config fixture works correctly."""
    assert valid_config.bot_token == 'test_bot_token'
    assert valid_config.guild_id == 123456789
    assert valid_config.api_token == 'test_api_token'
    assert valid_config.db_url == 'https://api.example.com'