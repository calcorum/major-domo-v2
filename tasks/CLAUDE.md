# Tasks Directory

The tasks directory contains automated background tasks for Discord Bot v2.0. These tasks handle periodic maintenance, data cleanup, and scheduled operations that run independently of user interactions.

## Architecture

### Task System Design
Tasks in Discord Bot v2.0 follow these patterns:
- **Discord.py tasks** using the `@tasks.loop` decorator
- **Structured logging** with contextual information
- **Error handling** with graceful degradation
- **Guild-specific operations** respecting bot permissions
- **Configurable intervals** via task decorators
- **Service layer integration** - ALWAYS use service methods, never direct API client access

### 🚨 CRITICAL: Service Layer Usage in Tasks

**Tasks MUST use the service layer for ALL API interactions.** Never bypass services by directly accessing the API client.

#### ❌ Anti-Pattern: Direct Client Access in Tasks

```python
# BAD: Don't do this in tasks
async def my_background_task(self):
    client = await some_service.get_client()  # ❌ WRONG
    response = await client.get('endpoint', params=[...])
    await client.patch(f'endpoint/{id}', data={'field': 'value'})
```

**Why this is bad:**
1. Breaks service layer abstraction
2. Makes testing harder (can't mock service methods)
3. Duplicates API logic across codebase
4. Misses service-level validation and caching
5. Creates maintenance nightmares when API changes

#### ✅ Correct Pattern: Use Service Methods

```python
# GOOD: Always use service methods
async def my_background_task(self):
    items = await some_service.get_items_by_criteria(...)  # ✅ CORRECT
    updated = await some_service.update_item(id, data)      # ✅ CORRECT
```

#### When Service Methods Don't Exist

If you need functionality that doesn't exist in a service:

1. **Add the method to the appropriate service** (preferred)
2. **Use existing BaseService methods** when possible
3. **Document the new method** with clear docstrings

**Example:**
```python
# In services/league_service.py
async def update_current_state(
    self,
    week: Optional[int] = None,
    freeze: Optional[bool] = None
) -> Optional[Current]:
    """Update current league state (week and/or freeze status)."""
    update_data = {}
    if week is not None:
        update_data['week'] = week
    if freeze is not None:
        update_data['freeze'] = freeze
    return await self.patch(current_id=1, model_data=update_data)

# In tasks/transaction_freeze.py
async def _begin_freeze(self, current: Current):
    updated_current = await league_service.update_current_state(
        week=new_week,
        freeze=True
    )  # ✅ Using service method
```

See `services/CLAUDE.md` for complete service layer best practices.

### Base Task Pattern
All tasks follow a consistent structure with **MANDATORY** safe startup:

```python
from discord.ext import tasks
from utils.logging import get_contextual_logger

class ExampleTask:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.ExampleTask')
        self.task_loop.start()

    def cog_unload(self):
        """Stop the task when cog is unloaded."""
        self.task_loop.cancel()

    @tasks.loop(hours=24)  # Run daily
    async def task_loop(self):
        """Main task implementation."""
        try:
            # Task logic here
            pass
        except Exception as e:
            self.logger.error("Task failed", error=e)

    @task_loop.before_loop
    async def before_task(self):
        """Wait for bot to be ready before starting - REQUIRED FOR SAFE STARTUP."""
        await self.bot.wait_until_ready()
        self.logger.info("Bot is ready, task starting")
```

### 🚨 CRITICAL: Safe Startup Pattern

**EVERY background task MUST use the `@task.before_loop` decorator with `await self.bot.wait_until_ready()`.**

This pattern prevents tasks from executing before:
- Discord connection is established
- Bot guilds are fully loaded
- Bot cache is populated
- Service dependencies are available

#### ✅ CORRECT Pattern (Always Use This)
```python
@tasks.loop(minutes=3)
async def my_task_loop(self):
    """Main task logic."""
    # Your task code here
    pass

@my_task_loop.before_loop
async def before_my_task(self):
    """Wait for bot to be ready before starting - REQUIRED."""
    await self.bot.wait_until_ready()
    self.logger.info("Bot is ready, my_task starting")
```

#### ❌ WRONG Pattern (Will Cause Errors)
```python
@tasks.loop(minutes=3)
async def my_task_loop(self):
    """Main task logic."""
    # Task starts immediately - bot may not be ready!
    # This will cause AttributeError, NoneType errors, etc.
    pass

# Missing @before_loop - BAD!
```

#### Why This Is Critical
Without the `before_loop` pattern:
- **Guild lookup fails** - `bot.get_guild()` returns `None`
- **Channel lookup fails** - `guild.text_channels` is empty or incomplete
- **Cache errors** - Discord objects not fully populated
- **Service failures** - Dependencies may not be initialized
- **Race conditions** - Task runs before bot state is stable

#### Implementation Checklist
When creating a new task, ensure:
- [ ] `@tasks.loop()` decorator on main loop method
- [ ] `@task.before_loop` decorator on before method
- [ ] `await self.bot.wait_until_ready()` in before method
- [ ] Log message confirming task is ready to start
- [ ] Task started in `__init__()` with `self.task_loop.start()`
- [ ] Task cancelled in `cog_unload()` with `self.task_loop.cancel()`

## Current Tasks

### Live Scorebug Tracker (`live_scorebug_tracker.py`)
**Purpose:** Automated live game score updates for active games

**Schedule:** Every 3 minutes

**Operations:**
- **Live Scores Channel Update:**
  - Reads all published scorecards from ScorecardTracker
  - Generates compact scorebug embeds for active games
  - Clears and updates `#live-sba-scores` channel
  - Filters out final games (only shows active/in-progress)

- **Voice Channel Description Update:**
  - For each active scorecard, checks for associated voice channel
  - Updates voice channel topic with live score (e.g., "BOS 4 @ 3 NYY")
  - Adds "- FINAL" suffix when game completes
  - Gracefully handles missing or deleted voice channels

#### Key Features
- **Restart Resilience:** Uses JSON-based scorecard tracking
- **Voice Integration:** Bi-directional integration with voice channel system
- **Rate Limiting:** 1-second delay between scorecard reads
- **Error Resilience:** Continues operation despite individual failures
- **Safe Startup:** Uses `@before_loop` pattern with `await bot.wait_until_ready()`

#### Configuration
The tracker respects configuration settings:

```python
# config.py settings
guild_id: int  # Target guild for operations
```

**Environment Variables:**
- `GUILD_ID` - Discord server ID

#### Scorecard Publishing
Users publish scorecards via `/publish-scorecard <url>`:
- Validates Google Sheets access and structure
- Stores text_channel_id → sheet_url mapping in JSON
- Persists across bot restarts

#### Voice Channel Association
When voice channels are created:
- Text channel ID stored in voice channel tracking data
- Enables scorebug → voice channel lookup
- Voice channel topic updated every 3 minutes with live scores

**Automatic Cleanup Integration:**
When voice channels are cleaned up (deleted after being empty):
- Voice cleanup service automatically unpublishes the associated scorecard
- Prevents live scorebug tracker from updating scores for games without active voice channels
- Ensures scorecard tracking stays synchronized with voice channel state
- Reduces unnecessary API calls to Google Sheets for inactive games

#### Channel Requirements
- **#live-sba-scores** - Live scorebug display channel

#### Error Handling
- Comprehensive try/catch blocks with structured logging
- Graceful degradation if channels not found
- Silent skip for deleted voice channels
- Prevents duplicate error messages
- Continues operation despite individual scorecard failures

### Draft Monitor (`draft_monitor.py`) (Updated December 2025)
**Purpose:** Automated draft timer monitoring, warnings, and auto-draft execution

**Schedule:** Smart polling intervals based on time remaining:
- **30 seconds** when >60s remaining on pick
- **15 seconds** when 30-60s remaining
- **5 seconds** when <30s remaining

**Operations:**
- **Timer Monitoring:**
  - Auto-starts when timer enabled via `/draft-admin timer`
  - Auto-starts when `/draft-admin set-pick` used with active timer
  - Self-terminates when `draft_data.timer = False`
  - Uses `_ensure_monitor_running()` helper for consistent management

- **On-Clock Announcements:**
  - Posts announcement embed when pick advances
  - Shows team name, pick info, and deadline
  - Displays team sWAR and cap space
  - Lists last 5 picks
  - Shows top 5 roster players by sWAR

- **Warning System:**
  - Sends 60-second warning to ping channel
  - Sends 30-second warning to ping channel
  - Resets warning flags when pick advances

- **Auto-Draft Execution:**
  - Triggers when pick deadline passes
  - Acquires global pick lock before auto-drafting
  - Tries each player in team's draft list until one succeeds
  - Validates cap space and player availability
  - Advances to next pick after auto-draft

#### Key Features
- **Auto-Start:** Starts automatically when timer enabled or pick set
- **Smart Polling:** Adjusts check frequency based on urgency
- **Self-Terminating:** Stops automatically when timer disabled (resource efficient)
- **Global Lock Integration:** Acquires same lock as `/draft` command
- **Crash Recovery:** Respects 30-second stale lock timeout
- **Safe Startup:** Uses `@before_loop` pattern with `await bot.wait_until_ready()`
- **Service Layer:** All API calls through services (no direct client access)

#### Configuration
The monitor respects draft configuration:

```python
# From DraftData model
timer: bool  # When False, monitor stops
pick_deadline: datetime  # Warning/auto-draft trigger
ping_channel_id: int  # Where warnings are sent
pick_minutes: int  # Timer duration per pick
```

**Environment Variables:**
- `GUILD_ID` - Discord server ID
- `SBA_CURRENT_SEASON` - Current draft season

#### Draft Lock Integration
The monitor integrates with the global pick lock:

```python
# In DraftPicksCog
self.pick_lock = asyncio.Lock()  # Shared lock
self.lock_acquired_at: Optional[datetime] = None
self.lock_acquired_by: Optional[int] = None

# Monitor acquires same lock for auto-draft
async with draft_picks_cog.pick_lock:
    draft_picks_cog.lock_acquired_at = datetime.now()
    draft_picks_cog.lock_acquired_by = None  # System auto-draft
    await self.auto_draft_current_pick()
```

#### Auto-Draft Process
1. Check if pick lock is available
2. Acquire global lock
3. Get team's draft list ordered by rank
4. For each player in list:
   - Validate player is still FA
   - Validate cap space
   - Attempt to draft player
   - Break on success
5. Advance to next pick
6. Release lock

#### Channel Requirements
- **ping_channel** - Where warnings and auto-draft announcements post

#### Error Handling
- Comprehensive try/catch blocks with structured logging
- Graceful degradation if channels not found
- Continues operation despite individual pick failures
- Task self-terminates on critical errors

**Resource Efficiency:**
This task is designed to run only during active drafts (~2 weeks per year). When `draft_data.timer = False`, the task calls `self.monitor_loop.cancel()` and stops consuming resources. Admin can restart via `/draft-admin timer on`.

### Transaction Freeze/Thaw (`transaction_freeze.py`)
**Purpose:** Automated weekly system for freezing transactions and processing contested player acquisitions

**Schedule:** Every minute (checks for specific times to trigger actions)

**📋 Implementation Documentation:** See `TRANSACTION_EXECUTION_AUTOMATION.md` for detailed automation plan

**Operations:**
- **Freeze Begin (Monday 00:00):**
  - Increments league week
  - Sets freeze flag to True
  - Runs regular transactions for the new week
  - Announces freeze period in #transaction-log
  - Posts weekly schedule info to #weekly-info (weeks 1-18 only)

- **Freeze End (Saturday 00:00):**
  - Processes frozen transactions with priority resolution
  - Resolves contested players (multiple teams want same player)
  - Uses team standings to determine priority (worst teams get first priority)
  - Cancels losing transactions and notifies GMs via DM
  - Unfreezes winning transactions
  - Posts successful transactions to #transaction-log
  - Announces thaw period

#### Key Features
- **Priority Resolution:** Uses team win percentage with random tiebreaker
- **Offseason Mode:** Respects `offseason_flag` config to skip operations
- **Contested Transaction Handling:** Fair resolution system for player conflicts
- **GM Notifications:** Direct messages to managers about cancelled moves
- **Comprehensive Logging:** Detailed logs for all freeze/thaw operations
- **Error Recovery:** Owner notifications on failures

#### ✅ Automated Player Roster Updates (Implemented October 2025)
**Feature Status:** Player roster updates now execute automatically during Monday freeze period.

**Implementation Details:**
- **Helper Method:** `_execute_player_update(player_id, new_team_id, player_name)` (lines 447-511)
  - Executes `PATCH /players/{player_id}?team_id={new_team_id}` via API client
  - Returns boolean success/failure status
  - Comprehensive logging with player/team context
  - Proper exception handling and re-raising

- **Integration Point:** `_run_transactions()` method (lines 348-379)
  - **Timing:** Executes on Monday 00:00 when freeze begins and week increments
  - Processes ALL transactions for the new week:
    - Regular transactions (submitted before freeze)
    - Previously frozen transactions that won contests
  - Rate limiting: 100ms delay between player updates
  - Success/failure tracking with detailed logs

- **Saturday Thaw Unchanged:** `_process_frozen_transactions()` only updates database records (cancelled/unfrozen status) - NO player PATCHes on Saturday

**Transaction Execution Timeline:**
1. **Monday 00:00** - Freeze begins, week increments, **player PATCHes execute**
2. **Monday-Saturday** - Teams submit frozen transactions (no execution)
3. **Saturday 00:00** - Resolve contests, update DB records only
4. **Next Monday 00:00** - Winning frozen transactions execute as part of new week

**Performance:**
- Rate limiting: 100ms between requests (prevents API overload)
- Typical execution: 31 transactions = ~3.1 seconds
- Graceful failure handling: Continues processing on individual errors

**Documentation:** See `TRANSACTION_EXECUTION_AUTOMATION.md` for:
- Complete implementation details and code examples
- Error handling strategies and retry logic
- Testing approaches and deployment checklist
- Week 19 manual execution example (31 transactions, 100% success rate)

#### Configuration
The freeze task respects configuration settings:

```python
# config.py settings
offseason_flag: bool = False  # When True, disables freeze/thaw operations
guild_id: int                 # Target guild for operations
```

**Environment Variables:**
- `OFFSEASON_FLAG=true` - Enables offseason mode (skips freeze/thaw)
- `GUILD_ID` - Discord server ID

#### Transaction Priority Logic
When multiple teams try to acquire the same player:
1. Calculate team win percentage from standings
2. Add small random component (5 decimal precision) for tiebreaking
3. Sort by priority (lowest win% = highest priority)
4. Team with lowest priority wins the player
5. All other teams have their transactions cancelled

**Tiebreaker Formula:**
```python
tiebreaker = team_win_percentage + random(0.00010000 to 0.00099999)
```

This ensures worst-record teams get priority while maintaining fairness through randomization.

#### Channel Requirements
- **#transaction-log** - Announcements and transaction posts
- **#weekly-info** - Weekly schedule information (cleared and updated)

#### Error Handling
- Comprehensive try/catch blocks with structured logging
- Owner DM notifications on failures
- Prevents duplicate error messages with warning flag
- Graceful degradation if channels not found
- Continues operation despite individual transaction failures

### Custom Command Cleanup (`custom_command_cleanup.py`)
**Purpose:** Automated cleanup system for user-created custom commands

**Schedule:** Daily (24 hours)

**Operations:**
- **Warning Phase:** Notifies users about commands at risk (unused for 60+ days)
- **Deletion Phase:** Removes commands unused for 90+ days
- **Admin Reporting:** Sends cleanup summaries to admin channels

#### Key Features
- **User Notifications:** Direct messages to command creators
- **Grace Period:** 30-day warning before deletion
- **Admin Transparency:** Optional summary reports
- **Bulk Operations:** Efficient batch processing
- **Error Resilience:** Continues operation despite individual failures

#### Configuration
The cleanup task respects guild settings and permissions:

```python
# Configuration via get_config()
guild_id = config.guild_id          # Target guild
admin_channels = ['admin', 'bot-logs']  # Admin notification channels
```

#### Notification System
**Warning Embed (30 days before deletion):**
- Lists commands at risk
- Shows days since last use
- Provides usage instructions
- Links to command management

**Deletion Embed (after deletion):**
- Lists deleted commands
- Shows final usage statistics
- Provides recreation instructions
- Explains cleanup policy

#### Admin Summary
Optional admin channel reporting includes:
- Number of warnings sent
- Number of commands deleted
- Current system statistics
- Next cleanup schedule

## Task Lifecycle

### Initialization
Tasks are initialized when the bot starts:

```python
# In bot startup
def setup_cleanup_task(bot: commands.Bot) -> CustomCommandCleanupTask:
    return CustomCommandCleanupTask(bot)

# Usage
cleanup_task = setup_cleanup_task(bot)
```

### Execution Flow
1. **Bot Ready Check:** Wait for `bot.wait_until_ready()`
2. **Guild Validation:** Verify bot has access to configured guild
3. **Permission Checks:** Ensure bot can send messages/DMs
4. **Main Operation:** Execute task logic with error handling
5. **Logging:** Record operation results and performance metrics
6. **Cleanup:** Reset state for next iteration

### Error Handling
Tasks implement comprehensive error handling:

```python
async def task_operation(self):
    try:
        # Main task logic
        result = await self.perform_operation()
        self.logger.info("Task completed", result=result)
    except SpecificException as e:
        self.logger.warning("Recoverable error", error=e)
        # Continue with degraded functionality
    except Exception as e:
        self.logger.error("Task failed", error=e)
        # Task will retry on next interval
```

## Development Patterns

### Creating New Tasks

1. **Inherit from Base Pattern**
```python
class NewTask:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.NewTask')
        self.main_loop.start()
```

2. **Configure Task Schedule**
```python
@tasks.loop(minutes=30)  # Every 30 minutes
# or
@tasks.loop(hours=6)     # Every 6 hours
# or
@tasks.loop(time=datetime.time(hour=3))  # Daily at 3 AM UTC
```

3. **Implement Before Loop**
```python
@main_loop.before_loop
async def before_loop(self):
    await self.bot.wait_until_ready()
    self.logger.info("Task initialized and ready")
```

4. **Add Cleanup Handling**
```python
def cog_unload(self):
    self.main_loop.cancel()
    self.logger.info("Task stopped")
```

### Task Categories

#### Maintenance Tasks
- **Data cleanup** (expired records, unused resources)
- **Cache management** (clear stale entries, optimize storage)
- **Log rotation** (archive old logs, manage disk space)

#### User Management
- **Inactive user cleanup** (remove old user data)
- **Permission auditing** (validate role assignments)
- **Usage analytics** (collect usage statistics)

#### System Monitoring
- **Health checks** (verify system components)
- **Performance monitoring** (track response times)
- **Error rate tracking** (monitor failure rates)

### Task Configuration

#### Environment Variables
Tasks respect standard bot configuration:
```python
GUILD_ID=12345...         # Target Discord guild
LOG_LEVEL=INFO           # Logging verbosity
REDIS_URL=redis://...    # Optional caching backend
```

#### Runtime Configuration
Tasks use the central config system:
```python
from config import get_config

config = get_config()
guild = self.bot.get_guild(config.guild_id)
```

## Logging and Monitoring

### Structured Logging
Tasks use contextual logging for observability:

```python
self.logger.info(
    "Cleanup task starting",
    guild_id=guild.id,
    commands_at_risk=len(at_risk_commands)
)

self.logger.warning(
    "User DM failed",
    user_id=user.id,
    reason="DMs disabled"
)

self.logger.error(
    "Task operation failed",
    operation="delete_commands",
    error=str(e)
)
```

### Performance Tracking
Tasks log timing and performance metrics:

```python
start_time = datetime.utcnow()
# ... task operations ...
duration = (datetime.utcnow() - start_time).total_seconds()

self.logger.info(
    "Task completed",
    duration_seconds=duration,
    operations_completed=operation_count
)
```

### Error Recovery
Tasks implement retry logic and graceful degradation:

```python
async def process_with_retry(self, operation, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await operation()
        except RecoverableError as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

## Testing Strategies

### Unit Testing Tasks
```python
@pytest.mark.asyncio
async def test_custom_command_cleanup():
    # Mock bot and services
    bot = AsyncMock()
    task = CustomCommandCleanupTask(bot)

    # Mock service responses
    with patch('services.custom_commands_service') as mock_service:
        mock_service.get_commands_needing_warning.return_value = []

        # Test task execution
        await task.cleanup_task()

        # Verify service calls
        mock_service.get_commands_needing_warning.assert_called_once()
```

### Integration Testing
```python
@pytest.mark.integration
async def test_cleanup_task_with_real_data():
    # Test with actual Discord bot instance
    # Use test guild and test data
    # Verify real Discord API interactions
```

### Performance Testing
```python
@pytest.mark.performance
async def test_cleanup_task_performance():
    # Test with large datasets
    # Measure execution time
    # Verify memory usage
```

## Security Considerations

### Permission Validation
Tasks verify bot permissions before operations:

```python
async def check_permissions(self, guild: discord.Guild) -> bool:
    """Verify bot has required permissions."""
    bot_member = guild.me

    # Check for required permissions
    if not bot_member.guild_permissions.send_messages:
        self.logger.warning("Missing send_messages permission")
        return False

    return True
```

### Data Privacy
Tasks handle user data responsibly:
- **Minimal data access** - Only access required data
- **Secure logging** - Avoid logging sensitive information
- **GDPR compliance** - Respect user data rights
- **Permission respect** - Honor user privacy settings

### Rate Limiting
Tasks implement Discord API rate limiting:

```python
async def send_notifications_with_rate_limiting(self, notifications):
    """Send notifications with rate limiting."""
    for notification in notifications:
        try:
            await self.send_notification(notification)
            await asyncio.sleep(1)  # Avoid rate limits
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limited
                retry_after = e.response.headers.get('Retry-After', 60)
                await asyncio.sleep(int(retry_after))
```

## Future Task Ideas

### Potential Additions
- **Database maintenance** - Optimize database performance
- **Backup automation** - Create data backups
- **Usage analytics** - Generate usage reports
- **Health monitoring** - System health checks
- **Cache warming** - Pre-populate frequently accessed data

### Scalability Patterns
- **Task queues** - Distribute work across multiple workers
- **Sharding support** - Handle multiple Discord guilds
- **Load balancing** - Distribute task execution
- **Monitoring integration** - External monitoring systems

---

**Next Steps for AI Agents:**
1. Review the existing cleanup task implementation
2. Understand the Discord.py tasks framework
3. Follow the structured logging patterns
4. Implement proper error handling and recovery
5. Consider guild permissions and user privacy
6. Test tasks thoroughly before deployment