# Player Commands

This directory contains Discord slash commands for player information and statistics.

## Files

### `info.py`
- **Command**: `/player`
- **Description**: Display comprehensive player information and statistics
- **Parameters**:
  - `name` (required): Player name to search for
  - `season` (optional): Season for statistics (defaults to current season)
- **Service Dependencies**:
  - `player_service.get_players_by_name()`
  - `player_service.search_players_fuzzy()`
  - `player_service.get_player()`
  - `stats_service.get_player_stats()`

## Key Features

### Player Search
- **Exact Name Matching**: Primary search method using player name
- **Fuzzy Search Fallback**: If no exact match, suggests similar player names
- **Multiple Player Handling**: When multiple players match, attempts exact match or asks user to be more specific
- **Suggestion System**: Shows up to 10 suggested players with positions when no exact match found

### Player Information Display
- **Basic Info**: Name, position(s), team, season
- **Statistics Integration**:
  - Batting stats (AVG/OBP/SLG, OPS, wOBA, HR, RBI, runs, etc.)
  - Pitching stats (W-L record, ERA, WHIP, strikeouts, saves, etc.)
  - Two-way player detection and display
- **Visual Elements**:
  - Team logo as author icon
  - Player card image as main image
  - Thumbnail priority: fancy card → headshot → team logo
  - Team color theming for embed

### Advanced Features
- **Concurrent Data Fetching**: Player data and statistics retrieved in parallel for performance
- **sWAR Display**: Shows Strat-o-Matic WAR value
- **Multi-Position Support**: Displays all eligible positions
- **Rich Error Handling**: Graceful fallbacks when data is unavailable

## Architecture Notes

### Search Logic Flow
1. Search by exact name in specified season
2. If no results, try fuzzy search across all players
3. If single result, display player card
4. If multiple results, attempt exact name match
5. If still multiple, show disambiguation list

### Performance Optimizations
- `asyncio.gather()` for concurrent API calls
- Efficient player data and statistics retrieval
- Lazy loading of optional player images

### Error Handling
- No players found: Suggests fuzzy matches
- Multiple matches: Provides clarification options
- Missing data: Shows partial information with clear indicators
- API failures: Graceful degradation with fallback data

## Troubleshooting

### Common Issues

1. **Player not found**:
   - Check player name spelling
   - Verify player exists in the specified season
   - Use fuzzy search suggestions

2. **Statistics not loading**:
   - Verify `stats_service.get_player_stats()` API endpoint
   - Check if player has statistics for the requested season
   - Ensure season parameter is valid

3. **Images not displaying**:
   - Check player image URLs in database
   - Verify team thumbnail URLs
   - Ensure image hosting is accessible

4. **Performance issues**:
   - Monitor concurrent API call efficiency
   - Check database query performance
   - Verify embed size limits

### Dependencies
- `services.player_service`
- `services.stats_service`
- `utils.decorators.logged_command`
- `views.embeds.EmbedTemplate`
- `constants.SBA_CURRENT_SEASON`
- `exceptions.BotException`

### Testing
Run tests with: `python -m pytest tests/test_commands_players.py -v`

## Database Requirements
- Player records with name, positions, team associations
- Statistics tables for batting and pitching
- Image URLs for player cards, headshots, and fancy cards
- Team logo and color information