# Transaction Commands

This directory contains Discord slash commands for transaction management and roster legality checking.

## Files

### `management.py`
- **Commands**:
  - `/mymoves` - View user's pending and scheduled transactions
  - `/legal` - Check roster legality for current and next week
- **Service Dependencies**:
  - `transaction_service` (multiple methods for transaction retrieval)
  - `roster_service` (roster validation and retrieval)
  - `team_service.get_teams_by_owner()` and `get_team_by_abbrev()`

## Key Features

### Transaction Status Display (`/mymoves`)
- **User Team Detection**: Automatically finds user's team by Discord ID
- **Transaction Categories**:
  - **Pending**: Transactions awaiting processing
  - **Frozen**: Scheduled transactions ready for processing
  - **Processed**: Recently completed transactions
  - **Cancelled**: Optional display of cancelled transactions
- **Status Visualization**:
  - Status emojis for each transaction type
  - Week numbering and move descriptions
  - Transaction count summaries
- **Smart Limiting**: Shows recent transactions (last 5 pending, 3 frozen/processed, 2 cancelled)

### Roster Legality Checking (`/legal`)
- **Dual Roster Validation**: Checks both current and next week rosters
- **Flexible Team Selection**:
  - Auto-detects user's team
  - Allows manual team specification via abbreviation
- **Comprehensive Validation**:
  - Player count verification (active roster + IL)
  - sWAR calculations and limits
  - League rule compliance checking
  - Error and warning categorization
- **Parallel Processing**: Roster retrieval and validation run concurrently

### Advanced Transaction Features
- **Concurrent Data Fetching**: Multiple transaction types retrieved in parallel
- **Owner-Based Filtering**: Transactions filtered by team ownership
- **Status Tracking**: Real-time transaction status with emoji indicators
- **Team Integration**: Team logos and colors in transaction displays

## Architecture Notes

### Permission Model
- **Team Ownership**: Commands use Discord user ID to determine team ownership
- **Cross-Team Viewing**: `/legal` allows checking other teams' roster status
- **Access Control**: Users can only view their own transactions via `/mymoves`

### Data Processing
- **Async Operations**: Heavy use of `asyncio.gather()` for performance
- **Error Resilience**: Graceful handling of missing roster data
- **Validation Pipeline**: Multi-step roster validation with detailed feedback

### Embed Structure
- **Status-Based Coloring**: Success (green) vs Error (red) color coding
- **Information Hierarchy**: Important information prioritized in embed layout
- **Team Branding**: Consistent use of team thumbnails and colors

## Troubleshooting

### Common Issues

1. **User team not found**:
   - Verify user has team ownership record in database
   - Check Discord user ID mapping to team ownership
   - Ensure current season team assignments are correct

2. **Transaction data missing**:
   - Verify `transaction_service` API endpoints are functional
   - Check transaction status filtering logic
   - Ensure transaction records exist for the team/season

3. **Roster validation failing**:
   - Check `roster_service.get_current_roster()` and `get_next_roster()` responses
   - Verify roster validation rules and logic
   - Ensure player data integrity in roster records

4. **Legal command errors**:
   - Verify team abbreviation exists in database
   - Check roster data availability for both current and next weeks
   - Ensure validation service handles edge cases properly

### Service Dependencies
- `services.transaction_service`:
  - `get_pending_transactions()`
  - `get_frozen_transactions()`
  - `get_processed_transactions()`
  - `get_team_transactions()`
- `services.roster_service`:
  - `get_current_roster()`
  - `get_next_roster()`
  - `validate_roster()`
- `services.team_service`:
  - `get_teams_by_owner()`
  - `get_team_by_abbrev()`

### Core Dependencies
- `utils.decorators.logged_command`
- `views.embeds.EmbedTemplate`
- `constants.SBA_CURRENT_SEASON`

### Testing
Run tests with: `python -m pytest tests/test_commands_transactions.py -v`

## Database Requirements
- Team ownership mapping (Discord user ID to team)
- Transaction records with status tracking
- Roster data for current and next weeks
- Player assignments and position information
- League rules and validation criteria

## Future Enhancements
- Transaction submission and modification commands
- Advanced transaction analytics and history
- Roster optimization suggestions
- Transaction approval workflow integration
- Automated roster validation alerts

## Security Considerations
- User authentication via Discord IDs
- Team ownership verification for sensitive operations
- Transaction privacy (users can only see their own transactions)
- Input validation for team abbreviations and parameters