"""
Application constants for Discord Bot v2.0
"""

# Discord Limits
DISCORD_EMBED_LIMIT = 6000
DISCORD_FIELD_VALUE_LIMIT = 1024
DISCORD_EMBED_DESCRIPTION_LIMIT = 4096

# League Constants
WEEKS_PER_SEASON = 18
GAMES_PER_WEEK = 4
MODERN_STATS_START_SEASON = 8

# Current Season Constants
SBA_CURRENT_SEASON = 12
PD_CURRENT_SEASON = 9

# API Constants
API_VERSION = "v3"
DEFAULT_TIMEOUT = 10
MAX_RETRIES = 3

# Baseball Positions
PITCHER_POSITIONS = {"SP", "RP", "P"}
POSITION_FIELDERS = {"C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "OF", "DH"}
ALL_POSITIONS = PITCHER_POSITIONS | POSITION_FIELDERS

# Draft Constants
DEFAULT_PICK_MINUTES = 10
DRAFT_ROUNDS = 25

# Special Team IDs
FREE_AGENT_TEAM_ID = 31  # Generic free agent team ID (same per season)

# Role Names
HELP_EDITOR_ROLE_NAME = "Help Editor"  # Users with this role can edit help commands
SBA_PLAYERS_ROLE_NAME = "Season 12 Players"  # Current season players

# Channel Names
SBA_NETWORK_NEWS_CHANNEL = "sba-network-news"  # Channel for game results

# Base URLs
SBA_BASE_URL = "https://sba.major-domo.app"  # Base URL for web links

# Note: Google Sheets credentials path is now managed via config.py
# Access it with: get_config().sheets_credentials_path