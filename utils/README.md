# Utils Package Documentation
**Discord Bot v2.0 - Utility Functions and Helpers**

This package contains utility functions, helpers, and shared components used throughout the Discord bot application.

## 📋 Table of Contents

1. [**Structured Logging**](#-structured-logging) - Contextual logging with Discord integration
2. [**Future Utilities**](#-future-utilities) - Planned utility modules

---

## 🔍 Structured Logging

**Location:** `utils/logging.py`  
**Purpose:** Provides hybrid logging system with contextual information for Discord bot debugging and monitoring.

### **Quick Start**

```python
from utils.logging import get_contextual_logger, set_discord_context

class YourCommandCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.YourCommandCog')
    
    async def your_command(self, interaction: discord.Interaction, param: str):
        # Set Discord context for all subsequent log entries
        set_discord_context(
            interaction=interaction,
            command="/your-command",
            param_value=param
        )
        
        # Start operation timing and get trace ID
        trace_id = self.logger.start_operation("your_command_operation")
        
        try:
            self.logger.info("Command started")
            
            # Your command logic here
            result = await some_api_call(param)
            self.logger.debug("API call completed", result_count=len(result))
            
            self.logger.info("Command completed successfully")
            
        except Exception as e:
            self.logger.error("Command failed", error=e)
            raise
```

### **Key Features**

#### **🎯 Contextual Information**
Every log entry automatically includes:
- **Discord Context**: User ID, guild ID, guild name, channel ID
- **Command Context**: Command name, parameters
- **Operation Context**: Trace ID, operation name, execution duration
- **Custom Fields**: Additional context via keyword arguments

#### **⏱️ Automatic Timing**
```python
trace_id = self.logger.start_operation("complex_operation")
# ... do work ...
self.logger.info("Operation completed")  # Automatically includes duration_ms
```

#### **🔗 Request Tracing**
Track a single request through all log entries using trace IDs:
```bash
# Find all logs for a specific request
jq '.context.trace_id == "abc12345"' logs/discord_bot_v2.json
```

#### **📤 Hybrid Output**
- **Console**: Human-readable for development
- **Traditional File** (`discord_bot_v2.log`): Human-readable with debug info
- **JSON File** (`discord_bot_v2.json`): Structured for analysis

### **API Reference**

#### **Core Functions**

**`get_contextual_logger(logger_name: str) -> ContextualLogger`**
```python
# Get a logger instance for your module
logger = get_contextual_logger(f'{__name__}.MyClass')
```

**`set_discord_context(interaction=None, user_id=None, guild_id=None, **kwargs)`**
```python
# Set context from Discord interaction (recommended)
set_discord_context(interaction=interaction, command="/player", player_name="Mike Trout")

# Or set context manually
set_discord_context(user_id="123456", guild_id="987654", custom_field="value")
```

**`clear_context()`**
```python
# Clear the current logging context (usually not needed)
clear_context()
```

#### **ContextualLogger Methods**

**`start_operation(operation_name: str = None) -> str`**
```python
# Start timing and get trace ID
trace_id = logger.start_operation("player_search")
```

**`info(message: str, **kwargs)`**
```python
logger.info("Player found", player_id=123, team_name="Yankees")
```

**`debug(message: str, **kwargs)`**
```python
logger.debug("API call started", endpoint="players/search", timeout=30)
```

**`warning(message: str, **kwargs)`**
```python
logger.warning("Multiple players found", candidates=["Player A", "Player B"])
```

**`error(message: str, error: Exception = None, **kwargs)`**
```python
# With exception
logger.error("API call failed", error=e, retry_count=3)

# Without exception
logger.error("Validation failed", field="player_name", value="invalid")
```

**`exception(message: str, **kwargs)`**
```python
# Automatically captures current exception
try:
    risky_operation()
except:
    logger.exception("Unexpected error in operation", operation_id=123)
```

### **Output Examples**

#### **Console Output (Development)**
```
2025-08-14 14:32:15,123 - commands.players.info.PlayerInfoCommands - INFO - Player info command started
2025-08-14 14:32:16,456 - commands.players.info.PlayerInfoCommands - DEBUG - Starting player search
2025-08-14 14:32:18,789 - commands.players.info.PlayerInfoCommands - INFO - Command completed successfully
```

#### **JSON Output (Monitoring & Analysis)**
```json
{
  "timestamp": "2025-08-14T14:32:15.123Z",
  "level": "INFO",
  "logger": "commands.players.info.PlayerInfoCommands",
  "message": "Player info command started",
  "function": "player_info",
  "line": 50,
  "context": {
    "user_id": "123456789",
    "guild_id": "987654321",
    "guild_name": "SBA League",
    "channel_id": "555666777",
    "command": "/player",
    "player_name": "Mike Trout",
    "season": 12,
    "trace_id": "abc12345",
    "operation": "player_info_command"
  },
  "extra": {
    "duration_ms": 0
  }
}
```

#### **Error Output with Exception**
```json
{
  "timestamp": "2025-08-14T14:32:18.789Z",
  "level": "ERROR",
  "logger": "commands.players.info.PlayerInfoCommands",
  "message": "API call failed",
  "function": "player_info",
  "line": 125,
  "exception": {
    "type": "APITimeout",
    "message": "Request timed out after 30s",
    "traceback": "Traceback (most recent call last):\n  File ..."
  },
  "context": {
    "user_id": "123456789",
    "guild_id": "987654321",
    "command": "/player",
    "player_name": "Mike Trout",
    "trace_id": "abc12345"
  },
  "extra": {
    "duration_ms": 30000,
    "retry_count": 3,
    "endpoint": "players/search"
  }
}
```

### **Advanced Usage Patterns**

#### **API Call Logging**
```python
async def fetch_player_data(self, player_name: str):
    self.logger.debug("API call started", 
                     api_endpoint="players/search",
                     search_term=player_name,
                     timeout_ms=30000)
    
    try:
        result = await api_client.get("players", params=[("name", player_name)])
        self.logger.info("API call successful", 
                        results_found=len(result) if result else 0,
                        response_size_kb=len(str(result)) // 1024)
        return result
        
    except TimeoutError as e:
        self.logger.error("API timeout", 
                         error=e,
                         endpoint="players/search",
                         search_term=player_name)
        raise
```

#### **Performance Monitoring**
```python
async def complex_operation(self, data):
    trace_id = self.logger.start_operation("complex_operation")
    
    # Step 1
    self.logger.debug("Processing step 1", step="validation")
    validate_data(data)
    
    # Step 2  
    self.logger.debug("Processing step 2", step="transformation")
    processed = transform_data(data)
    
    # Step 3
    self.logger.debug("Processing step 3", step="persistence")
    result = await save_data(processed)
    
    self.logger.info("Complex operation completed",
                    input_size=len(data),
                    output_size=len(result),
                    steps_completed=3)
    
    # Final log automatically includes total duration_ms
```

#### **Error Context Enrichment**
```python
async def handle_player_command(self, interaction, player_name):
    set_discord_context(
        interaction=interaction,
        command="/player",
        player_name=player_name,
        # Add additional context that helps debugging
        user_permissions=interaction.user.guild_permissions.administrator,
        guild_member_count=len(interaction.guild.members),
        request_timestamp=discord.utils.utcnow().isoformat()
    )
    
    try:
        # Command logic
        pass
    except Exception as e:
        # Error logs will include all the above context automatically
        self.logger.error("Player command failed", 
                         error=e,
                         # Additional error-specific context
                         error_code="PLAYER_NOT_FOUND",
                         suggestion="Try using the full player name")
        raise
```

### **Querying JSON Logs**

#### **Using jq for Analysis**

**Find all errors:**
```bash
jq 'select(.level == "ERROR")' logs/discord_bot_v2.json
```

**Find slow operations (>5 seconds):**
```bash
jq 'select(.extra.duration_ms > 5000)' logs/discord_bot_v2.json
```

**Track a specific user's activity:**
```bash
jq 'select(.context.user_id == "123456789")' logs/discord_bot_v2.json
```

**Find API timeout errors:**
```bash
jq 'select(.exception.type == "APITimeout")' logs/discord_bot_v2.json
```

**Get error summary by type:**
```bash
jq -r 'select(.level == "ERROR") | .exception.type' logs/discord_bot_v2.json | sort | uniq -c
```

**Trace a complete request:**
```bash
jq 'select(.context.trace_id == "abc12345")' logs/discord_bot_v2.json | jq -s 'sort_by(.timestamp)'
```

#### **Performance Analysis**

**Average command execution time:**
```bash
jq -r 'select(.message == "Command completed successfully") | .extra.duration_ms' logs/discord_bot_v2.json | awk '{sum+=$1; n++} END {print sum/n}'
```

**Most active users:**
```bash
jq -r '.context.user_id' logs/discord_bot_v2.json | sort | uniq -c | sort -nr | head -10
```

**Command usage statistics:**
```bash
jq -r '.context.command' logs/discord_bot_v2.json | sort | uniq -c | sort -nr
```

### **Best Practices**

#### **✅ Do:**
1. **Always set Discord context** at the start of command handlers
2. **Use start_operation()** for timing critical operations
3. **Include relevant context** in log messages via keyword arguments
4. **Log at appropriate levels** (debug for detailed flow, info for milestones, warning for recoverable issues, error for failures)
5. **Include error context** when logging exceptions

#### **❌ Don't:**
1. **Don't log sensitive information** (passwords, tokens, personal data)
2. **Don't over-log in tight loops** (use sampling or conditional logging)
3. **Don't use string formatting in log messages** (use keyword arguments instead)
4. **Don't forget to handle exceptions** in logging code itself

#### **Performance Considerations**
- JSON serialization adds minimal overhead (~1-2ms per log entry)
- Context variables are async-safe and thread-local
- Log rotation prevents disk space issues
- Structured queries are much faster than grep on large files

### **Troubleshooting**

#### **Common Issues**

**Logs not appearing:**
- Check log level configuration in environment
- Verify logs/ directory permissions
- Ensure handlers are properly configured

**JSON serialization errors:**
- Avoid logging complex objects directly
- Convert objects to strings or dicts before logging
- The JSONFormatter handles most common types automatically

**Context not appearing in logs:**
- Ensure `set_discord_context()` is called before logging
- Context is tied to the current async task
- Check that context is not cleared prematurely

**Performance issues:**
- Monitor log file sizes and rotation
- Consider reducing log level in production
- Use sampling for high-frequency operations

---

## 🚀 Future Utilities

Additional utility modules planned for future implementation:

### **Discord Helpers** (Planned)
- Embed builders and formatters
- Permission checking decorators
- User mention and role utilities
- Message pagination helpers

### **API Utilities** (Planned)  
- Rate limiting decorators
- Response caching mechanisms
- Retry logic with exponential backoff
- Request validation helpers

### **Data Processing** (Planned)
- CSV/JSON export utilities
- Statistical calculation helpers
- Date/time formatting for baseball seasons
- Text processing and search utilities

### **Testing Utilities** (Planned)
- Mock Discord objects for testing
- Fixture generators for common test data
- Assertion helpers for Discord responses
- Test database setup and teardown

---

## 📚 Usage Examples by Module

### **Logging Integration in Commands**

```python
# commands/teams/roster.py
from utils.logging import get_contextual_logger, set_discord_context

class TeamRosterCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.TeamRosterCommands')
    
    @discord.app_commands.command(name="roster")
    async def team_roster(self, interaction, team_name: str, season: int = None):
        set_discord_context(
            interaction=interaction,
            command="/roster", 
            team_name=team_name,
            season=season
        )
        
        trace_id = self.logger.start_operation("team_roster_command")
        
        try:
            self.logger.info("Team roster command started")
            
            # Command implementation
            team = await team_service.find_team(team_name)
            self.logger.debug("Team found", team_id=team.id, team_abbreviation=team.abbrev)
            
            players = await team_service.get_roster(team.id, season)
            self.logger.info("Roster retrieved", player_count=len(players))
            
            # Create and send response
            embed = create_roster_embed(team, players)
            await interaction.followup.send(embed=embed)
            
            self.logger.info("Team roster command completed")
            
        except TeamNotFoundError as e:
            self.logger.warning("Team not found", search_term=team_name)
            await interaction.followup.send(f"❌ Team '{team_name}' not found", ephemeral=True)
            
        except Exception as e:
            self.logger.error("Team roster command failed", error=e)
            await interaction.followup.send("❌ Error retrieving team roster", ephemeral=True)
```

### **Service Layer Logging**

```python
# services/team_service.py  
from utils.logging import get_contextual_logger

class TeamService(BaseService[Team]):
    def __init__(self):
        super().__init__(Team, 'teams')
        self.logger = get_contextual_logger(f'{__name__}.TeamService')
    
    async def find_team(self, team_name: str) -> Team:
        self.logger.debug("Starting team search", search_term=team_name)
        
        # Try exact match first
        teams = await self.get_by_field('name', team_name)
        if len(teams) == 1:
            self.logger.debug("Exact team match found", team_id=teams[0].id)
            return teams[0]
        
        # Try abbreviation match
        teams = await self.get_by_field('abbrev', team_name.upper())
        if len(teams) == 1:
            self.logger.debug("Team abbreviation match found", team_id=teams[0].id)
            return teams[0]
        
        # Try fuzzy search
        all_teams = await self.get_all_items()
        matches = [t for t in all_teams if team_name.lower() in t.name.lower()]
        
        if len(matches) == 0:
            self.logger.warning("No team matches found", search_term=team_name)
            raise TeamNotFoundError(f"No team found matching '{team_name}'")
        elif len(matches) > 1:
            match_names = [t.name for t in matches]
            self.logger.warning("Multiple team matches found", 
                              search_term=team_name,
                              matches=match_names)
            raise MultipleTeamsFoundError(f"Multiple teams found: {', '.join(match_names)}")
        
        self.logger.debug("Fuzzy team match found", team_id=matches[0].id)
        return matches[0]
```

---

## 📁 File Structure

```
utils/
├── README.md          # This documentation
├── __init__.py        # Package initialization
└── logging.py         # Structured logging implementation

# Future files:
├── discord_helpers.py # Discord utility functions
├── api_utils.py       # API helper functions  
├── data_processing.py # Data manipulation utilities
└── testing.py         # Testing helper functions
```

---

**Last Updated:** Phase 2.1 - Structured Logging Implementation  
**Next Update:** When additional utility modules are added

For questions or improvements to the logging system, check the implementation in `utils/logging.py` or refer to the JSON log outputs in `logs/discord_bot_v2.json`.