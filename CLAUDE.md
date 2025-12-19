# 🚨 CRITICAL: @ MENTION HANDLING 🚨
When ANY file is mentioned with @ syntax, you MUST IMMEDIATELY call Read tool on that file BEFORE responding.
You will see automatic loads of any @ mentioned filed, this is NOT ENOUGH, it only loads the file contents.
You MUST perform Read tool calls on the files directly, even if they were @ included.
This is NOT optional - it loads required CLAUDE.md context. along the file path.
See @./.claude/force-claude-reads.md for details.

---

# CLAUDE.md - Discord Bot v2.0

This file provides comprehensive guidance to Claude Code (claude.ai/code) when working with the Discord Bot v2.0 codebase.

**🔍 IMPORTANT:** Always check CLAUDE.md files in the current and parent directories for specific reference information and implementation details before making changes or additions to the codebase.

## 📚 Documentation References

### Core Documentation Files
- **[commands/CLAUDE.md](commands/CLAUDE.md)** - Command architecture, patterns, and implementation guidelines
- **[services/CLAUDE.md](services/CLAUDE.md)** - Service layer architecture, BaseService patterns, and API interactions
- **[models/CLAUDE.md](models/CLAUDE.md)** - Pydantic models, validation patterns, and data structures
- **[views/CLAUDE.md](views/CLAUDE.md)** - Discord UI components, embeds, modals, and interactive elements
- **[tasks/CLAUDE.md](tasks/CLAUDE.md)** - Background tasks, automated cleanup, and scheduled operations
- **[tests/CLAUDE.md](tests/CLAUDE.md)** - Testing strategies, patterns, and lessons learned
- **[utils/CLAUDE.md](utils/CLAUDE.md)** - Utility functions, logging system, caching, and decorators

### Command-Specific Documentation
- **[commands/league/CLAUDE.md](commands/league/CLAUDE.md)** - League-wide commands (/league, /standings, /schedule)
- **[commands/players/CLAUDE.md](commands/players/CLAUDE.md)** - Player information commands (/player)
- **[commands/teams/CLAUDE.md](commands/teams/CLAUDE.md)** - Team information and roster commands (/team, /teams, /roster)
- **[commands/transactions/CLAUDE.md](commands/transactions/CLAUDE.md)** - Transaction management commands (/mymoves, /legal)
- **[commands/voice/CLAUDE.md](commands/voice/CLAUDE.md)** - Voice channel management commands (/voice-channel)
- **[commands/help/CLAUDE.md](commands/help/CLAUDE.md)** - Help system commands (/help, /help-create, /help-edit, /help-delete, /help-list)

### API Reference
- **SBA Database API OpenAPI Spec**: https://sba.manticorum.com/api/openapi.json
  - Use `WebFetch` to retrieve current endpoint definitions
  - ~80+ endpoints covering players, teams, stats, transactions, draft, etc.
  - Always fetch fresh rather than relying on cached/outdated specs

## 🏗️ Project Overview

**Discord Bot v2.0** is a comprehensive Discord bot for managing a Strat-o-Matic Baseball Association (SBA) fantasy league. Built with discord.py and modern async Python patterns.

### Core Architecture
- **Command System**: Modular, package-based command organization
- **Logging**: Structured logging with Discord context integration
- **Services**: Clean service layer for API interactions
- **Caching**: Optional Redis caching for performance
- **Error Handling**: Comprehensive error handling with user-friendly messages

## 🚀 Development Commands

### Local Development
```bash
# Start the bot
python bot.py

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest --tb=short -q

# Run specific test files
python -m pytest tests/test_commands_transactions.py -v --tb=short
python -m pytest tests/test_services.py -v
```

### Testing Commands
```bash
# Full test suite (should pass all tests)
python -m pytest --tb=short -q

# Test specific components
python -m pytest tests/test_utils_decorators.py -v
python -m pytest tests/test_models.py -v
python -m pytest tests/test_api_client_with_aioresponses.py -v
```

## 📁 Project Structure

```
discord-app-v2/
├── CLAUDE.md files (check these first!)
├── bot.py                          # Main bot entry point
├── commands/                       # Discord slash commands
│   ├── CLAUDE.md                  # 🔍 Command architecture guide
│   ├── league/                    # League-wide commands
│   │   ├── CLAUDE.md              # 🔍 League command reference
│   │   └── info.py                # /league command
│   ├── players/                   # Player information commands
│   │   ├── CLAUDE.md              # 🔍 Player command reference
│   │   └── info.py                # /player command
│   ├── teams/                     # Team information commands
│   │   ├── CLAUDE.md              # 🔍 Team command reference
│   │   ├── info.py                # /team, /teams commands
│   │   └── roster.py              # /roster command
│   ├── transactions/              # Transaction management
│   │   ├── CLAUDE.md              # 🔍 Transaction command reference
│   │   └── management.py          # /mymoves, /legal commands
│   └── voice/                     # Voice channel management
│       ├── CLAUDE.md              # 🔍 Voice command reference
│       ├── channels.py            # /voice-channel commands
│       ├── cleanup_service.py     # Automatic channel cleanup
│       └── tracker.py             # JSON-based channel tracking
├── services/                      # API service layer
│   └── CLAUDE.md                  # 🔍 Service layer documentation
├── models/                        # Pydantic data models
│   └── CLAUDE.md                  # 🔍 Model patterns and validation
├── tasks/                         # Background automated tasks
│   └── CLAUDE.md                  # 🔍 Task system documentation
├── utils/                         # Utility functions and helpers
│   ├── CLAUDE.md                  # 🔍 Utils documentation
│   ├── logging.py                 # Structured logging system
│   ├── decorators.py              # Command and caching decorators
│   └── cache.py                   # Redis caching system
├── views/                         # Discord UI components
│   └── CLAUDE.md                  # 🔍 UI components and embeds
├── tests/                         # Test suite
│   └── CLAUDE.md                  # 🔍 Testing guide and patterns
└── logs/                          # Log files
```

## 🔧 Key Development Patterns

### 1. Command Implementation with @logged_command Decorator

**✅ Recommended Pattern:**
```python
from utils.decorators import logged_command
from utils.logging import get_contextual_logger

class YourCommandCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.YourCommandCog')  # Required

    @discord.app_commands.command(name="example")
    @logged_command("/example")  # Add this decorator
    async def your_command(self, interaction, param: str):
        # Only business logic - no try/catch/finally boilerplate needed
        # Decorator handles all logging, timing, and error handling
        result = await some_service.get_data(param)
        embed = create_embed(result)
        await interaction.followup.send(embed=embed)
```

**Benefits:**
- Eliminates ~15-20 lines of boilerplate per command
- Automatic trace ID generation and request correlation
- Consistent error handling and operation timing
- Standardized logging patterns

### 2. Service Layer with Caching

**✅ Service Implementation:**
```python
from utils.decorators import cached_api_call
from services.base_service import BaseService

class PlayerService(BaseService[Player]):
    @cached_api_call(ttl=600)  # Cache for 10 minutes
    async def get_players_by_team(self, team_id: int, season: int) -> List[Player]:
        return await self.get_all_items(params=[('team_id', team_id), ('season', season)])
```

### 3. Structured Logging

**✅ Logging Pattern:**
```python
from utils.logging import get_contextual_logger, set_discord_context

# In command handlers
set_discord_context(interaction=interaction, command="/example", param_value=param)
trace_id = self.logger.start_operation("operation_name")

self.logger.info("Operation started", context_param=value)
# ... business logic ...
self.logger.end_operation(trace_id, "completed")
```

### 4. Autocomplete Pattern (REQUIRED)

**✅ Recommended Pattern - Standalone Function:**
```python
# Define autocomplete function OUTSIDE the class
async def entity_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    """Autocomplete for entity names."""
    try:
        # Get matching entities from service
        entities = await service.get_entities_for_autocomplete(current, limit=25)

        return [
            app_commands.Choice(name=entity.display_name, value=entity.name)
            for entity in entities
        ]
    except Exception:
        # Return empty list on error to avoid breaking autocomplete
        return []


class YourCommandCog(commands.Cog):
    @app_commands.command(name="command")
    @app_commands.autocomplete(parameter_name=entity_name_autocomplete)  # Reference function
    @logged_command("/command")
    async def your_command(self, interaction, parameter_name: str):
        # ... command implementation ...
```

**Benefits:**
- Consistent pattern across all commands
- Reusable autocomplete functions
- Cleaner code organization
- Easier testing and maintenance

**❌ Avoid Method-Based Autocomplete:**
```python
# DON'T USE THIS PATTERN
class YourCommandCog(commands.Cog):
    @app_commands.command(name="command")
    async def your_command(self, interaction, parameter: str):
        pass

    @your_command.autocomplete('parameter')  # Avoid this pattern
    async def parameter_autocomplete(self, interaction, current: str):
        pass
```

**Reference Implementation:**
- See `commands/players/info.py:20-67` for the canonical example
- See `commands/help/main.py:30-48` for help topic autocomplete

### 5. Discord Embed Usage - Emoji Best Practices

**CRITICAL:** Avoid double emoji in Discord embeds by following these guidelines:

#### Template Method Emoji Prefixes

The following `EmbedTemplate` methods **automatically add emoji prefixes** to titles:

- `EmbedTemplate.success()` → adds `✅` prefix
- `EmbedTemplate.error()` → adds `❌` prefix
- `EmbedTemplate.warning()` → adds `⚠️` prefix
- `EmbedTemplate.info()` → adds `ℹ️` prefix
- `EmbedTemplate.loading()` → adds `⏳` prefix

#### ✅ CORRECT Usage Patterns

```python
# ✅ CORRECT - Using template method without emoji in title
embed = EmbedTemplate.success(
    title="Operation Completed",
    description="Your action was successful"
)
# Result: "✅ Operation Completed"

# ✅ CORRECT - Custom emoji with create_base_embed
embed = EmbedTemplate.create_base_embed(
    title="🎉 Special Success Message",
    description="Using a different emoji",
    color=EmbedColors.SUCCESS
)
# Result: "🎉 Special Success Message"
```

#### ❌ WRONG Usage Patterns

```python
# ❌ WRONG - Double emoji
embed = EmbedTemplate.success(
    title="✅ Operation Completed",  # Will result in "✅ ✅ Operation Completed"
    description="Your action was successful"
)

# ❌ WRONG - Emoji in title with auto-prefix method
embed = EmbedTemplate.error(
    title="❌ Failed",  # Will result in "❌ ❌ Failed"
    description="Something went wrong"
)
```

#### Rules for Embed Creation

1. **When using template methods** (`success()`, `error()`, `warning()`, `info()`, `loading()`):
   - ❌ **DON'T** include emojis in the title parameter
   - ✅ **DO** use plain text titles
   - The template method will add the appropriate emoji automatically

2. **When you want custom emojis**:
   - ✅ **DO** use `EmbedTemplate.create_base_embed()`
   - ✅ **DO** specify the appropriate color parameter
   - You have full control over the title including custom emojis

3. **Code review checklist**:
   - Check all `EmbedTemplate.success/error/warning/info/loading()` calls
   - Verify titles don't contain emojis
   - Ensure `create_base_embed()` is used for custom emoji titles

#### Common Mistakes to Avoid

```python
# ❌ BAD: Double warning emoji
embed = EmbedTemplate.warning(
    title="⚠️ Delete Command"  # Results in "⚠️ ⚠️ Delete Command"
)

# ✅ GOOD: Template adds emoji automatically
embed = EmbedTemplate.warning(
    title="Delete Command"  # Results in "⚠️ Delete Command"
)

# ❌ BAD: Different emoji with auto-prefix method
embed = EmbedTemplate.error(
    title="🗑️ Deleted"  # Results in "❌ 🗑️ Deleted"
)

# ✅ GOOD: Use create_base_embed for custom emoji
embed = EmbedTemplate.create_base_embed(
    title="🗑️ Deleted",  # Results in "🗑️ Deleted"
    color=EmbedColors.ERROR
)
```

**Reference Files**:
- `views/embeds.py` - EmbedTemplate implementation
- `DOUBLE_EMOJI_AUDIT.md` - Complete audit of double emoji issues (January 2025)
- Fixed files: `tasks/custom_command_cleanup.py`, `views/help_commands.py`, `views/custom_commands.py`

## 🎯 Development Guidelines

### Git Workflow - CRITICAL

**🚨 NEVER make code changes directly to the `main` branch. Always work in a separate branch.**

#### Branch Workflow
1. **Create a new branch** for all code changes:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/bug-description
   ```

2. **Make your changes** in the feature branch

3. **Commit your changes** following the commit message format:
   ```bash
   git commit -m "CLAUDE: Your commit message

   🤖 Generated with [Claude Code](https://claude.com/claude-code)

   Co-Authored-By: Claude <noreply@anthropic.com>"
   ```

4. **Push your branch** to the remote repository:
   ```bash
   git push -u origin feature/your-feature-name
   ```

5. **Create a Pull Request** to merge into `main` when ready

**Why This Matters:**
- Protects the `main` branch from broken code
- Allows code review before merging
- Makes it easy to revert changes if needed
- Enables parallel development on multiple features
- Maintains a clean, stable main branch

**Exception:** Only emergency hotfixes or critical production issues may warrant direct commits to `main`, and only with explicit authorization.

### Before Making Changes
1. **Check CLAUDE.md files** in current and parent directories
2. **Review existing patterns** in similar commands/services
3. **Follow the @logged_command decorator pattern** for new commands
4. **Use structured logging** with contextual information
5. **Add appropriate caching** for expensive operations

### Command Development
- **Always use `@logged_command` decorator** for Discord commands
- **Ensure command class has `self.logger`** in `__init__`
- **Focus on business logic** - decorator handles boilerplate
- **Use EmbedTemplate** for consistent Discord embed styling
- **CRITICAL: Follow emoji best practices** - see "Discord Embed Usage - Emoji Best Practices" section
- **Follow error handling patterns** from existing commands
- **Use standalone functions for autocomplete** - see Autocomplete Pattern below

### Testing Requirements
- **All tests should pass**: Run `python -m pytest --tb=short -q`
- **Use aioresponses** for HTTP client testing (see `tests/CLAUDE.md`)
- **Provide complete model data** that satisfies Pydantic validation
- **Follow testing patterns** documented in `tests/CLAUDE.md`

### Model Requirements
- **Database entities require `id` fields** since they're always fetched from database
- **Use explicit None checks** (`if obj is None:`) for better type safety
- **Required fields eliminate Optional type issues**

## 🔍 Key Files to Reference

### When Adding New Commands
1. **Read `commands/CLAUDE.md`** - Command architecture and patterns
2. **Check existing command files** in relevant package (league/players/teams/transactions)
3. **Review package-specific CLAUDE.md** files for implementation details
4. **Follow `@logged_command` decorator patterns**

### When Working with Services
1. **Check `services/` directory** for existing service patterns
2. **Use `BaseService[T]` inheritance** for consistent API interactions
3. **Add caching decorators** for expensive operations
4. **Follow error handling patterns**

### When Writing Tests
1. **Read `tests/CLAUDE.md`** thoroughly - contains crucial testing patterns
2. **Use aioresponses** for HTTP mocking, not manual AsyncMock
3. **Provide complete model data** with helper functions
4. **Test both success and error scenarios**

### When Working with Utilities
1. **Read `utils/CLAUDE.md`** for logging, caching, and decorators
2. **Use structured logging** with `get_contextual_logger()`
3. **Leverage caching decorators** for performance optimization
4. **Follow established patterns** for Discord context setting

## 🚨 Critical Reminders

### Decorator Migration (Completed)
- **All commands use `@logged_command`** - eliminates boilerplate logging code
- **Standardizes error handling** and operation timing across all commands
- **See existing commands** for implementation patterns

### Model Breaking Changes (Implemented)
- **Database entities require `id` fields** - test cases must provide ID values
- **Use `Player(id=123, ...)` and `Team(id=456, ...)` in tests**
- **No more Optional[int] warnings** - improved PyLance type safety

### Redis Caching (Available)
- **Optional caching infrastructure** - graceful fallback without Redis
- **Use `@cached_api_call()` and `@cached_single_item()` decorators**
- **Zero breaking changes** - all existing functionality preserved

### Code Quality Requirements
- **Pylance warnings are disabled for optional values** - always either return a value or raise an Exception
- **Use "Raise or Return" pattern** - do not return optional values unless specifically required
- **Favor Python dataclasses** over standard classes unless there's a technical limitation

## 🧪 Testing Strategy

### Current Test Coverage
- **44 comprehensive tests** covering core functionality
- **HTTP testing with aioresponses** - reliable async HTTP mocking
- **Service layer testing** - complete model validation
- **All tests should pass** - run `python -m pytest --tb=short -q`

### Test Files by Component
- `test_utils_decorators.py` - Decorator functionality
- `test_models.py` - Pydantic model validation
- `test_services.py` - Service layer operations (25 tests)
- `test_api_client_with_aioresponses.py` - HTTP client operations (19 tests)

## 🔧 Environment Variables

### Required
```bash
BOT_TOKEN=your_discord_bot_token
API_TOKEN=your_database_api_token
DB_URL=http://localhost:8000
GUILD_ID=your_discord_server_id
LOG_LEVEL=INFO
```

### Optional (Caching)
```bash
REDIS_URL=redis://localhost:6379    # Empty disables caching
REDIS_CACHE_TTL=300                 # Default TTL in seconds
```

## 🐳 Docker Hub Configuration

### 🚨 CRITICAL: Correct Repository Name

**Discord Bot v2.0 Docker Hub Repository:**
```
manticorum67/major-domo-discordapp
```

**⚠️ IMPORTANT: There is NO DASH between "discord" and "app"**

### Common Mistakes to Avoid
```bash
# ❌ WRONG - Has extra dash
manticorum67/major-domo-discord-app

# ❌ WRONG - Uses v2 suffix
manticorum67/major-domo-discordapp-v2

# ❌ WRONG - Different project name pattern
manticorum67/major-domo-discord-app-v2

# ✅ CORRECT - Use this exact name
manticorum67/major-domo-discordapp
```

### Build and Push Commands
```bash
# Build with version tag
docker build -t manticorum67/major-domo-discordapp:X.Y.Z .

# Tag as latest
docker tag manticorum67/major-domo-discordapp:X.Y.Z manticorum67/major-domo-discordapp:latest

# Push both tags
docker push manticorum67/major-domo-discordapp:X.Y.Z
docker push manticorum67/major-domo-discordapp:latest
```

### Version Tagging Convention
- **Version tags**: `manticorum67/major-domo-discordapp:2.24.0`
- **Latest tag**: `manticorum67/major-domo-discordapp:latest`
- **Development tag**: `manticorum67/major-domo-discordapp:dev`

### Related Repositories
| Component | Docker Hub Repository |
|-----------|----------------------|
| Discord Bot v2 | `manticorum67/major-domo-discordapp` |
| Database API | `manticorum67/major-domo-database` |

## 📊 Monitoring and Logs

### Log Files
- **`logs/discord_bot_v2.log`** - Human-readable logs
- **`logs/discord_bot_v2.json`** - Structured JSON logs for analysis

### Log Analysis Examples
```bash
# Find all errors
jq 'select(.level == "ERROR")' logs/discord_bot_v2.json

# Track specific request
jq 'select(.trace_id == "abc12345")' logs/discord_bot_v2.json

# Find slow operations
jq 'select(.extra.duration_ms > 5000)' logs/discord_bot_v2.json
```

## 🎯 Future AI Agent Instructions

### Always Start Here
1. **Read this CLAUDE.md file completely**
2. **Check CLAUDE.md files** in current and parent directories
3. **Review relevant package-specific documentation**
4. **Understand existing patterns** before implementing changes

### Documentation Priority
1. **Current directory CLAUDE.md** - Most specific context
2. **Parent directory CLAUDE.md** - Package-level context
3. **Root project CLAUDE.md** - Overall project guidance
4. **Component-specific CLAUDE.md** files - Detailed implementation guides

### Implementation Checklist
- [ ] Reviewed relevant CLAUDE.md files
- [ ] Followed existing command/service patterns
- [ ] Used `@logged_command` decorator for new commands
- [ ] Added structured logging with context
- [ ] Included appropriate error handling
- [ ] **Followed Discord Embed emoji best practices** (no double emojis)
- [ ] Added tests following established patterns
- [ ] Verified all tests pass

## 🔄 Recent Major Enhancements

### Multi-GM Trade Access (December 2025)
**Enables any GM participating in a trade to access and modify the trade builder**

**Problem Solved**: Previously, only the user who initiated a trade (`/trade initiate`) could add players, view, or modify the trade. Other GMs whose teams were part of the trade had no access.

**Solution**: Implemented dual-key indexing pattern with a secondary index mapping team IDs to trade keys.

**Key Changes**:
- **`services/trade_builder.py`**:
  - Added `_team_to_trade_key` secondary index
  - Added `get_trade_builder_by_team(team_id)` function
  - Added `clear_trade_builder_by_team(team_id)` function
  - Updated `add_team()`, `remove_team()`, `clear_trade_builder()` to maintain index
- **`commands/transactions/trade.py`**:
  - Refactored 5 commands to use team-based lookups: `add-team`, `add-player`, `supplementary`, `view`, `clear`
  - Any GM whose team is in the trade can now use these commands

**Docker Images**:
- `manticorum67/major-domo-discordapp:2.22.0`
- `manticorum67/major-domo-discordapp:dev`

**Tests**: 9 new tests added to `tests/test_services_trade_builder.py`

### Custom Help Commands System (January 2025)
**Comprehensive admin-managed help system for league documentation**:

- **Full CRUD Operations**: Create, read, update, and delete help topics via Discord commands
- **Permission System**: Administrators and "Help Editor" role can manage content
- **Rich Features**:
  - Markdown-formatted content (up to 4000 characters)
  - Category organization (rules, guides, resources, info, faq)
  - View tracking and analytics
  - Soft delete with restore capability
  - Full audit trail (creator, editor, timestamps)
  - Autocomplete for topic discovery
  - Paginated list views
- **Interactive UI**: Modals for creation/editing, confirmation dialogs for deletion
- **Replaces**: Planned `/links` command with more flexible solution
- **Commands**: `/help`, `/help-create`, `/help-edit`, `/help-delete`, `/help-list`
- **Documentation**: See `commands/help/CLAUDE.md` for complete reference
- **Database**: Requires `help_commands` table migration (see `.claude/DATABASE_MIGRATION_HELP_COMMANDS.md`)

**Key Components**:
- **Model**: `models/help_command.py` - Pydantic models with validation
- **Service**: `services/help_commands_service.py` - Business logic and API integration
- **Views**: `views/help_commands.py` - Interactive modals and list views
- **Commands**: `commands/help/main.py` - Command handlers with @logged_command decorator

### Enhanced Transaction Builder with sWAR Tracking
**Major upgrade to transaction management system**:

- **Comprehensive sWAR Calculations**: Now tracks Major League and Minor League sWAR projections
- **Pre-existing Transaction Support**: Accounts for scheduled moves when validating new transactions
- **Organizational Team Matching**: Proper handling of PORMIL, PORIL transactions for POR teams
- **Enhanced User Interface**: Transaction embeds show complete context including pre-existing moves

### Team Model Organizational Affiliates
**New Team model methods for organizational relationships**:

- **`team.major_league_affiliate()`**: Get ML team via API
- **`team.minor_league_affiliate()`**: Get MiL team via API
- **`team.injured_list_affiliate()`**: Get IL team via API
- **`team.is_same_organization()`**: Check if teams belong to same organization

### Key Benefits for Users
- **Complete Transaction Context**: Users see impact of both current and scheduled moves
- **Accurate sWAR Projections**: Better strategic decision-making with team strength data
- **Improved Validation**: Proper roster type detection for all transaction types
- **Enhanced UX**: Clean, informative displays with contextual information

### Technical Improvements
- **API Efficiency**: Cached data to avoid repeated calls
- **Backwards Compatibility**: All existing functionality preserved
- **Error Handling**: Graceful fallbacks and proper exception handling
- **Testing**: Comprehensive test coverage for new functionality

### Critical Bug Fixes (January 2025)

#### 1. Trade Channel Creation Permission Error (Fixed)
**Issue**: Trade channels failed to create with Discord API error 50013 "Missing Permissions"

**Root Cause**: The bot was attempting to grant itself `manage_channels` and `manage_permissions` in channel-specific permission overwrites during channel creation. Discord prohibits bots from self-granting elevated permissions in channel overwrites as a security measure.

**Fix**: Removed `manage_channels` and `manage_permissions` from bot's channel-specific overwrites in `commands/transactions/trade_channels.py:74-77`. The bot's server-level permissions are sufficient for all channel management operations.

**Impact**: Trade discussion channels now create successfully. All channel management features (create, delete, permission updates) work correctly with server-level permissions only.

**Files Changed**:
- `commands/transactions/trade_channels.py` - Simplified bot permission overwrites
- `commands/transactions/CLAUDE.md` - Documented permission requirements and fix

#### 2. TeamService Method Name AttributeError (Fixed)
**Issue**: Bot crashed with `AttributeError: 'TeamService' object has no attribute 'get_team_by_id'` when adding players to trades

**Root Cause**: Code was calling non-existent method `team_service.get_team_by_id()`. The correct method name is `team_service.get_team()`.

**Fix**: Updated method call in `services/trade_builder.py:201` and all corresponding test mocks in `tests/test_services_trade_builder.py`.

**Impact**: Adding players to trades now works correctly. All 18 trade builder tests pass.

**Files Changed**:
- `services/trade_builder.py` - Changed `get_team_by_id()` to `get_team()`
- `tests/test_services_trade_builder.py` - Updated all test mocks
- `services/CLAUDE.md` - Documented correct TeamService method names

**Prevention**: Added clear documentation in `services/CLAUDE.md` showing correct TeamService method signatures to prevent future confusion.

### Critical Bug Fixes (October 2025)

#### 1. Custom Command Execution Validation Error (Fixed)
**Issue**: Custom commands failed to execute with Pydantic validation error: `creator_id Field required`

**Root Cause**: The API's `/custom_commands/by_name/{name}/execute` endpoint returns command data **without** the `creator_id` field, but the `CustomCommand` model required this field. This caused validation to fail when parsing the execute endpoint response.

**Fix**: Made `creator_id` field optional in the `CustomCommand` model:
```python
# Before
creator_id: int = Field(..., description="ID of the creator")

# After
creator_id: Optional[int] = Field(None, description="ID of the creator (may be missing from execute endpoint)")
```

**Impact**: Custom commands (`/cc`) now execute successfully. The execute endpoint only needs to return command content, not creator information. Permission checks (edit/delete) use different endpoints that include full creator data.

**Files Changed**:
- `models/custom_command.py:30` - Made `creator_id` optional
- `models/CLAUDE.md` - Documented Custom Command Model changes

**Why This Design Works**:
- Execute endpoint: Returns minimal data (name, content, use_count) for fast execution
- Get/Create/Update/Delete endpoints: Return complete data including creator information
- Permission checks always use endpoints with full creator data

#### 2. Admin Commands Type Safety Issues (Fixed)
**Issue**: Multiple Pylance type errors in `commands/admin/management.py` causing potential runtime errors

**Root Causes**:
1. Accessing `guild_permissions` on `User` type (only exists on `Member`)
2. Passing `Optional[int]` to `discord.Object(id=...)` which requires `int`
3. Calling `purge()` on channel types that don't support it
4. Calling `delete()` on potentially `None` message
5. Passing `None` to `content` parameter that requires `str`

**Fixes**:
1. Added `isinstance(interaction.user, discord.Member)` check before accessing `guild_permissions`
2. Added explicit None check: `if not interaction.guild_id: raise ValueError(...)`
3. Added channel type validation: `isinstance(interaction.channel, (discord.TextChannel, discord.Thread, ...))`
4. Added None check: `if message:` before calling `message.delete()`
5. Changed from conditional variable to explicit if/else branches for `content` parameter
6. Removed unused imports (`Optional`, `Union`)

**Impact**: All admin commands now have proper type safety. No more Pylance warnings, and code is more robust against edge cases.

**Files Changed**:
- `commands/admin/management.py:26-42` - Guild permissions and member checks
- `commands/admin/management.py:246-253` - Guild ID validation
- `commands/admin/management.py:361-366` - Channel type validation
- `commands/admin/management.py:389-393` - Message None check
- `commands/admin/management.py:436-439` - Content parameter handling
- `commands/admin/management.py:6` - Removed unused imports

**Prevention**: Follow Discord.py type patterns - always check for `Member` vs `User`, validate optional IDs before use, and verify channel types support the operations you're calling.

---

**Last Updated:** December 2025
**Maintenance:** Keep this file synchronized with CLAUDE.md files when making significant architectural changes
**Next Review:** When major new features or patterns are added

This CLAUDE.md file serves as the central reference point for AI development agents. Always consult the referenced CLAUDE.md files for the most detailed and current information about specific components and implementation patterns.