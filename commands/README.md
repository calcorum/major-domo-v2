# Commands Package Documentation
**Discord Bot v2.0 - Scalable Command Architecture**

This document outlines the command architecture, patterns, and best practices established for the SBA Discord Bot v2.0.

## 📁 Architecture Overview

### **Package Structure**
```
commands/
├── README.md                    # This documentation
├── __init__.py                  # Future: Global command utilities
└── players/                     # Player-related commands
    ├── __init__.py             # Package setup with resilient loading
    └── info.py                 # Player information commands
```

### **Future Expansion (Phase 2+)**
```
commands/
├── README.md
├── __init__.py                  
├── players/                     # ✅ COMPLETED
│   ├── __init__.py
│   ├── info.py                 # /player command
│   ├── search.py               # /player-search, /player-lookup
│   ├── stats.py                # /player-stats, /player-compare
│   └── rankings.py             # /player-rankings, /leaderboard
├── teams/                       # 🔄 PLANNED
│   ├── __init__.py
│   ├── roster.py               # /team-roster, /team-depth
│   ├── stats.py                # /team-stats, /team-leaders
│   └── schedule.py             # /team-schedule, /team-record
├── league/                      # 🔄 PLANNED
│   ├── __init__.py
│   ├── standings.py            # /standings, /playoff-race
│   ├── schedule.py             # /schedule, /scores
│   └── leaders.py              # /leaders, /awards
├── draft/                       # 🔄 PLANNED
│   ├── __init__.py
│   ├── picks.py                # /draft-pick, /draft-order
│   ├── board.py                # /draft-board, /draft-list
│   └── timer.py                # /draft-status, /draft-timer
├── transactions/                # 🔄 PLANNED
│   ├── __init__.py
│   ├── trades.py               # /trade, /trade-history
│   ├── waivers.py              # /waivers, /free-agents
│   └── history.py              # /transaction-history
├── admin/                       # 🔄 PLANNED
│   ├── __init__.py
│   ├── league.py               # /admin-season, /admin-week
│   ├── draft.py                # /admin-draft, /admin-timer
│   └── system.py               # /health, /sync-commands
└── utils/                       # 🔄 PLANNED
    ├── __init__.py
    ├── dice.py                 # /roll, /dice
    └── fun.py                  # Fun/misc commands
```

## 🏗️ Design Principles

### **1. Single Responsibility**
- Each file handles 2-4 closely related commands
- Clear logical grouping by domain (players, teams, etc.)
- Focused functionality reduces complexity

### **2. Resilient Loading**
- One failed cog doesn't break the entire package
- Loop-based loading with comprehensive error handling
- Clear logging for debugging and monitoring

### **3. Scalable Architecture**
- Easy to add new packages and cogs
- Consistent patterns across all command groups
- Future-proof structure for bot growth

### **4. Modern Discord.py Patterns**
- Application commands (slash commands) only
- Proper error handling with user-friendly messages
- Async/await throughout
- Type hints and comprehensive documentation

## 🔧 Implementation Patterns

### **Command Package Structure**

#### **Individual Command File (e.g., `players/info.py`)**
```python
"""
Player Information Commands

Implements slash commands for displaying player information and statistics.
"""
import logging
from typing import Optional

import discord
from discord.ext import commands

from services.player_service import player_service
from exceptions import BotException

logger = logging.getLogger(f'{__name__}.PlayerInfoCommands')


class PlayerInfoCommands(commands.Cog):
    """Player information and statistics command handlers."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @discord.app_commands.command(
        name="player",
        description="Display player information and statistics"
    )
    @discord.app_commands.describe(
        name="Player name to search for",
        season="Season to show stats for (defaults to current season)"
    )
    async def player_info(
        self,
        interaction: discord.Interaction,
        name: str,
        season: Optional[int] = None
    ):
        """Display player card with statistics."""
        try:
            # Always defer for potentially slow API calls
            await interaction.response.defer()
            
            # Command implementation here
            # Use logger for error logging
            # Create Discord embeds for responses
            
        except Exception as e:
            logger.error(f"Player info command error: {e}", exc_info=True)
            error_msg = "❌ Error retrieving player information."
            
            if interaction.response.is_done():
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                await interaction.response.send_message(error_msg, ephemeral=True)


async def setup(bot: commands.Bot):
    """Load the player info commands cog."""
    await bot.add_cog(PlayerInfoCommands(bot))
```

#### **Package __init__.py with Resilient Loading**
```python
"""
Player Commands Package

This package contains all player-related Discord commands organized into focused modules.
"""
import logging
from discord.ext import commands

from .info import PlayerInfoCommands
# Future imports:
# from .search import PlayerSearchCommands
# from .stats import PlayerStatsCommands

logger = logging.getLogger(__name__)


async def setup_players(bot: commands.Bot):
    """
    Setup all player command modules.
    
    Returns:
        tuple: (successful_count, failed_count, failed_modules)
    """
    # Define all player command cogs to load
    player_cogs = [
        ("PlayerInfoCommands", PlayerInfoCommands),
        # Future cogs:
        # ("PlayerSearchCommands", PlayerSearchCommands),
        # ("PlayerStatsCommands", PlayerStatsCommands), 
    ]
    
    successful = 0
    failed = 0
    failed_modules = []
    
    for cog_name, cog_class in player_cogs:
        try:
            await bot.add_cog(cog_class(bot))
            logger.info(f"✅ Loaded {cog_name}")
            successful += 1
        except Exception as e:
            logger.error(f"❌ Failed to load {cog_name}: {e}", exc_info=True)
            failed += 1
            failed_modules.append(cog_name)
    
    # Log summary
    if failed == 0:
        logger.info(f"🎉 All {successful} player command modules loaded successfully")
    else:
        logger.warning(f"⚠️  Player commands loaded with issues: {successful} successful, {failed} failed")
    
    return successful, failed, failed_modules


# Export the setup function for easy importing
__all__ = ['setup_players', 'PlayerInfoCommands']
```

## 🔄 Smart Command Syncing

### **Hash-Based Change Detection**
The bot implements smart command syncing that only updates Discord when commands actually change:

**Development Mode:**
- Automatically detects command changes using SHA-256 hashing
- Only syncs when changes are detected
- Saves hash to `.last_command_hash` for comparison
- Prevents unnecessary Discord API calls

**Production Mode:**
- No automatic syncing
- Commands must be manually synced using `/sync` command
- Prevents accidental command updates in production

### **How It Works**
1. **Hash Generation**: Creates hash of command names, descriptions, and parameters
2. **Comparison**: Compares current hash with stored hash from `.last_command_hash`
3. **Conditional Sync**: Only syncs if hashes differ or no previous hash exists
4. **Hash Storage**: Saves new hash after successful sync

### **Benefits**
- ✅ **API Efficiency**: Avoids Discord rate limits
- ✅ **Development Speed**: Fast restarts when no command changes
- ✅ **Production Safety**: No accidental command updates
- ✅ **Consistency**: Commands stay consistent across restarts

## 🚀 Bot Integration

### **Command Loading in bot.py**
```python
async def setup_hook(self):
    """Called when the bot is starting up."""
    # Load command packages
    await self._load_command_packages()
    
    # Smart command syncing: auto-sync in development if changes detected
    config = get_config()
    if config.is_development:
        if await self._should_sync_commands():
            self.logger.info("Development mode: changes detected, syncing commands...")
            await self._sync_commands()
            await self._save_command_hash()
        else:
            self.logger.info("Development mode: no command changes detected, skipping sync")
    else:
        self.logger.info("Production mode: commands loaded but not auto-synced")

async def _load_command_packages(self):
    """Load all command packages with resilient error handling."""
    from commands.players import setup_players
    
    # Define command packages to load
    command_packages = [
        ("players", setup_players),
        # Future packages:
        # ("teams", setup_teams),
        # ("league", setup_league), 
    ]
    
    # Loop-based loading with error isolation
    for package_name, setup_func in command_packages:
        try:
            successful, failed, failed_modules = await setup_func(self)
            # Log results
        except Exception as e:
            self.logger.error(f"❌ Failed to load {package_name} package: {e}")
```

## 📋 Development Guidelines

### **Adding New Command Packages**

#### **1. Create Package Structure**
```bash
mkdir commands/teams
touch commands/teams/__init__.py
touch commands/teams/roster.py
```

#### **2. Implement Command Module**
- Follow the pattern from `players/info.py`
- Use module-level logger: `logger = logging.getLogger(f'{__name__}.ClassName')`
- Always defer responses: `await interaction.response.defer()`
- Comprehensive error handling with user-friendly messages
- Type hints and docstrings

#### **3. Create Package Setup Function**
- Follow the pattern from `players/__init__.py`
- Use loop-based cog loading with error isolation
- Return tuple: `(successful, failed, failed_modules)`
- Comprehensive logging with emojis for quick scanning

#### **4. Register in Bot**
- Add import to `_load_command_packages()` in `bot.py`
- Add to `command_packages` list
- Test in development environment

### **Adding Commands to Existing Packages**

#### **1. Create New Command Module**
```python
# commands/players/search.py
class PlayerSearchCommands(commands.Cog):
    # Implementation
    pass

async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerSearchCommands(bot))
```

#### **2. Update Package __init__.py**
```python
from .search import PlayerSearchCommands

# Add to player_cogs list
player_cogs = [
    ("PlayerInfoCommands", PlayerInfoCommands),
    ("PlayerSearchCommands", PlayerSearchCommands),  # New cog
]
```

#### **3. Test Import Structure**
```python
# Verify imports work
from commands.players import setup_players
from commands.players.search import PlayerSearchCommands
```

## 🎯 Best Practices

### **Command Implementation**
1. **Always defer responses** for API calls: `await interaction.response.defer()`
2. **Use ephemeral responses** for errors: `ephemeral=True`
3. **Comprehensive error handling** with try/except blocks
4. **User-friendly error messages** with emojis
5. **Proper logging** with context and stack traces
6. **Type hints** on all parameters and return values
7. **Descriptive docstrings** for commands and methods

### **Package Organization**
1. **2-4 commands per file** maximum
2. **Logical grouping** by functionality/domain
3. **Consistent naming** patterns across packages
4. **Module-level logging** for clean, consistent logs
5. **Loop-based cog loading** for error resilience
6. **Comprehensive return values** from setup functions

### **Error Handling**
1. **Package-level isolation** - one failed cog doesn't break the package
2. **Clear error logging** with stack traces for debugging
3. **User-friendly messages** that don't expose internal errors
4. **Graceful degradation** when possible
5. **Metric reporting** for monitoring (success/failure counts)

## 📊 Monitoring & Metrics

### **Startup Logging**
The command loading system provides comprehensive metrics:

```
INFO - Loading players commands...
INFO - ✅ Loaded PlayerInfoCommands
INFO - 🎉 All 1 player command modules loaded successfully
INFO - ✅ players commands loaded successfully (1 cogs)
INFO - 🎉 All command packages loaded successfully (1 total cogs)
```

### **Error Scenarios**
```
ERROR - ❌ Failed to load PlayerInfoCommands: <error details>
WARNING - ⚠️  Player commands loaded with issues: 0 successful, 1 failed
WARNING - Failed modules: PlayerInfoCommands
```

### **Command Sync Logging**
```
INFO - Development mode: changes detected, syncing commands...
INFO - Synced 1 commands to guild 123456789
```

or

```
INFO - Development mode: no command changes detected, skipping sync
```

## 🔧 Troubleshooting

### **Common Issues**

#### **Import Errors**
- Check that `__init__.py` files exist in all packages
- Verify cog class names match imports
- Ensure service dependencies are available

#### **Command Not Loading**
- Check logs for specific error messages
- Verify cog is added to the package's cog list
- Test individual module imports in Python REPL

#### **Commands Not Syncing**
- Check if running in development mode (`config.is_development`)
- Verify `.last_command_hash` file permissions
- Use manual `/sync` command for troubleshooting
- Check Discord API rate limits

#### **Performance Issues**
- Monitor command loading times in logs
- Check for unnecessary API calls during startup
- Verify hash-based sync is working correctly

### **Debugging Tips**
1. **Use the logs** - comprehensive logging shows exactly what's happening
2. **Test imports individually** - isolate package/module issues
3. **Check hash file** - verify command change detection is working
4. **Monitor Discord API** - watch for rate limiting or errors
5. **Use development mode** - auto-sync helps debug command issues

## 📦 Command Groups Pattern

### **⚠️ CRITICAL: Use `app_commands.Group`, NOT `commands.GroupCog`**

Discord.py provides two ways to create command groups (e.g., `/injury roll`, `/injury clear`):
1. **`app_commands.Group`** ✅ **RECOMMENDED - Use this pattern**
2. **`commands.GroupCog`** ❌ **AVOID - Has interaction timing issues**

### **Why `commands.GroupCog` Fails**

`commands.GroupCog` has a critical bug that causes **duplicate interaction processing**, leading to:
- **404 "Unknown interaction" errors** when trying to defer/respond
- **Interaction already acknowledged errors** in error handlers
- **Commands fail randomly** even with proper error handling

**Root Cause:** GroupCog triggers the command handler twice for a single interaction, causing the first execution to consume the interaction token before the second execution can respond.

### **✅ Correct Pattern: `app_commands.Group`**

Use the same pattern as `ChartCategoryGroup` and `ChartManageGroup`:

```python
from discord import app_commands
from discord.ext import commands
from utils.decorators import logged_command

class InjuryGroup(app_commands.Group):
    """Injury management command group."""

    def __init__(self):
        super().__init__(
            name="injury",
            description="Injury management commands"
        )
        self.logger = get_contextual_logger(f'{__name__}.InjuryGroup')

    @app_commands.command(name="roll", description="Roll for injury")
    @logged_command("/injury roll")
    async def injury_roll(self, interaction: discord.Interaction, player_name: str):
        """Roll for injury using player's injury rating."""
        await interaction.response.defer()

        # Command implementation
        # No try/catch needed - @logged_command handles it

async def setup(bot: commands.Bot):
    """Setup function for loading the injury commands."""
    bot.tree.add_command(InjuryGroup())
```

### **Key Differences**

| Feature | `app_commands.Group` ✅ | `commands.GroupCog` ❌ |
|---------|------------------------|------------------------|
| **Registration** | `bot.tree.add_command(Group())` | `await bot.add_cog(Cog(bot))` |
| **Initialization** | `__init__(self)` no bot param | `__init__(self, bot)` requires bot |
| **Decorator Support** | `@logged_command` works perfectly | Causes duplicate execution |
| **Interaction Handling** | Single execution, reliable | Duplicate execution, 404 errors |
| **Recommended Use** | ✅ All command groups | ❌ Never use |

### **Migration from GroupCog to Group**

If you have an existing `commands.GroupCog`, convert it:

1. **Change class inheritance:**
   ```python
   # Before
   class InjuryCog(commands.GroupCog, name="injury"):
       def __init__(self, bot):
           self.bot = bot
           super().__init__()

   # After
   class InjuryGroup(app_commands.Group):
       def __init__(self):
           super().__init__(name="injury", description="...")
   ```

2. **Update registration:**
   ```python
   # Before
   await bot.add_cog(InjuryCog(bot))

   # After
   bot.tree.add_command(InjuryGroup())
   ```

3. **Remove duplicate interaction checks:**
   ```python
   # Before (needed for GroupCog bug workaround)
   if not interaction.response.is_done():
       await interaction.response.defer()

   # After (clean, simple)
   await interaction.response.defer()
   ```

### **Working Examples**

**Good examples to reference:**
- `commands/utilities/charts.py` - `ChartManageGroup` and `ChartCategoryGroup`
- `commands/injuries/management.py` - `InjuryGroup`

Both use `app_commands.Group` successfully with `@logged_command` decorators.

## 🚦 Future Enhancements

### **Planned Features**
- **Permission Decorators**: Role-based command restrictions per package
- **Dynamic Loading**: Hot-reload commands without bot restart
- **Usage Metrics**: Command usage tracking and analytics
- **Rate Limiting**: Per-command rate limiting for resource management

### **Architecture Improvements**
- **Shared Utilities**: Common embed builders, decorators, helpers
- **Configuration**: Per-package configuration and feature flags
- **Testing**: Automated testing for command packages
- **Documentation**: Auto-generated command documentation
- **Monitoring**: Health checks and performance metrics per package

This architecture provides a solid foundation for scaling the Discord bot while maintaining code quality, reliability, and developer productivity.

---

**Last Updated:** Phase 2.1 - Command Package Conversion  
**Next Review:** After implementing teams/ and league/ packages