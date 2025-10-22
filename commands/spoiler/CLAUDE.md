# Spoiler Package Documentation
**Discord Bot v2.0 - Spoiler Detection System**

## Overview

The spoiler package monitors all messages for Discord spoiler tags (`||text||`) and pings the "Deez Watch" role when detected. This provides a fun, automated alert when users post spoilers in the server.

## Package Structure

```
commands/spoiler/
├── CLAUDE.md        # This documentation
├── __init__.py      # Package setup with resilient loading
└── listener.py      # Spoiler detection listener
```

## Components

### **SpoilerListener** (`listener.py`)

**Purpose:** Monitors all messages for Discord spoiler syntax and posts role ping alerts.

**Implementation:**
```python
class SpoilerListener(commands.Cog):
    """Listens for spoiler tags and responds with Deez Watch role ping."""

    @commands.Cog.listener(name='on_message')
    async def on_message_listener(self, message: discord.Message):
        # Uses shared message filters from utils.listeners
        if not should_process_message(message, *COMMAND_FILTERS):
            return

        # Detect Discord spoiler syntax (||)
        spoiler_count = message.content.count("||")
        if spoiler_count < 2:
            return

        # Find and ping the "Deez Watch" role
        deez_watch_role = discord.utils.get(message.guild.roles, name="Deez Watch")
        if deez_watch_role:
            await message.channel.send(f"{deez_watch_role.mention}!")
        else:
            # Fallback if role doesn't exist
            await message.channel.send("Deez Watch!")
```

## Discord Spoiler Syntax

Discord uses `||` markers to create spoiler tags:
- `||hidden text||` creates a single spoiler
- Multiple spoilers can exist in one message: `||spoiler 1|| some text ||spoiler 2||`
- The listener detects any message with 2+ instances of `||` (i.e., at least one complete spoiler tag)

## Message Filtering

Uses the shared `COMMAND_FILTERS` from `utils.listeners`, which includes:
- **Ignore bot messages** - Prevents bot loops
- **Ignore empty messages** - Messages with no content
- **Ignore command prefix** - Messages starting with '!' (legacy commands)
- **Ignore DMs** - Only process guild messages
- **Guild validation** - Only process messages from configured guild

See `utils/listeners.py` for filter implementation details.

## Logging

The listener logs:
- **Startup:** When the cog is initialized
- **Detection:** When a spoiler is detected (with user info and spoiler count)
- **Success:** When the alert is posted with role mention
- **Warning:** When the Deez Watch role is not found (falls back to text)
- **Errors:** Permission issues or send failures

**Example log output (with role):**
```
INFO - SpoilerListener cog initialized
INFO - Spoiler detected in message from Username (ID: 123456789) with 2 spoiler tag(s)
DEBUG - Spoiler alert posted with role mention
```

**Example log output (without role):**
```
INFO - Spoiler detected in message from Username (ID: 123456789) with 1 spoiler tag(s)
WARNING - Deez Watch role not found, posted without mention
```

## Error Handling

**Permission Errors:**
- Catches `discord.Forbidden` when bot lacks send permissions
- Logs error with channel ID for troubleshooting

**General Errors:**
- Catches all exceptions during message sending
- Logs with full stack trace for debugging
- Does not crash the bot or stop listening

## Requirements

**Discord Role:**
- A role named **"Deez Watch"** must exist in the guild
- Bot automatically looks up the role by name at runtime
- If role doesn't exist, bot falls back to posting "Deez Watch!" without mention

**Permissions:**
- Bot needs **Send Messages** permission in channels
- Bot needs **Mention Everyone** permission to ping roles (if role is not mentionable)
- Role can be set as mentionable to avoid needing special permissions

## Usage Examples

**Single Spoiler (with role):**
```
User: Hey did you know that ||Bruce Willis is dead the whole time||?
Bot: @Deez Watch!
```

**Multiple Spoilers:**
```
User: ||Darth Vader|| is ||Luke's father||
Bot: @Deez Watch!
```

**Fallback (no role):**
```
User: Hey did you know that ||Bruce Willis is dead the whole time||?
Bot: Deez Watch!
```

**Edge Cases:**
- Single `||` marker - **Not detected** (incomplete spoiler)
- Text with `||` in code blocks - **Detected** (Discord doesn't parse spoilers in code blocks)
- Empty spoilers `||||` - **Detected** (valid Discord syntax)

## Testing

**Setup:**
1. Create a role named "Deez Watch" in your Discord server (recommended)
2. Set the role as mentionable OR ensure bot has "Mention Everyone" permission

**Manual Testing:**
1. Start the bot in development mode
2. Post a message with `||test||` in the configured guild
3. Verify bot responds with @Deez Watch! (role mention)

**Test Cases:**
- ✅ Single spoiler tag with role mention
- ✅ Multiple spoiler tags
- ✅ Fallback to text if role doesn't exist
- ✅ Bot ignores own messages
- ✅ Bot ignores DMs
- ✅ Bot ignores messages from other guilds
- ✅ Bot ignores command messages (starting with '!')

## Performance Considerations

**Impact:**
- Listener processes every non-filtered message in the guild
- String counting (`message.content.count("||")`) is O(n) but fast for typical message lengths
- Only sends one message per detection (no loops)

**Optimization:**
- Early returns via message filters reduce processing
- Simple string operation (no regex needed)
- Async operations prevent blocking

## Future Enhancements

Potential improvements for the spoiler system:

1. **Configurable Response:**
   - Custom responses per guild
   - Random selection from multiple responses
   - Embed responses with more context

2. **Cooldown System:**
   - Prevent spam by rate-limiting responses
   - Per-channel or per-user cooldowns
   - Configurable cooldown duration

3. **Statistics Tracking:**
   - Track spoiler counts per user
   - Leaderboard of "most spoiler-prone" users
   - Channel statistics

4. **Advanced Detection:**
   - Detect spoiler context (movie, game, book)
   - Different responses based on content
   - Integration with spoiler databases

5. **Permissions:**
   - Allow certain roles to bypass detection
   - Channel-specific enable/disable
   - Opt-in/opt-out system

## Related Files

- **`utils/listeners.py`** - Shared message filtering utilities
- **`commands/soak/listener.py`** - Similar listener pattern (template used)
- **`bot.py`** - Package registration and loading

---

**Last Updated:** October 2025
**Maintenance:** Keep logging and error handling consistent with other listeners
**Next Review:** When additional listener features are requested
