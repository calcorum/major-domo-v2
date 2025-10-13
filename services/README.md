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
    async def get_team(team_id: int) -> Optional[Team]  # ✅ Correct method name
    async def get_teams_by_owner(owner_id: int, season: Optional[int], roster_type: Optional[str]) -> List[Team]
    async def get_team_by_abbrev(abbrev: str, season: Optional[int]) -> Optional[Team]
    async def get_teams_by_season(season: int) -> List[Team]
    async def get_team_roster(team_id: int, roster_type: str = 'current') -> Optional[Dict[str, Any]]
```

**⚠️ Common Mistake (Fixed January 2025)**:
- **Incorrect**: `team_service.get_team_by_id(team_id)` ❌ (method does not exist)
- **Correct**: `team_service.get_team(team_id)` ✅

This naming inconsistency was fixed in `services/trade_builder.py` line 201 and corresponding test mocks.

### Transaction Services
- **`transaction_service.py`** - Player transaction operations (trades, waivers, etc.)
- **`transaction_builder.py`** - Complex transaction building and validation

### Custom Features
- **`custom_commands_service.py`** - User-created custom Discord commands

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