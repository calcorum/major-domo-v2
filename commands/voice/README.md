# Voice Channel Commands

This directory contains Discord slash commands for creating and managing voice channels for gameplay.

## Files

### `channels.py`
- **Commands**:
  - `/voice-channel public` - Create a public voice channel for gameplay
  - `/voice-channel private` - Create a private team vs team voice channel
- **Description**: Main command implementation with VoiceChannelCommands cog
- **Service Dependencies**:
  - `team_service.get_teams_by_owner()` - Verify user has a team
  - `league_service.get_current_state()` - Get current season/week info
  - `schedule_service.get_team_schedule()` - Find opponent for private channels
- **Deprecated Commands**:
  - `!vc`, `!voice`, `!gameplay` → Shows migration message to `/voice-channel public`
  - `!private` → Shows migration message to `/voice-channel private`

### `cleanup_service.py`
- **Class**: `VoiceChannelCleanupService`
- **Description**: Manages automatic cleanup of bot-created voice channels
- **Features**:
  - Restart-resilient channel tracking using JSON persistence
  - Configurable cleanup intervals and empty thresholds
  - Background monitoring loop with error recovery
  - Startup verification to clean stale tracking entries

### `tracker.py`
- **Class**: `VoiceChannelTracker`
- **Description**: JSON-based persistent tracking of voice channels
- **Features**:
  - Channel creation and status tracking
  - Empty duration monitoring with datetime handling
  - Cleanup candidate identification
  - Automatic stale entry removal

### `__init__.py`
- **Function**: `setup_voice(bot)`
- **Description**: Package initialization with resilient cog loading
- **Integration**: Follows established bot architecture patterns

## Key Features

### Public Voice Channels (`/voice-channel public`)
- **Permissions**: Everyone can connect and speak
- **Naming**: Random codename generation (e.g., "Gameplay Phoenix", "Gameplay Thunder")
- **Requirements**: User must own a Major League team (3-character abbreviations like NYY, BOS)
- **Auto-cleanup**: Configurable threshold (default: empty for configured minutes)

### Private Voice Channels (`/voice-channel private`)
- **Permissions**:
  - Team members can connect and speak (using `team.lname` Discord roles)
  - Everyone else can connect but only listen
- **Naming**: Automatic "{Away} vs {Home}" format based on current week's schedule
- **Opponent Detection**: Uses current league week to find scheduled opponent
- **Requirements**:
  - User must own a Major League team (3-character abbreviations like NYY, BOS)
  - Team must have upcoming games in current week
- **Role Integration**: Finds Discord roles matching team full names (`team.lname`)

### Automatic Cleanup System
- **Monitoring Interval**: Configurable (default: 60 seconds)
- **Empty Threshold**: Configurable (default: 5 minutes empty before deletion)
- **Restart Resilience**: JSON file persistence survives bot restarts
- **Startup Verification**: Validates tracked channels still exist on bot startup
- **Graceful Error Handling**: Continues operation even if individual operations fail

## Architecture

### Command Flow
1. **Major League Team Verification**: Check user owns a Major League team using `team_service`
2. **Channel Creation**: Create voice channel with appropriate permissions
3. **Tracking Registration**: Add channel to cleanup service tracking
4. **User Feedback**: Send success embed with channel details

### Team Validation Logic
The voice channel system validates that users own **Major League teams** specifically:

```python
async def _get_user_major_league_team(self, user_id: int, season: Optional[int] = None):
    """Get the user's Major League team for schedule/game purposes."""
    teams = await team_service.get_teams_by_owner(user_id, season)

    # Filter to only Major League teams (3-character abbreviations)
    major_league_teams = [team for team in teams if team.roster_type() == RosterType.MAJOR_LEAGUE]

    return major_league_teams[0] if major_league_teams else None
```

**Team Types:**
- **Major League**: 3-character abbreviations (e.g., NYY, BOS, LAD) - **Required for voice channels**
- **Minor League**: 4+ characters ending in "MIL" (e.g., NYYMIL, BOSMIL) - **Not eligible**
- **Injured List**: Ending in "IL" (e.g., NYYIL, BOSIL) - **Not eligible**

**Rationale:** Only Major League teams participate in weekly scheduled games, so voice channel creation is restricted to active Major League team owners.

### Permission System
```python
# Public channels - everyone can speak
overwrites = {
    guild.default_role: discord.PermissionOverwrite(speak=True, connect=True)
}

# Private channels - team roles only can speak
overwrites = {
    guild.default_role: discord.PermissionOverwrite(speak=False, connect=True),
    user_team_role: discord.PermissionOverwrite(speak=True, connect=True),
    opponent_team_role: discord.PermissionOverwrite(speak=True, connect=True)
}
```

### Cleanup Service Integration
```python
# Bot initialization (bot.py)
from commands.voice.cleanup_service import VoiceChannelCleanupService
self.voice_cleanup_service = VoiceChannelCleanupService()
asyncio.create_task(self.voice_cleanup_service.start_monitoring(self))

# Channel tracking
if hasattr(self.bot, 'voice_cleanup_service'):
    cleanup_service = self.bot.voice_cleanup_service
    cleanup_service.tracker.add_channel(channel, channel_type, interaction.user.id)
```

### JSON Data Structure
```json
{
  "voice_channels": {
    "123456789": {
      "channel_id": "123456789",
      "guild_id": "987654321",
      "name": "Gameplay Phoenix",
      "type": "public",
      "created_at": "2025-01-15T10:30:00",
      "last_checked": "2025-01-15T10:35:00",
      "empty_since": "2025-01-15T10:32:00",
      "creator_id": "111222333"
    }
  }
}
```

## Configuration

### Cleanup Service Settings
- **`cleanup_interval`**: How often to check channels (default: 60 seconds)
- **`empty_threshold`**: Minutes empty before deletion (default: 5 minutes)
- **`data_file`**: JSON persistence file path (default: "storage/voice_channels.json")

### Channel Categories
- Channels are created in the "Voice Channels" category if it exists
- Falls back to no category if "Voice Channels" category not found

### Random Codenames
```python
CODENAMES = [
    "Phoenix", "Thunder", "Lightning", "Storm", "Blaze", "Frost", "Shadow", "Nova",
    "Viper", "Falcon", "Wolf", "Eagle", "Tiger", "Shark", "Bear", "Dragon",
    "Alpha", "Beta", "Gamma", "Delta", "Echo", "Foxtrot", "Golf", "Hotel",
    "Crimson", "Azure", "Emerald", "Golden", "Silver", "Bronze", "Platinum", "Diamond"
]
```

## Error Handling

### Common Scenarios
- **No Team Found**: User-friendly message directing to contact league administrator
- **No Upcoming Games**: Informative message about being between series
- **Missing Discord Roles**: Warning in embed about teams without speaking permissions
- **Permission Errors**: Clear message to contact server administrator
- **League Info Unavailable**: Graceful fallback with retry suggestion

### Service Dependencies
- **Graceful Degradation**: Voice channels work without cleanup service
- **API Failures**: Comprehensive error handling for external service calls
- **Discord Errors**: Specific handling for Forbidden, NotFound, etc.

## Testing Coverage

### Test Files
- **`tests/test_commands_voice.py`**: Comprehensive test suite covering:
  - VoiceChannelTracker JSON persistence and datetime handling
  - VoiceChannelCleanupService restart resilience and monitoring
  - VoiceChannelCommands slash command functionality
  - Error scenarios and edge cases
  - Deprecated command migration messages

### Mock Objects
- Discord guild, channels, roles, and interactions
- Team service responses and player data
- Schedule service responses and game data
- League service current state information

## Integration Points

### Bot Integration
- **Package Loading**: Integrated into `bot.py` command package loading sequence
- **Background Tasks**: Cleanup service started in `_setup_background_tasks()`
- **Shutdown Handling**: Cleanup service stopped in `bot.close()`

### Service Layer
- **Team Service**: User team verification and ownership lookup
- **League Service**: Current season/week information retrieval
- **Schedule Service**: Team schedule and opponent detection

### Discord Integration
- **Application Commands**: Modern slash command interface with command groups
- **Permission Overwrites**: Fine-grained voice channel permission control
- **Embed Templates**: Consistent styling using established embed patterns
- **Error Handling**: Integration with global application command error handler

## Usage Examples

### Creating Public Channel
```
/voice-channel public
```
**Result**: Creates "Gameplay [Codename]" with public speaking permissions

### Creating Private Channel
```
/voice-channel private
```
**Result**: Creates "[Away] vs [Home]" with team-only speaking permissions

### Migration from Old Commands
```
!vc
```
**Result**: Shows deprecation message suggesting `/voice-channel public`

## Future Enhancements

### Potential Features
- **Channel Limits**: Per-user or per-team channel creation limits
- **Custom Names**: Allow users to specify custom channel names
- **Extended Permissions**: More granular permission control options
- **Channel Templates**: Predefined setups for different game types
- **Integration Webhooks**: Notifications when channels are created/deleted

### Configuration Options
- **Environment Variables**: Make cleanup intervals configurable via env vars
- **Per-Guild Settings**: Different settings for different Discord servers
- **Role Mapping**: Custom role name patterns for team permissions

---

**Last Updated**: January 2025
**Architecture**: Modern async Discord.py with JSON persistence
**Dependencies**: discord.py, team_service, league_service, schedule_service