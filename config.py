"""
Configuration management for Discord Bot v2.0
"""
import os
from typing import Optional

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
    sba_season: int = 13
    pd_season: int = 10
    fa_lock_week: int = 14
    sba_color: str = "a6ce39"
    weeks_per_season: int = 18
    games_per_week: int = 4
    playoff_weeks_per_season: int = 3
    playoff_round_one_games: int = 5
    playoff_round_two_games: int = 7
    playoff_round_three_games: int = 7
    modern_stats_start_season: int = 8
    offseason_flag: bool = False  # When True, relaxes roster limits and disables weekly freeze/thaw

    # Roster Limits
    expand_mil_week: int = 15            # Week when MiL roster expands (early vs late limits)
    ml_roster_limit_early: int = 26      # ML limit for weeks before expand_mil_week
    ml_roster_limit_late: int = 26       # ML limit for weeks >= expand_mil_week
    mil_roster_limit_early: int = 6      # MiL limit for weeks before expand_mil_week
    mil_roster_limit_late: int = 14      # MiL limit for weeks >= expand_mil_week
    ml_roster_limit_offseason: int = 69  # ML limit during offseason
    mil_roster_limit_offseason: int = 69 # MiL limit during offseason


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
    free_agent_team_id: int = 547

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

    # Draft Sheet settings (for writing picks to Google Sheets)
    # Sheet IDs can be overridden via environment variables: DRAFT_SHEET_KEY_12, DRAFT_SHEET_KEY_13, etc.
    draft_sheet_enabled: bool = True  # Feature flag - set DRAFT_SHEET_ENABLED=false to disable
    draft_sheet_worksheet: str = "Ordered List"  # Worksheet name to write picks to
    draft_sheet_start_column: str = "D"  # Column where pick data starts (D, E, F, G for 4 columns)

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

    def get_draft_sheet_key(self, season: int) -> Optional[str]:
        """
        Get the Google Sheet ID for a given draft season.

        Sheet IDs are configured via environment variables:
        - DRAFT_SHEET_KEY_12 for season 12
        - DRAFT_SHEET_KEY_13 for season 13
        - etc.

        Returns None if no sheet is configured for the season.
        """
        # Default sheet IDs (hardcoded as fallback)
        default_keys = {
            12: "1OF-sAFykebc_2BrcYCgxCR-4rJo0GaNmTstagV-PMBU",
            13: "1vWJfvuz9jN5BU2ZR0X0oC9BAVr_R8o-dWZsF2KXQMsE"
        }

        # Check environment variable first (allows runtime override)
        env_key = os.getenv(f"DRAFT_SHEET_KEY_{season}")
        if env_key:
            return env_key

        # Fall back to hardcoded default
        return default_keys.get(season)

    def get_draft_sheet_url(self, season: int) -> Optional[str]:
        """
        Get the full Google Sheets URL for a given draft season.

        Returns None if no sheet is configured for the season.
        """
        sheet_key = self.get_draft_sheet_key(season)
        if sheet_key:
            return f"https://docs.google.com/spreadsheets/d/{sheet_key}"
        return None


# Global configuration instance - lazily initialized to avoid import-time errors
_config = None

def get_config() -> BotConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = BotConfig()  # type: ignore
    return _config