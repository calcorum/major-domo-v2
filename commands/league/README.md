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
- `utils.decorators.logged_command`
- `views.embeds.EmbedTemplate`
- `constants.SBA_CURRENT_SEASON`

### Testing
Run tests with: `python -m pytest tests/test_commands_league.py -v`