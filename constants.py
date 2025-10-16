"""
Application constants for Discord Bot v2.0

Most constants are now configurable via environment variables.
See config.py for default values and .env.example for configuration options.
"""
from config import get_config

# Load configuration
_config = get_config()

# Discord Limits (configurable)
DISCORD_EMBED_LIMIT = _config.discord_embed_limit
DISCORD_FIELD_VALUE_LIMIT = _config.discord_field_value_limit
DISCORD_EMBED_DESCRIPTION_LIMIT = _config.discord_embed_description_limit

# League Constants (configurable)
WEEKS_PER_SEASON = _config.weeks_per_season
GAMES_PER_WEEK = _config.games_per_week
MODERN_STATS_START_SEASON = _config.modern_stats_start_season

# Current Season Constants (configurable)
SBA_CURRENT_SEASON = _config.sba_current_season
PD_CURRENT_SEASON = _config.pd_current_season

# API Constants (configurable)
API_VERSION = _config.api_version
DEFAULT_TIMEOUT = _config.default_timeout
MAX_RETRIES = _config.max_retries

# Baseball Positions (static)
PITCHER_POSITIONS = {"SP", "RP", "P"}
POSITION_FIELDERS = {"C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "OF", "DH"}
ALL_POSITIONS = PITCHER_POSITIONS | POSITION_FIELDERS

# Draft Constants (configurable)
DEFAULT_PICK_MINUTES = _config.default_pick_minutes
DRAFT_ROUNDS = _config.draft_rounds

# Special Team IDs (configurable)
FREE_AGENT_TEAM_ID = _config.free_agent_team_id

# Role Names (configurable)
HELP_EDITOR_ROLE_NAME = _config.help_editor_role_name
SBA_PLAYERS_ROLE_NAME = _config.sba_players_role_name

# Channel Names (configurable)
SBA_NETWORK_NEWS_CHANNEL = _config.sba_network_news_channel

# Base URLs (configurable)
SBA_BASE_URL = _config.sba_base_url

# Note: Google Sheets credentials path is managed via config.py
# Access it with: get_config().sheets_credentials_path