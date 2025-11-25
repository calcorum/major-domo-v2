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

### `branding.py`
- **Command**: `/branding`
- **Description**: Update team colors and logos via interactive modal
- **Access**: Team owners only (verified via `team_service.get_team_by_owner()`)
- **Service Dependencies**:
  - `team_service.get_team_by_owner()`
  - `team_service.update_team()`
  - `models.team.Team.minor_league_affiliate()`

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

### Team Branding Management (`branding.py`)
- **Modal-Based Input**: Interactive form with 5 optional fields
- **Preview + Confirmation**: Visual preview before applying changes
- **Multi-Team Support**: Updates major league and minor league teams
- **Discord Integration**: Attempts to update Discord role colors (non-blocking)

#### Workflow
1. User runs `/branding`
2. Bot verifies user owns a team
3. Modal displays with 5 optional fields showing current values
4. User fills in desired changes, submits
5. Bot validates all inputs (hex colors, URL accessibility)
6. Bot shows preview embeds with confirmation buttons
7. User confirms or cancels
8. Bot applies changes to database
9. Bot attempts to update Discord role color (non-blocking)
10. Bot shows success message with details

#### Modal Fields
- **Major League Team Color** - 6-character hex code (e.g., FF5733 or #FF5733)
- **Major League Logo URL** - Public image URL (.png, .jpg, .jpeg, .gif, .webp)
- **Minor League Team Color** - 6-character hex code
- **Minor League Logo URL** - Public image URL
- **Dice Roll Color** - 6-character hex code for dice displays

#### Validation Rules
- **Hex Colors**: Must be exactly 6 characters, valid hex digits (0-9, A-F), # prefix optional
- **Image URLs**: Must start with http:// or https://, end with valid extension, be publicly accessible
- **All Fields Optional**: Leave blank to keep current value
- **URL Accessibility**: Tests URLs with HEAD request (5 second timeout)
- **Content Type Check**: Verifies URLs point to images

#### Database Updates
- Major league team: `color`, `thumbnail`, `dice_color` fields
- Minor league team: `color`, `thumbnail` fields
- Uses `team_service.update_team()` for all database operations

#### Discord Role Updates
- Bot attempts to update Discord role color to match team color
- Failures are non-blocking (show warning but database updates succeed)
- Common failure reasons: role not found, missing permissions
- Updates role by matching `team.lname` (long name)

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

5. **Branding command issues**:
   - **"You don't own a team"**: User is not registered as team owner for current season
   - **"URL not accessible"**: Image URL returned non-200 status or timed out (check URL is public)
   - **"Color must be 6 characters"**: Hex color is wrong length or contains invalid characters
   - **"Discord role update failed"**: Role color couldn't be updated (database still succeeded - not critical)
   - **"No minor league affiliate"**: Team doesn't have MiL team (this is normal for some teams)

### Dependencies
- `services.team_service`
- `models.team.Team`
- `utils.decorators.logged_command`
- `views.embeds.EmbedTemplate`
- `constants.SBA_CURRENT_SEASON`
- `exceptions.BotException`

### Testing
Run tests with:
- All team commands: `python -m pytest tests/test_commands_teams.py -v`
- Branding command only: `python -m pytest tests/test_commands_teams_branding.py -v`

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