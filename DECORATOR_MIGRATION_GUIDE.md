# Discord Bot v2.0 - Logging Decorator Migration Guide

This guide documents the process for migrating existing Discord commands to use the new `@logged_command` decorator, which eliminates boilerplate logging code and standardizes command logging patterns.

## Overview

The `@logged_command` decorator automatically handles:
- Discord context setting with interaction details
- Operation timing and trace ID generation
- Command start/completion/failure logging
- Exception handling and logging
- Parameter logging with exclusion options

## What Was Changed

### Before (Manual Logging Pattern)
```python
@discord.app_commands.command(name="roster", description="Display team roster")
async def team_roster(self, interaction: discord.Interaction, abbrev: str):
    set_discord_context(interaction=interaction, command="/roster")
    trace_id = logger.start_operation("team_roster_command")
    
    try:
        logger.info("Team roster command started")
        # Business logic here
        logger.info("Team roster command completed successfully")
        
    except Exception as e:
        logger.error("Team roster command failed", error=e)
        # Error handling
        
    finally:
        logger.end_operation(trace_id)
```

### After (With Decorator)
```python
@discord.app_commands.command(name="roster", description="Display team roster")
@logged_command("/roster")
async def team_roster(self, interaction: discord.Interaction, abbrev: str):
    # Business logic only - no logging boilerplate needed
    # All try/catch/finally logging is handled automatically
```

## Step-by-Step Migration Process

### 1. Update Imports

**Add the decorator import:**
```python
from utils.decorators import logged_command
```

**Remove unused logging imports (if no longer needed):**
```python
# Remove if not used elsewhere in the file:
from utils.logging import set_discord_context  # Usually can be removed
```

### 2. Ensure Class Has Logger

**Before migration, ensure the command class has a logger:**
```python
class YourCommandCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.YourCommandCog')  # Add this line
```

### 3. Apply the Decorator

**Add the decorator above the command method:**
```python
@discord.app_commands.command(name="your-command", description="...")
@logged_command("/your-command")  # Add this line
async def your_command_method(self, interaction, ...):
```

### 4. Remove Manual Logging Boilerplate

**Remove these patterns:**
- `set_discord_context(interaction=interaction, command="...")`
- `trace_id = logger.start_operation("...")`
- `try:` / `except:` / `finally:` blocks used only for logging
- `logger.info("Command started")` and `logger.info("Command completed")`
- `logger.error("Command failed", error=e)` in catch blocks
- `logger.end_operation(trace_id)`

**Keep these:**
- Business logic logging (e.g., `logger.info("Team found", team_id=123)`)
- Specific error handling (user-facing error messages)
- All business logic and Discord interaction code

### 5. Test the Migration

**Run the tests to ensure the migration works:**
```bash
python -m pytest tests/test_utils_decorators.py -v
python -m pytest  # Run all tests to ensure no regressions
```

## Example: Complete Migration

### commands/teams/roster.py (BEFORE)
```python
"""Team roster commands for Discord Bot v2.0"""
import logging
from typing import Optional, Dict, Any, List
import discord
from discord.ext import commands
from utils.logging import get_contextual_logger, set_discord_context

class TeamRosterCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Missing: self.logger = get_contextual_logger(...)
    
    @discord.app_commands.command(name="roster", description="Display team roster")
    async def team_roster(self, interaction: discord.Interaction, abbrev: str):
        set_discord_context(interaction=interaction, command="/roster")
        trace_id = logger.start_operation("team_roster_command")
        
        try:
            await interaction.response.defer()
            logger.info("Team roster command requested", team_abbrev=abbrev)
            
            # Business logic
            team = await team_service.get_team_by_abbrev(abbrev)
            # ... more business logic ...
            
            logger.info("Team roster displayed successfully")
            
        except BotException as e:
            logger.error("Bot error in team roster command", error=str(e))
            # Error handling
            
        except Exception as e:
            logger.error("Unexpected error in team roster command", error=str(e))
            # Error handling
            
        finally:
            logger.end_operation(trace_id)
```

### commands/teams/roster.py (AFTER)
```python
"""Team roster commands for Discord Bot v2.0"""
import logging
from typing import Optional, Dict, Any, List
import discord
from discord.ext import commands
from utils.logging import get_contextual_logger
from utils.decorators import logged_command  # Added

class TeamRosterCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.TeamRosterCommands')  # Added
    
    @discord.app_commands.command(name="roster", description="Display team roster")
    @logged_command("/roster")  # Added
    async def team_roster(self, interaction: discord.Interaction, abbrev: str):
        await interaction.response.defer()
        
        # Business logic only - all boilerplate logging removed
        team = await team_service.get_team_by_abbrev(abbrev)
        
        if team is None:
            self.logger.info("Team not found", team_abbrev=abbrev)  # Business logic logging
            # ... handle not found ...
            return
        
        # ... rest of business logic ...
        
        self.logger.info("Team roster displayed successfully",  # Business logic logging
                   team_id=team.id, team_abbrev=team.abbrev)
```

## Migration Checklist for Each Command

- [ ] Add `from utils.decorators import logged_command` import
- [ ] Ensure class has `self.logger = get_contextual_logger(...)` in `__init__`
- [ ] Add `@logged_command("/command-name")` decorator
- [ ] Remove `set_discord_context()` call
- [ ] Remove `trace_id = logger.start_operation()` call
- [ ] Remove `try:` block (if only used for logging)
- [ ] Remove `logger.info("Command started")` and `logger.info("Command completed")`
- [ ] Remove generic `except Exception as e:` blocks (if only used for logging)
- [ ] Remove `logger.error("Command failed")` calls
- [ ] Remove `finally:` block and `logger.end_operation()` call
- [ ] Keep business logic logging (specific info/debug/warning messages)
- [ ] Keep error handling that sends user-facing messages
- [ ] Test the command works correctly

## Decorator Options

### Basic Usage
```python
@logged_command("/command-name")
async def my_command(self, interaction, param1: str):
    # Implementation
```

### Auto-Detect Command Name
```python
@logged_command()  # Will use "/my-command" based on function name
async def my_command(self, interaction, param1: str):
    # Implementation
```

### Exclude Sensitive Parameters
```python
@logged_command("/login", exclude_params=["password", "token"])
async def login_command(self, interaction, username: str, password: str):
    # password won't appear in logs
```

### Disable Parameter Logging
```python
@logged_command("/sensitive-command", log_params=False)
async def sensitive_command(self, interaction, sensitive_data: str):
    # No parameters will be logged
```

## Expected Benefits

### Lines of Code Reduction
- **Before**: ~25-35 lines per command (including try/catch/finally)
- **After**: ~10-15 lines per command
- **Reduction**: ~15-20 lines of boilerplate per command

### Consistency Improvements
- Standardized logging format across all commands
- Consistent error handling patterns
- Automatic trace ID generation and correlation
- Reduced chance of logging bugs (forgotten `end_operation`, etc.)

### Maintainability
- Single point of change for logging behavior
- Easier to add new logging features (e.g., performance metrics)
- Less code duplication
- Clearer separation of business logic and infrastructure

## Files to Migrate

Based on the current codebase structure, these files likely need migration:

```
commands/
├── league/
│   └── info.py
├── players/
│   └── info.py
└── teams/
    ├── info.py
    └── roster.py  # ✅ Already migrated (example)
```

## Testing Migration

### 1. Unit Tests
```bash
# Test the decorator itself
python -m pytest tests/test_utils_decorators.py -v

# Test migrated commands still work
python -m pytest tests/ -v
```

### 2. Integration Testing
```bash
# Verify command registration still works
python -c "
import discord
from commands.teams.roster import TeamRosterCommands
from discord.ext import commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)
cog = TeamRosterCommands(bot)
print('✅ Command loads successfully')
"
```

### 3. Log Output Verification
After migration, verify that log entries still contain:
- Correct trace IDs for request correlation
- Command start/completion messages
- Error logging with exceptions
- Business logic messages
- Discord context (user_id, guild_id, etc.)

## Troubleshooting

### Common Issues

**Issue**: `AttributeError: 'YourCog' object has no attribute 'logger'`
**Solution**: Add `self.logger = get_contextual_logger(...)` to the cog's `__init__` method

**Issue**: Parameters not appearing in logs
**Solution**: Check if parameters are in the `exclude_params` list or if `log_params=False`

**Issue**: Command not registering with Discord
**Solution**: Ensure `@logged_command()` is placed AFTER `@discord.app_commands.command()`

**Issue**: Signature errors during command registration
**Solution**: The decorator preserves signatures automatically; if issues persist, check Discord.py version compatibility

### Debugging Steps

1. Check that all imports are correct
2. Verify logger exists on the cog instance
3. Run unit tests to ensure decorator functionality
4. Check log files for expected trace IDs and messages
5. Test command execution in a development environment

## Migration Timeline

**Recommended approach**: Migrate one command at a time and test thoroughly before moving to the next.

1. **Phase 1**: Migrate simple commands (no complex error handling)
2. **Phase 2**: Migrate commands with custom error handling
3. **Phase 3**: Migrate complex commands with multiple operations
4. **Phase 4**: Update documentation and add any additional decorator features

This approach ensures that any issues can be isolated and resolved before affecting multiple commands.