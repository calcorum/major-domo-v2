"""
Configuration management for Discord Bot v2.0
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

# Baseball position constants (static, not configurable)
PITCHER_POSITIONS = {"SP", "RP", "P"}
POSITION_FIELDERS = {"C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "OF", "DH"}
ALL_POSITIONS = PITCHER_POSITIONS | POSITION_FIELDERS


class BotConfig(BaseSettings):
    """Application configuration with environment variable support."""

    # Discord settings
    bot_token: str
    guild_id: int

    # Database API settings
    api_token: str
    db_url: str

    # Discord Limits
    discord_embed_limit: int = 6000
    discord_field_value_limit: int = 1024
    discord_embed_description_limit: int = 4096

    # League settings
    sba_season: int = 12
    pd_season: int = 9
    fa_lock_week: int = 14
    sba_color: str = "a6ce39"
    weeks_per_season: int = 18
    games_per_week: int = 4
    modern_stats_start_season: int = 8
    offseason_flag: bool = False  # When True, relaxes roster limits and disables weekly freeze/thaw

    # Current Season Constants
    sba_current_season: int = 12
    pd_current_season: int = 9

    # API Constants
    api_version: str = "v3"
    default_timeout: int = 10
    max_retries: int = 3

    # Draft Constants
    default_pick_minutes: int = 10
    draft_rounds: int = 32
    draft_team_count: int = 16                  # Number of teams in draft
    draft_linear_rounds: int = 10              # Rounds 1-10 are linear, 11+ are snake
    swar_cap_limit: float = 32.00              # Maximum sWAR cap for team roster
    cap_player_count: int = 26                 # Number of players that count toward cap

    # Special Team IDs
    free_agent_team_id: int = 498

    # Role Names
    help_editor_role_name: str = "Help Editor"
    sba_players_role_name: str = "Season 12 Players"

    # Channel Names
    sba_network_news_channel: str = "sba-network-news"

    # Base URLs
    sba_base_url: str = "https://sba.manticorum.com"
    sba_logo_url: str = f'{sba_base_url}/images/sba-logo.png'

    # Application settings
    log_level: str = "INFO"
    environment: str = "development"
    testing: bool = True

    # Google Sheets settings
    sheets_credentials_path: str = "/app/data/major-domo-service-creds.json"

    # Giphy API settings
    giphy_api_key: str = "H86xibttEuUcslgmMM6uu74IgLEZ7UOD"
    giphy_translate_url: str = "https://api.giphy.com/v1/gifs/translate"

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

    @property
    def draft_total_picks(self) -> int:
        """Calculate total picks in draft (derived value)."""
        return self.draft_rounds * self.draft_team_count


# Global configuration instance - lazily initialized to avoid import-time errors
_config = None

def get_config() -> BotConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = BotConfig()  # type: ignore
    return _config