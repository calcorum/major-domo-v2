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
- **Basic Info**: Name, position(s), team, season, sWAR, injury status
- **Injury Indicator**: 🤕 emoji in title if player has active injury
- **Injury Information**:
  - Injury Rating (always displayed)
  - Injury Return date (displayed only when injured, format: w##g#)
- **Statistics Integration**:
  - **Batting stats** displayed in two inline fields with rounded box code blocks:
    - **Rate Stats**: AVG, OBP, SLG, OPS, wOBA
    - **Counting Stats**: HR, RBI, R, AB, H, BB, SO
  - **Pitching stats** displayed in two inline fields with rounded box code blocks:
    - **Record Stats**: G-GS, W-L, H-SV, ERA, WHIP, IP
    - **Counting Stats**: SO, BB, H
  - Two-way player detection and display
- **Visual Elements**:
  - Player name as embed title (with 🤕 emoji if injured)
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

## Stat Display Format (January 2025)

### Batting Stats
Stats are displayed in two side-by-side inline fields using rounded box code blocks:

**Rate Stats (Left):**
```
╭─────────────╮
│ AVG  .305  │
│ OBP  .385  │
│ SLG  .545  │
│ OPS  .830  │
│ wOBA .355  │
╰─────────────╯
```

**Counting Stats (Right):**
```
╭───────────╮
│  HR  25  │
│ RBI  80  │
│   R  95  │
│  AB 450  │
│   H 137  │
│  BB  55  │
│  SO  98  │
╰───────────╯
```

### Pitching Stats
Stats are displayed in two side-by-side inline fields using rounded box code blocks:

**Record Stats (Left):**
```
╭─────────────╮
│ G-GS 28-28  │
│  W-L 12-8   │
│ H-SV  3-0   │
│  ERA  3.45  │
│ WHIP  1.25  │
│   IP 165.1  │
╰─────────────╯
```

**Counting Stats (Right):**
```
╭────────╮
│ SO 185 │
│ BB  48 │
│  H 145 │
╰────────╯
```

**Design Features:**
- Compact, professional appearance using rounded box characters (`╭╮╰╯─│`)
- Right-aligned numeric values for clean alignment
- Inline fields allow side-by-side display
- Empty field separator above stats for visual spacing
- Consistent styling between batting and pitching displays

## Database Requirements
- Player records with name, positions, team associations
- Player injury data (injury_rating, il_return fields)
- Statistics tables for batting and pitching
- Image URLs for player cards, headshots, and fancy cards
- Team logo and color information