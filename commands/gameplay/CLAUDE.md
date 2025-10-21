# Gameplay Commands

This directory contains Discord slash commands for live game tracking and scorecard management during gameplay.

## Files

### `scorebug.py`
- **Commands**:
  - `/publish-scorecard <url>` - Link a Google Sheets scorecard to a channel for live tracking
  - `/scorebug [full_length]` - Display the current scorebug from the published scorecard
- **Description**: Main command implementation for scorebug display and management
- **Service Dependencies**:
  - `ScorebugService` - Reading live game data from Google Sheets
  - `team_service.get_team()` - Team information lookup
- **Tracker Dependencies**:
  - `ScorecardTracker` - JSON-based persistent storage of scorecard-channel mappings

### `scorecard_tracker.py`
- **Class**: `ScorecardTracker`
- **Description**: JSON-based persistent tracking of published scorecards
- **Features**:
  - Maps Discord text channels to Google Sheets URLs
  - Persistent storage across bot restarts
  - Automatic stale entry cleanup
  - Timestamp tracking for monitoring

### `__init__.py`
- **Function**: `setup_gameplay(bot)`
- **Description**: Package initialization with resilient cog loading
- **Integration**: Follows established bot architecture patterns

## Background Integration

### Live Scorebug Tracker Task
**File**: `tasks/live_scorebug_tracker.py`

**Schedule**: Every 3 minutes

**Operations**:
1. **Update `#live-sba-scores` Channel**
   - Reads all published scorecards from tracker
   - Generates compact scorebug embeds for active games
   - Clears old messages and posts fresh scorebugs
   - Filters out final games (only shows active/in-progress)

2. **Update Voice Channel Descriptions**
   - For each active scorecard, checks for associated voice channel
   - Updates voice channel topic with live score: `"BOS 4 @ 3 NYY"`
   - Adds "FINAL" suffix when game completes: `"BOS 5 @ 3 NYY - FINAL"`
   - Gracefully handles missing or deleted voice channels

## Key Features

### `/publish-scorecard <url>`
**URL/Key Support**:
- Full URL: `https://docs.google.com/spreadsheets/d/[KEY]/edit...`
- Just the key: `[SHEET_KEY]`

**Validation**:
- Checks scorecard accessibility (public read permissions)
- Verifies scorecard has required 'Scorebug' tab
- Tests data reading to ensure valid scorecard structure

**Storage**:
- Saves mapping in `data/scorecards.json`
- Persists across bot restarts
- Associates scorecard with text channel ID

**User Feedback**:
- Confirmation message with sheet title
- Usage instructions for `/scorebug` command
- Clear error messages for access issues

### `/scorebug [full_length]`
**Display Modes**:
- `full_length=True` (default): Complete scorebug with runners, matchups, and summary
- `full_length=False`: Compact view with just score and status

**Data Display**:
- Game header and inning information
- Score formatted in table
- Current game status (inning/half)
- Runners on base with positions
- Current matchups (optional)
- Game summary (optional)
- Team colors and thumbnails

**Error Handling**:
- Clear message if no scorecard published in channel
- Helpful errors for access or read failures
- Graceful handling of missing team data

### Live Score Updates (Background Task)
**Channel Updates**:
- Clears `#live-sba-scores` channel before each update
- Posts up to 10 scorebugs per message (Discord limit)
- Splits into multiple messages if needed
- Shows only active games (filters out finals)

**Voice Channel Integration**:
- Looks up voice channel associated with scorecard's text channel
- Updates voice channel `topic` with formatted score
- Format: `"{AWAY_ABBREV} {AWAY_SCORE} @ {HOME_SCORE} {HOME_ABBREV}"`
- Adds "- FINAL" when game completes
- Rate limits to avoid Discord API issues

## Architecture

### Service Layer Integration
**ScorebugService** (`services/scorebug_service.py`):
- Extends `SheetsService` for Google Sheets access
- Returns `ScorebugData` objects with parsed game information
- Supports both URL and key-based scorecard access
- Reads from 'Scorebug' tab (B2:S20) for game state
- Reads team IDs from 'Setup' tab (B5:B6)

**ScorebugData Fields**:
```python
{
    'away_team_id': int,
    'home_team_id': int,
    'header': str,           # Game header with inning info
    'away_score': int,
    'home_score': int,
    'which_half': str,       # Top/Bottom inning indicator
    'is_final': bool,
    'runners': list,         # Runner info [position, name] pairs
    'matchups': list,        # Current batter/pitcher matchups
    'summary': list          # Game summary data
}
```

### Tracker Integration
**ScorecardTracker** stores:
```json
{
  "scorecards": {
    "123456789": {
      "text_channel_id": "123456789",
      "sheet_url": "https://docs.google.com/...",
      "published_at": "2025-01-15T10:30:00",
      "last_updated": "2025-01-15T10:35:00",
      "publisher_id": "111222333"
    }
  }
}
```

**Voice Channel Association**:
- Voice tracker updated to store `text_channel_id` when voice channels created
- New method: `get_voice_channel_for_text_channel(text_channel_id)`
- Enables background task to update voice channel descriptions

### Command Flow
**Publishing Flow**:
1. User runs `/publish-scorecard <url>`
2. Bot validates access to Google Sheet
3. Bot verifies Scorebug tab exists
4. Bot reads sample data to ensure valid structure
5. Tracker stores text_channel_id → sheet_url mapping
6. User receives confirmation message

**Display Flow**:
1. User runs `/scorebug` in channel
2. Bot looks up scorecard URL from tracker
3. Bot reads current scorebug data from sheet
4. Bot fetches team information from API
5. Bot creates rich embed with game state
6. Bot updates tracker timestamp

**Background Update Flow**:
1. Task runs every 3 minutes
2. Reads all published scorecards from tracker
3. For each scorecard:
   - Reads current scorebug data
   - Checks if game is active (not final)
   - Creates compact embed for live channel
   - Checks for associated voice channel
   - Updates voice channel description if found
4. Posts all active scorebugs to `#live-sba-scores`
5. Clears channel if no active games

## Configuration

### Channel Requirements
- **`#live-sba-scores`** - Live scorebug display channel (auto-updated every 3 minutes)

### Data Storage
- **`data/scorecards.json`** - Published scorecard mappings
- **`data/voice_channels.json`** - Voice channel tracking (includes text_channel_id)

### Google Sheets Requirements
Scorecards must have:
- **Scorebug tab**: Live game data (B2:S20)
- **Setup tab**: Team IDs (B5:B6)
- **Public read access**: "Anyone with the link can view"

## Error Handling

### Common Scenarios
- **Sheet not accessible**: Clear message about public permissions
- **Missing Scorebug tab**: Error indicating invalid scorecard structure
- **No scorecard published**: Helpful message to use `/publish-scorecard`
- **Sheet read failures**: Graceful degradation with retry suggestions
- **Voice channel deleted**: Silent skip (no errors to users)
- **Missing permissions**: Clear permission error messages

### Service Dependencies
- **Graceful degradation**: Commands work without background task
- **Rate limiting**: 1-second delay between scorecard reads
- **API failures**: Comprehensive error handling for external service calls
- **Discord errors**: Specific handling for Forbidden, NotFound, etc.

## Voice Channel Enhancement

### Text Channel Association
When voice channels are created via `/voice-channel`:
- Text channel ID stored in voice channel tracking data
- Enables scorebug → voice channel lookup
- Persistent across bot restarts

### Description Update Format
**Active Game**:
```
BOS 4 @ 3 NYY
```

**Final Game**:
```
BOS 5 @ 3 NYY - FINAL
```

**Implementation**:
- Uses voice channel `topic` field (description)
- Updates every 3 minutes with live scores
- Automatic cleanup when game ends
- No manual user interaction required

## Integration Points

### Bot Integration
- **Package Loading**: Integrated into `bot.py` command package loading sequence
- **Background Tasks**: Live scorebug tracker started in `_setup_background_tasks()`
- **Shutdown Handling**: Tracker stopped in `bot.close()`

### Service Layer
- **ScorebugService**: Google Sheets data extraction
- **TeamService**: Team information and logo lookups
- **ScorecardTracker**: Persistent scorecard-channel mapping

### Discord Integration
- **Application Commands**: Modern slash command interface
- **Embed Templates**: Consistent styling using `EmbedTemplate`
- **Error Handling**: Integration with global application command error handler
- **Voice Channels**: Bi-directional integration with voice channel system

## Usage Examples

### Publishing a Scorecard
```
/publish-scorecard https://docs.google.com/spreadsheets/d/ABC123/edit
```
**Result**: Scorecard linked to current channel for live tracking

### Using Just Sheet Key
```
/publish-scorecard ABC123DEF456
```
**Result**: Same functionality with cleaner input

### Displaying Scorebug
```
/scorebug
```
**Result**: Full scorebug display with all details

### Compact Scorebug
```
/scorebug full_length:False
```
**Result**: Just score and status, no runners/matchups/summary

## Monitoring and Logs

### Structured Logging
```python
self.logger.info(f"Published scorecard to channel {text_channel_id}: {sheet_url}")
self.logger.debug(f"Updated voice channel {voice_channel.name} description to: {description}")
self.logger.warning(f"Could not read scorecard {sheet_url}: {e}")
```

### Performance Tracking
- Background task execution timing
- Google Sheets read latency
- Voice channel update success rates
- Scorecard access failure rates

## Future Enhancements

### Potential Features
- **Scorecard rotation**: Multiple scorecard support per channel
- **Custom refresh intervals**: User-configurable update frequency
- **Notification system**: Alerts for game events (runs, innings, etc.)
- **Statistics tracking**: Historical scorebug access patterns
- **Mobile optimization**: Compact embeds for mobile viewing

### Configuration Options
- **Per-channel settings**: Different update intervals per channel
- **Role permissions**: Restrict scorecard publishing to specific roles
- **Format customization**: User-selectable scorebug styles
- **Alert thresholds**: Configurable notification triggers

---

**Last Updated**: January 2025
**Architecture**: Modern async Discord.py with Google Sheets integration
**Dependencies**: discord.py, pygsheets, ScorebugService, ScorecardTracker, VoiceChannelTracker
