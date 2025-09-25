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
    async def delete(self, object_id: int) -> bool
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

---

**Next Steps for AI Agents:**
1. Review existing service implementations for patterns
2. Check the corresponding model definitions in `/models`
3. Understand the caching decorators in `/utils/decorators.py`
4. Follow the error handling patterns established in `BaseService`
5. Use structured logging with contextual information