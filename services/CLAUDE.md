# Services Directory

The services directory contains the service layer for Discord Bot v2.0, providing clean abstractions for API interactions and business logic. All services inherit from `BaseService` and follow consistent patterns for data operations.

## Architecture

### Service Layer Pattern
Services act as the interface between Discord commands and the external API, providing:
- **Data validation** using Pydantic models
- **Error handling** with consistent exception patterns
- **Caching support** via Redis decorators
- **Type safety** with generic TypeVar support
- **Logging integration** with structured logging

### Base Service (`base_service.py`)
The foundation for all services, providing:
- **Generic CRUD operations** (Create, Read, Update, Delete)
- **API client management** with connection pooling
- **Response format handling** for API responses
- **Cache key generation** and management
- **Error handling** with APIException wrapping

```python
class BaseService(Generic[T]):
    def __init__(self, model_class: Type[T], endpoint: str)
    async def get_by_id(self, object_id: int) -> Optional[T]
    async def get_all(self, params: Optional[List[tuple]] = None) -> Tuple[List[T], int]
    async def create(self, model_data: Dict[str, Any]) -> Optional[T]
    async def update(self, object_id: int, model_data: Dict[str, Any]) -> Optional[T]
    async def patch(self, object_id: int, model_data: Dict[str, Any], use_query_params: bool = False) -> Optional[T]
    async def delete(self, object_id: int) -> bool
```

**PATCH vs PUT Operations:**
- `update()` uses HTTP PUT for full resource replacement
- `patch()` uses HTTP PATCH for partial updates
- `use_query_params=True` sends data as URL query parameters instead of JSON body

**When to use `use_query_params=True`:**
Some API endpoints (notably the player PATCH endpoint) expect data as query parameters instead of JSON body. Example:

```python
# Standard PATCH with JSON body
await base_service.patch(object_id, {"field": "value"})
# → PATCH /api/v3/endpoint/{id} with JSON: {"field": "value"}

# PATCH with query parameters
await base_service.patch(object_id, {"field": "value"}, use_query_params=True)
# → PATCH /api/v3/endpoint/{id}?field=value
```

## 🚨 Service Layer Abstraction - CRITICAL BEST PRACTICE

**NEVER bypass the service layer by directly accessing the API client.** This is a critical architectural principle that must be followed in all code.

### ❌ Anti-Pattern: Direct Client Access

```python
# BAD: Bypassing service layer
async def my_task():
    client = await some_service.get_client()
    await client.patch(f'endpoint/{id}', data={'field': 'value'})  # ❌ WRONG
```

**Problems:**
1. **Breaks Abstraction** - Services exist to abstract API details
2. **Harder to Test** - Can't easily mock individual operations
3. **Duplicated Logic** - Same API calls repeated in multiple places
4. **Maintenance Nightmare** - API changes require updates everywhere
5. **Missing Validation** - Services provide business logic validation
6. **No Caching** - Bypass caching decorators on service methods

### ✅ Correct Pattern: Use Service Methods

```python
# GOOD: Using service layer
async def my_task():
    updated = await some_service.update_item(id, {'field': 'value'})  # ✅ CORRECT
```

### When Service Methods Don't Exist

**If a service method doesn't exist for your use case:**

1. **Add the method to the service** (preferred approach)
2. **Document it properly** with docstrings
3. **Use existing BaseService methods** when possible

#### Example: Adding Missing Service Method

```python
# In league_service.py
class LeagueService(BaseService[Current]):
    async def update_current_state(
        self,
        week: Optional[int] = None,
        freeze: Optional[bool] = None
    ) -> Optional[Current]:
        """
        Update current league state (week and/or freeze status).

        Args:
            week: New week number (None to leave unchanged)
            freeze: New freeze status (None to leave unchanged)

        Returns:
            Updated Current object or None if update failed
        """
        update_data = {}
        if week is not None:
            update_data['week'] = week
        if freeze is not None:
            update_data['freeze'] = freeze

        # Use BaseService patch method
        return await self.patch(current_id=1, model_data=update_data)
```

Then use it in tasks/commands:

```python
# In task code
updated_current = await league_service.update_current_state(
    week=new_week,
    freeze=True
)
```

### Real-World Example: Transaction Freeze Task

**❌ BEFORE (Bad - Direct Client Access):**
```python
# Anti-pattern: bypassing services
client = await league_service.get_client()
await client.patch(f'current/{current_id}', data={'week': new_week, 'freeze': True})

client = await transaction_service.get_client()
response = await client.get('transactions', params=[...])
moves_data = response.get('transactions', [])
transactions = [Transaction.from_api_data(move) for move in moves_data]

await client.patch(f'transactions/{move.id}', data={'frozen': False})
```

**✅ AFTER (Good - Using Service Methods):**
```python
# Proper pattern: using service layer
updated_current = await league_service.update_current_state(
    week=new_week,
    freeze=True
)

transactions = await transaction_service.get_frozen_transactions_by_week(
    season=current.season,
    week_start=current.week,
    week_end=current.week + 1
)

await transaction_service.unfreeze_transaction(move.id)
```

### Benefits of Service Layer Approach

1. **Testability** - Mock `league_service.update_current_state()` easily
2. **Consistency** - All API calls go through services
3. **Maintainability** - API changes only need service updates
4. **Validation** - Services add business logic validation
5. **Reusability** - Other code can use the same service methods
6. **Abstraction** - Tasks don't need to know about API structure
7. **Caching** - Service methods can be cached with decorators
8. **Error Handling** - Consistent exception handling

### Code Review Checklist

When reviewing code, **reject any PR that:**
- ✘ Calls `await service.get_client()` outside of service layer
- ✘ Makes direct API calls in commands, tasks, or views
- ✘ Parses API responses outside of services
- ✘ Uses `client.get()`, `client.post()`, `client.patch()` outside services

**Accept only code that:**
- ✓ Uses service methods for ALL API interactions
- ✓ Adds new service methods when needed
- ✓ Properly documents new service methods
- ✓ Uses BaseService inherited methods when appropriate

## Service Files

### Core Entity Services
- **`player_service.py`** - Player data operations and search functionality
- **`team_service.py`** - Team information and roster management
- **`league_service.py`** - League-wide data and current season info
- **`standings_service.py`** - Team standings and division rankings
- **`schedule_service.py`** - Game scheduling and results
- **`stats_service.py`** - Player statistics (batting, pitching, fielding)
- **`roster_service.py`** - Team roster composition and position assignments

#### TeamService Key Methods
The `TeamService` provides team data operations with specific method names:

```python
class TeamService(BaseService[Team]):
    async def get_team(team_id: int) -> Optional[Team]  # ✅ Correct method name - CACHED
    async def get_team_by_owner(owner_id: int, season: Optional[int]) -> Optional[Team]  # NEW - CACHED
    async def get_teams_by_owner(owner_id: int, season: Optional[int], roster_type: Optional[str]) -> List[Team]
    async def get_team_by_abbrev(abbrev: str, season: Optional[int]) -> Optional[Team]
    async def get_teams_by_season(season: int) -> List[Team]
    async def get_team_roster(team_id: int, roster_type: str = 'current') -> Optional[Dict[str, Any]]
```

**⚠️ Common Mistake (Fixed January 2025)**:
- **Incorrect**: `team_service.get_team_by_id(team_id)` ❌ (method does not exist)
- **Correct**: `team_service.get_team(team_id)` ✅

This naming inconsistency was fixed in `services/trade_builder.py` line 201 and corresponding test mocks.

#### TeamService Caching Strategy (October 2025)

**Cached Methods** (30-minute TTL with `@cached_single_item`):
- `get_team(team_id)` - Returns `Optional[Team]`
- `get_team_by_owner(owner_id, season)` - Returns `Optional[Team]` (NEW convenience method for GM validation)

**Rationale:** GM assignments and team details rarely change during a season. These methods are called on every command for GM validation, making them ideal candidates for caching. The 30-minute TTL balances freshness with performance.

**Cache Keys:**
- `team:id:{team_id}`
- `team:owner:{season}:{owner_id}`

**Performance Impact:** Reduces API calls by ~80% during active bot usage, with cache hits taking <1ms vs 50-200ms for API calls.

**Not Cached:**
- `get_teams_by_owner(...)` with `roster_type` parameter - Returns `List[Team]`, more flexible query
- `get_teams_by_season(season)` - Team list may change during operations (keepers, expansions)
- `get_team_by_abbrev(abbrev, season)` - Less frequently used, not worth caching overhead

**Future Cache Invalidation:**
When implementing team ownership transfers or team modifications, use:
```python
from utils.decorators import cache_invalidate

@cache_invalidate("team:owner:*", "team:id:*")
async def transfer_ownership(old_owner_id: int, new_owner_id: int):
    # ... ownership change logic ...
    # Caches automatically cleared by decorator
```

### Transaction Services
- **`transaction_service.py`** - Player transaction operations (trades, waivers, etc.)
- **`transaction_builder.py`** - Complex transaction building and validation

#### TransactionService Key Methods (October 2025 Update)
```python
class TransactionService(BaseService[Transaction]):
    # Transaction retrieval methods
    async def get_team_transactions(...) -> List[Transaction]
    async def get_pending_transactions(...) -> List[Transaction]
    async def get_frozen_transactions(...) -> List[Transaction]
    async def get_processed_transactions(...) -> List[Transaction]

    # NEW: Real-time transaction creation (for /ilmove)
    async def create_transaction_batch(transactions: List[Transaction]) -> List[Transaction]:
        """
        Create multiple transactions via API POST (for immediate execution).

        This is used for real-time transactions (like IL moves) that need to be
        posted to the database immediately rather than scheduled for later processing.

        Args:
            transactions: List of Transaction objects to create

        Returns:
            List of created Transaction objects with API-assigned IDs

        Raises:
            APIException: If transaction creation fails
        """
```

**Usage Example:**
```python
# Create transactions for immediate execution
created_transactions = await transaction_service.create_transaction_batch(transactions)

# Each transaction now has a database-assigned ID
for txn in created_transactions:
    print(f"Created transaction {txn.id}: {txn.move_description}")
```

#### PlayerService Key Methods (October 2025 Update)
```python
class PlayerService(BaseService[Player]):
    # Player search and retrieval methods
    async def get_player(...) -> Optional[Player]
    async def search_players(...) -> List[Player]
    async def get_players_by_team(...) -> List[Player]

    # NEW: Team assignment updates (for /ilmove)
    async def update_player_team(player_id: int, new_team_id: int) -> Optional[Player]:
        """
        Update a player's team assignment (for real-time IL moves).

        This is used for immediate roster changes where the player needs to show
        up on their new team right away, rather than waiting for transaction processing.

        Args:
            player_id: Player ID to update
            new_team_id: New team ID to assign

        Returns:
            Updated player instance or None

        Raises:
            APIException: If player update fails
        """
```

**Usage Example:**
```python
# Update player team assignment immediately
updated_player = await player_service.update_player_team(
    player_id=player.id,
    new_team_id=new_team.id
)

# Player now shows on new team in all queries
print(f"{updated_player.name} now on team {updated_player.team_id}")
```

### Game Submission Services (NEW - January 2025)
- **`game_service.py`** - Game CRUD operations and scorecard submission support
- **`play_service.py`** - Play-by-play data management for game submissions
- **`decision_service.py`** - Pitching decision operations for game results
- **`sheets_service.py`** - Google Sheets integration for scorecard reading

#### GameService Key Methods
```python
class GameService(BaseService[Game]):
    async def find_duplicate_game(season: int, week: int, game_num: int,
                                   away_team_id: int, home_team_id: int) -> Optional[Game]
    async def find_scheduled_game(season: int, week: int,
                                   away_team_id: int, home_team_id: int) -> Optional[Game]
    async def wipe_game_data(game_id: int) -> bool  # Transaction rollback support
    async def update_game_result(game_id: int, away_score: int, home_score: int,
                                 away_manager_id: int, home_manager_id: int,
                                 game_num: int, scorecard_url: str) -> Game
```

#### PlayService Key Methods
```python
class PlayService:
    async def create_plays_batch(plays: List[Dict[str, Any]]) -> bool
    async def delete_plays_for_game(game_id: int) -> bool  # Transaction rollback
    async def get_top_plays_by_wpa(game_id: int, limit: int = 3) -> List[Play]
```

#### DecisionService Key Methods
```python
class DecisionService:
    async def create_decisions_batch(decisions: List[Dict[str, Any]]) -> bool
    async def delete_decisions_for_game(game_id: int) -> bool  # Transaction rollback
    def find_winning_losing_pitchers(decisions_data: List[Dict[str, Any]])
        -> Tuple[Optional[int], Optional[int], Optional[int], List[int], List[int]]
```

#### SheetsService Key Methods
```python
class SheetsService:
    async def open_scorecard(sheet_url: str) -> pygsheets.Spreadsheet
    async def read_setup_data(scorecard: pygsheets.Spreadsheet) -> Dict[str, Any]
    async def read_playtable_data(scorecard: pygsheets.Spreadsheet) -> List[Dict[str, Any]]
    async def read_pitching_decisions(scorecard: pygsheets.Spreadsheet) -> List[Dict[str, Any]]
    async def read_box_score(scorecard: pygsheets.Spreadsheet) -> Dict[str, List[int]]
```

**Transaction Rollback Pattern:**
The game submission services implement a 3-state transaction rollback pattern:
1. **PLAYS_POSTED**: Plays submitted → Rollback: Delete plays
2. **GAME_PATCHED**: Game updated → Rollback: Wipe game + Delete plays
3. **COMPLETE**: All data committed → No rollback needed

**Usage Example:**
```python
# Create plays (state: PLAYS_POSTED)
await play_service.create_plays_batch(plays_data)
rollback_state = "PLAYS_POSTED"

try:
    # Update game (state: GAME_PATCHED)
    await game_service.update_game_result(game_id, ...)
    rollback_state = "GAME_PATCHED"

    # Create decisions (state: COMPLETE)
    await decision_service.create_decisions_batch(decisions_data)
    rollback_state = "COMPLETE"
except APIException as e:
    # Rollback based on current state
    if rollback_state == "GAME_PATCHED":
        await game_service.wipe_game_data(game_id)
        await play_service.delete_plays_for_game(game_id)
    elif rollback_state == "PLAYS_POSTED":
        await play_service.delete_plays_for_game(game_id)
```

### Custom Features
- **`custom_commands_service.py`** - User-created custom Discord commands
- **`help_commands_service.py`** - Admin-managed help system and documentation

## Caching Integration

Services support optional Redis caching via decorators:

```python
from utils.decorators import cached_api_call, cached_single_item

class PlayerService(BaseService[Player]):
    @cached_api_call(ttl=600)  # Cache for 10 minutes
    async def get_players_by_team(self, team_id: int, season: int) -> List[Player]:
        return await self.get_all_items(params=[('team_id', team_id), ('season', season)])

    @cached_single_item(ttl=300)  # Cache for 5 minutes
    async def get_player_by_name(self, name: str) -> Optional[Player]:
        players = await self.get_by_field('name', name)
        return players[0] if players else None
```

### Caching Features
- **Graceful degradation** - Works without Redis
- **Automatic key generation** based on method parameters
- **TTL support** with configurable expiration
- **Cache invalidation** patterns for data updates

## Error Handling

All services use consistent error handling:

```python
try:
    result = await some_service.get_data()
    return result
except APIException as e:
    logger.error("API error occurred", error=e)
    raise  # Re-raise for command handlers
except Exception as e:
    logger.error("Unexpected error", error=e)
    raise APIException(f"Service operation failed: {e}")
```

### Exception Types
- **`APIException`** - API communication errors
- **`ValueError`** - Data validation errors
- **`ConnectionError`** - Network connectivity issues

## Usage Patterns

### Service Initialization
Services are typically initialized once and reused:

```python
# In services/__init__.py
from .player_service import PlayerService
from models.player import Player

player_service = PlayerService(Player, 'players')
```

### Command Integration
Services integrate with Discord commands via the `@logged_command` decorator:

```python
@discord.app_commands.command(name="player")
@logged_command("/player")
async def player_info(self, interaction: discord.Interaction, name: str):
    player = await player_service.get_player_by_name(name)
    if not player:
        await interaction.followup.send("Player not found")
        return

    embed = create_player_embed(player)
    await interaction.followup.send(embed=embed)
```

## API Response Format

Services handle the standard API response format:
```json
{
  "count": 150,
  "players": [
    {"id": 1, "name": "Player Name", ...},
    {"id": 2, "name": "Another Player", ...}
  ]
}
```

The `BaseService._extract_items_and_count_from_response()` method automatically parses this format and returns typed model instances.

## Development Guidelines

### Adding New Services
1. **Inherit from BaseService** with appropriate model type
2. **Define specific business methods** beyond CRUD operations
3. **Add caching decorators** for expensive operations
4. **Include comprehensive logging** with structured context
5. **Handle edge cases** and provide meaningful error messages

### Service Method Patterns
- **Query methods** should return `List[T]` or `Optional[T]`
- **Mutation methods** should return the updated model or `None`
- **Search methods** should accept flexible parameters
- **Bulk operations** should handle batching efficiently

### Testing Services
- Use `aioresponses` for HTTP client mocking
- Test both success and error scenarios
- Validate model parsing and transformation
- Verify caching behavior when Redis is available

## Environment Integration

Services respect environment configuration:
- **`DB_URL`** - Database API endpoint
- **`API_TOKEN`** - Authentication token
- **`REDIS_URL`** - Optional caching backend
- **`LOG_LEVEL`** - Logging verbosity

## Performance Considerations

### Optimization Strategies
- **Connection pooling** via global API client
- **Response caching** for frequently accessed data
- **Batch operations** for bulk data processing
- **Lazy loading** for expensive computations

### Monitoring
- All operations are logged with timing information
- Cache hit/miss ratios are tracked
- API error rates are monitored
- Service response times are measured

## Transaction Builder Enhancements (January 2025)

### Enhanced sWAR Calculations
The `TransactionBuilder` now includes comprehensive sWAR (sum of WARA) tracking for both current moves and pre-existing transactions:

```python
class TransactionBuilder:
    async def validate_transaction(self, next_week: Optional[int] = None) -> RosterValidationResult:
        """
        Validate transaction with optional pre-existing transaction analysis.

        Args:
            next_week: Week to check for existing transactions (includes pre-existing analysis)

        Returns:
            RosterValidationResult with projected roster counts and sWAR values
        """
```

### Pre-existing Transaction Support
When `next_week` is provided, the transaction builder:
- **Fetches existing transactions** for the specified week via API
- **Calculates roster impact** of scheduled moves using organizational team matching
- **Tracks sWAR changes** separately for Major League and Minor League rosters
- **Provides contextual display** for user transparency

#### Usage Examples
```python
# Basic validation (current functionality)
validation = await builder.validate_transaction()

# Enhanced validation with pre-existing transactions
current_week = await league_service.get_current_week()
validation = await builder.validate_transaction(next_week=current_week + 1)

# Access enhanced data
print(f"Projected ML sWAR: {validation.major_league_swar}")
print(f"Pre-existing impact: {validation.pre_existing_transactions_note}")
```

### Enhanced RosterValidationResult
New fields provide complete transaction context:

```python
@dataclass
class RosterValidationResult:
    # Existing fields...
    major_league_swar: float = 0.0
    minor_league_swar: float = 0.0
    pre_existing_ml_swar_change: float = 0.0
    pre_existing_mil_swar_change: float = 0.0
    pre_existing_transaction_count: int = 0

    @property
    def major_league_swar_status(self) -> str:
        """Formatted sWAR display with emoji."""

    @property
    def pre_existing_transactions_note(self) -> str:
        """User-friendly note about pre-existing moves impact."""
```

### Organizational Team Matching
Transaction processing now uses sophisticated team matching:

```python
# Enhanced logic using Team.is_same_organization()
if transaction.oldteam.is_same_organization(self.team):
    # Accurately determine which roster the player is leaving
    from_roster_type = transaction.oldteam.roster_type()

    if from_roster_type == RosterType.MAJOR_LEAGUE:
        # Update ML roster and sWAR
    elif from_roster_type == RosterType.MINOR_LEAGUE:
        # Update MiL roster and sWAR
```

### Key Improvements
- **Accurate Roster Detection**: Uses `Team.roster_type()` instead of assumptions
- **Organization Awareness**: Properly handles PORMIL, PORIL transactions for POR team
- **Separate sWAR Tracking**: ML and MiL sWAR changes tracked independently
- **Performance Optimization**: Pre-existing transactions loaded once and cached
- **User Transparency**: Clear display of how pre-existing moves affect calculations

### Implementation Details
- **Backwards Compatible**: All existing functionality preserved
- **Optional Enhancement**: `next_week` parameter is optional
- **Error Handling**: Graceful fallback if pre-existing transactions cannot be loaded
- **Caching**: Transaction and roster data cached to avoid repeated API calls

---

**Next Steps for AI Agents:**
1. Review existing service implementations for patterns
2. Check the corresponding model definitions in `/models`
3. Understand the caching decorators in `/utils/decorators.py`
4. Follow the error handling patterns established in `BaseService`
5. Use structured logging with contextual information
6. Consider pre-existing transaction impact when building new transaction features