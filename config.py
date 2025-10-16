"""
Configuration management for Discord Bot v2.0
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotConfig(BaseSettings):
    """Application configuration with environment variable support."""
    
    # Discord settings
    bot_token: str
    guild_id: int
    
    # Database API settings
    api_token: str
    db_url: str
    
    # League settings
    sba_season: int = 12
    pd_season: int = 9
    fa_lock_week: int = 14
    sba_color: str = "a6ce39"
    
    # Application settings
    log_level: str = "INFO"
    environment: str = "development"
    testing: bool = False

    # Google Sheets settings
    sheets_credentials_path: str = "/data/major-domo-service-creds.json"

    # Optional Redis caching settings
    redis_url: str = ""  # Empty string means no Redis caching
    redis_cache_ttl: int = 300  # 5 minutes default TTL
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"  # Ignore extra environment variables
    )
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() == "development"
    
    @property
    def is_testing(self) -> bool:
        """Check if running in test mode."""
        return self.testing


# Global configuration instance - lazily initialized to avoid import-time errors
_config = None

def get_config() -> BotConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = BotConfig()  # type: ignore
    return _config