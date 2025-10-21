# Team Commands

This directory contains Discord slash commands for team information and roster management.

## Files

### `info.py`
- **Commands**:
  - `/team` - Display comprehensive team information
  - `/teams` - List all teams in a season
- **Parameters**:
  - `abbrev` (required for `/team`): Team abbreviation (e.g., NYY, BOS, LAD)
  - `season` (optional): Season to display (defaults to current season)
- **Service Dependencies**:
  - `team_service.get_team_by_abbrev()`
  - `team_service.get_teams_by_season()`
  - `team_service.get_team_standings_position()`

### `roster.py`
- **Command**: `/roster`
- **Description**: Display detailed team roster with position breakdowns
- **Parameters**:
  - `abbrev` (required): Team abbreviation
  - `roster_type` (optional): "current" or "next" week roster (defaults to current)
- **Service Dependencies**:
  - `team_service.get_team_by_abbrev()`
  - `team_service.get_team_roster()`

## Key Features

### Team Information Display (`info.py`)
- **Comprehensive Team Data**:
  - Team names (long name, short name, abbreviation)
  - Stadium information
  - Division assignment
  - Team colors and logos
- **Standings Integration**:
  - Win-loss record and winning percentage
  - Games behind division leader
  - Current standings position
- **Visual Elements**:
  - Team color theming for embeds
  - Team logo thumbnails
  - Consistent branding across displays

### Team Listing (`/teams`)
- **Season Overview**: All teams organized by division
- **Division Grouping**: Automatically groups teams by division ID
- **Fallback Display**: Shows simple list if division data unavailable
- **Team Count**: Total team summary

### Roster Management (`roster.py`)
- **Multi-Week Support**: Current and next week roster views
- **Position Breakdown**:
  - Batting positions (C, 1B, 2B, 3B, SS, LF, CF, RF, DH)
  - Pitching positions (SP, RP, CP)
  - Position player counts and totals
- **Advanced Features**:
  - Total sWAR calculation and display
  - Minor League (shortil) player tracking
  - Injured List (longil) player management
  - Detailed player lists with positions and WAR values

### Roster Display Structure
- **Summary Embed**: Position counts and totals
- **Detailed Player Lists**: Separate embeds for each roster type
- **Player Organization**: Batters and pitchers grouped separately
- **Chunked Display**: Long player lists split across multiple fields

## Architecture Notes

### Embed Design
- **Team Color Integration**: Uses team hex colors for embed theming
- **Fallback Colors**: Default colors when team colors unavailable
- **Thumbnail Priority**: Team logos displayed consistently
- **Multi-Embed Support**: Complex data split across multiple embeds

### Error Handling
- **Team Not Found**: Clear messaging with season context
- **Missing Roster Data**: Graceful handling of unavailable data
- **API Failures**: Fallback to partial information display

### Performance Considerations
- **Concurrent Data Fetching**: Standings and roster data retrieved in parallel
- **Efficient Roster Processing**: Position grouping and calculations optimized
- **Chunked Player Lists**: Prevents Discord embed size limits

## Troubleshooting

### Common Issues

1. **Team not found**:
   - Verify team abbreviation spelling
   - Check if team exists in the specified season
   - Ensure abbreviation matches database format

2. **Roster data missing**:
   - Verify `team_service.get_team_roster()` API endpoint
   - Check if roster data exists for the requested week type
   - Ensure team ID is correctly passed to roster service

3. **Position counts incorrect**:
   - Verify roster data structure and position field names
   - Check sWAR calculation logic
   - Ensure player position arrays are properly parsed

4. **Standings not displaying**:
   - Check `get_team_standings_position()` API response
   - Verify standings data structure matches expected format
   - Ensure error handling for malformed standings data

### Dependencies
- `services.team_service`
- `models.team.Team`
- `utils.decorators.logged_command`
- `views.embeds.EmbedTemplate`
- `constants.SBA_CURRENT_SEASON`
- `exceptions.BotException`

### Testing
Run tests with: `python -m pytest tests/test_commands_teams.py -v`

## Database Requirements
- Team records with abbreviations, names, colors, logos
- Division assignment and organization
- Roster data with position assignments and player details
- Standings calculations and team statistics
- Stadium and venue information

## Future Enhancements
- Team statistics and performance metrics
- Historical team data and comparisons
- Roster change tracking and transaction history
- Advanced roster analytics and projections