# League Commands

This directory contains Discord slash commands related to league-wide information and statistics.

## Files

### `info.py`
- **Command**: `/league`
- **Description**: Display current league status and information
- **Functionality**: Shows current season/week, phase (regular season/playoffs/offseason), transaction status, trade deadlines, and league configuration
- **Service Dependencies**: `league_service.get_current_state()`
- **Key Features**:
  - Dynamic phase detection (offseason, playoffs, regular season)
  - Transaction freeze status
  - Trade deadline and playoff schedule information
  - Draft pick trading status

### `standings.py`
- **Commands**:
  - `/standings` - Display league standings by division
  - `/playoff-picture` - Show current playoff picture and wild card race
- **Parameters**:
  - `season`: Optional season number (defaults to current)
  - `division`: Optional division filter for standings
- **Service Dependencies**: `standings_service`
- **Key Features**:
  - Division-based standings display
  - Games behind calculations
  - Recent form statistics (home record, last 8 games, current streak)
  - Playoff cutoff visualization
  - Wild card race tracking

### `schedule.py`
- **Commands**:
  - `/schedule` - Display game schedules
  - `/results` - Show recent game results
- **Parameters**:
  - `season`: Optional season number (defaults to current)
  - `week`: Optional specific week filter
  - `team`: Optional team abbreviation filter
- **Service Dependencies**: `schedule_service`
- **Key Features**:
  - Weekly schedule views
  - Team-specific schedule filtering
  - Series grouping and summary
  - Recent/upcoming game overview
  - Game completion tracking

### `submit_scorecard.py`
- **Command**: `/submit-scorecard`
- **Description**: Submit Google Sheets scorecards with game results and play-by-play data
- **Parameters**:
  - `sheet_url`: Full URL to the Google Sheets scorecard
- **Required Role**: `Season 12 Players`
- **Service Dependencies**:
  - `SheetsService` - Google Sheets data extraction
  - `game_service` - Game CRUD operations
  - `play_service` - Play-by-play data management
  - `decision_service` - Pitching decision management
  - `standings_service` - Standings recalculation
  - `league_service` - Current state retrieval
  - `team_service` - Team lookup
  - `player_service` - Player lookup for results display
- **Key Features**:
  - **Scorecard Validation**: Checks sheet access and version compatibility
  - **Permission Control**: Only GMs of playing teams can submit
  - **Duplicate Detection**: Identifies already-played games with confirmation dialog
  - **Transaction Rollback**: Full rollback support at 3 states:
    - `PLAYS_POSTED`: Deletes plays on error
    - `GAME_PATCHED`: Wipes game and deletes plays on error
    - `COMPLETE`: All data committed successfully
  - **Data Extraction**: Reads 68 fields from Playtable, 14 fields from Pitcherstats, box score, and game metadata
  - **Results Display**: Rich embed with box score, pitching decisions, and top 3 key plays by WPA
  - **Automated Standings**: Triggers standings recalculation after successful submission
  - **News Channel Posting**: Automatically posts results to configured channel

**Workflow (14 Phases)**:
1. Validate scorecard access and version
2. Extract game metadata from Setup tab
3. Lookup teams and match managers
4. Check user permissions (must be GM of one team or bot owner)
5. Check for duplicate games (with confirmation if found)
6. Find scheduled game in database
7. Read play-by-play data (up to 297 plays)
8. Submit plays to database
9. Read box score
10. Update game with scores and managers
11. Read pitching decisions (up to 27 pitchers)
12. Submit decisions to database
13. Create and post results embed to news channel
14. Recalculate league standings

**Error Handling**:
- User-friendly error messages for common issues
- Graceful rollback on validation errors
- API error parsing for actionable feedback
- Non-critical errors (key plays, standings) don't fail submission

**Configuration**:
- `sheets_credentials_path` (in config.py): Path to Google service account credentials JSON (set via `SHEETS_CREDENTIALS_PATH` env var)
- `SBA_NETWORK_NEWS_CHANNEL`: Channel name for results posting
- `SBA_PLAYERS_ROLE_NAME`: Role required to submit scorecards

## Architecture Notes

### Decorator Usage
All commands use the `@logged_command` decorator pattern:
- Eliminates boilerplate logging code
- Provides consistent error handling
- Automatic request tracing and timing

### Error Handling
- Graceful fallbacks for missing data
- User-friendly error messages
- Ephemeral responses for errors

### Embed Structure
- Uses `EmbedTemplate` for consistent styling
- Color coding based on context (success/error/info)
- Rich formatting with team logos and thumbnails

## Troubleshooting

### Common Issues

1. **No league data available**: Check `league_service.get_current_state()` API endpoint
2. **Standings not loading**: Verify `standings_service.get_standings_by_division()` returns valid data
3. **Schedule commands failing**: Ensure `schedule_service` methods are properly handling season/week parameters

### Dependencies
- `services.league_service`
- `services.standings_service`
- `services.schedule_service`
- `services.sheets_service` (NEW) - Google Sheets integration
- `services.game_service` (NEW) - Game management
- `services.play_service` (NEW) - Play-by-play data
- `services.decision_service` (NEW) - Pitching decisions
- `services.team_service`
- `services.player_service`
- `utils.decorators.logged_command`
- `utils.discord_helpers` (NEW) - Channel and message utilities
- `utils.team_utils`
- `views.embeds.EmbedTemplate`
- `views.confirmations.ConfirmationView` (NEW) - Reusable confirmation dialog
- `constants.SBA_CURRENT_SEASON`
- `config.BotConfig.sheets_credentials_path` (NEW) - Google Sheets credentials path
- `constants.SBA_NETWORK_NEWS_CHANNEL` (NEW)
- `constants.SBA_PLAYERS_ROLE_NAME` (NEW)

### Testing
Run tests with: `python -m pytest tests/test_commands_league.py -v`