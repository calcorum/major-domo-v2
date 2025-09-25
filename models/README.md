# Models Directory

The models directory contains Pydantic data models for Discord Bot v2.0, providing type-safe representations of all SBA (Strat-o-Matic Baseball Association) entities. All models inherit from `SBABaseModel` and follow consistent validation patterns.

## Architecture

### Pydantic Foundation
All models use Pydantic v2 with:
- **Automatic validation** of field types and constraints
- **Serialization/deserialization** for API interactions
- **Type safety** with full IDE support
- **JSON schema generation** for documentation
- **Field validation** with custom validators

### Base Model (`base.py`)
The foundation for all SBA models:

```python
class SBABaseModel(BaseModel):
    model_config = {
        "validate_assignment": True,
        "use_enum_values": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {datetime: lambda v: v.isoformat() if v else None}
    }

    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

### Breaking Changes (August 2025)
**Database entities now require `id` fields** since they're always fetched from the database:
- `Player` model: `id: int = Field(..., description="Player ID from database")`
- `Team` model: `id: int = Field(..., description="Team ID from database")`

## Model Categories

### Core Entities

#### League Structure
- **`team.py`** - Team information, abbreviations, divisions
- **`division.py`** - Division structure and organization
- **`manager.py`** - Team managers and ownership
- **`standings.py`** - Team standings and rankings

#### Player Data
- **`player.py`** - Core player information and identifiers
- **`sbaplayer.py`** - Extended SBA-specific player data
- **`batting_stats.py`** - Batting statistics and performance metrics
- **`pitching_stats.py`** - Pitching statistics and performance metrics
- **`roster.py`** - Team roster assignments and positions

#### Game Operations
- **`game.py`** - Individual game results and scheduling
- **`transaction.py`** - Player transactions (trades, waivers, etc.)

#### Draft System
- **`draft_pick.py`** - Individual draft pick information
- **`draft_data.py`** - Draft round and selection data
- **`draft_list.py`** - Complete draft lists and results

#### Custom Features
- **`custom_command.py`** - User-created Discord commands

### Legacy Models
- **`current.py`** - Legacy model definitions for backward compatibility

## Model Validation Patterns

### Required Fields
Models distinguish between required and optional fields:

```python
class Player(SBABaseModel):
    id: int = Field(..., description="Player ID from database")  # Required
    name: str = Field(..., description="Player full name")        # Required
    team_id: Optional[int] = None                                  # Optional
    position: Optional[str] = None                                 # Optional
```

### Field Constraints
Models use Pydantic validators for data integrity:

```python
class BattingStats(SBABaseModel):
    at_bats: int = Field(ge=0, description="At bats (non-negative)")
    hits: int = Field(ge=0, le=Field('at_bats'), description="Hits (cannot exceed at_bats)")

    @field_validator('batting_average')
    @classmethod
    def validate_batting_average(cls, v):
        if v is not None and not 0.0 <= v <= 1.0:
            raise ValueError('Batting average must be between 0.0 and 1.0')
        return v
```

### Custom Validators
Models implement business logic validation:

```python
class Transaction(SBABaseModel):
    transaction_type: str
    player_id: int
    from_team_id: Optional[int] = None
    to_team_id: Optional[int] = None

    @model_validator(mode='after')
    def validate_team_requirements(self):
        if self.transaction_type == 'trade':
            if not self.from_team_id or not self.to_team_id:
                raise ValueError('Trade transactions require both from_team_id and to_team_id')
        return self
```

## API Integration

### Data Transformation
Models provide methods for API interaction:

```python
class Player(SBABaseModel):
    @classmethod
    def from_api_data(cls, data: Dict[str, Any]):
        """Create model instance from API response data."""
        if not data:
            raise ValueError(f"Cannot create {cls.__name__} from empty data")
        return cls(**data)

    def to_dict(self, exclude_none: bool = True) -> Dict[str, Any]:
        """Convert model to dictionary for API requests."""
        return self.model_dump(exclude_none=exclude_none)
```

### Serialization Examples
Models handle various data formats:

```python
# From API JSON
player_data = {"id": 123, "name": "Player Name", "team_id": 5}
player = Player.from_api_data(player_data)

# To API JSON
api_payload = player.to_dict(exclude_none=True)

# JSON string serialization
json_string = player.model_dump_json()

# From JSON string
player_copy = Player.model_validate_json(json_string)
```

## Testing Requirements

### Model Validation Testing
All model tests must provide complete data:

```python
def test_player_creation():
    # ✅ Correct - provides required ID field
    player = Player(
        id=123,
        name="Test Player",
        team_id=5,
        position="1B"
    )
    assert player.id == 123

def test_incomplete_data():
    # ❌ This will fail - missing required ID
    with pytest.raises(ValidationError):
        Player(name="Test Player")  # Missing required id field
```

### Test Data Patterns
Use helper functions for consistent test data:

```python
def create_test_player(**overrides) -> Player:
    """Create a test player with default values."""
    defaults = {
        "id": 123,
        "name": "Test Player",
        "team_id": 1,
        "position": "1B"
    }
    defaults.update(overrides)
    return Player(**defaults)

def test_player_with_stats():
    player = create_test_player(name="Star Player")
    assert player.name == "Star Player"
    assert player.id == 123  # Default from helper
```

## Field Types and Constraints

### Common Field Patterns

#### Identifiers
```python
id: int = Field(..., description="Database primary key")
player_id: int = Field(..., description="Foreign key to player")
team_id: Optional[int] = Field(None, description="Foreign key to team")
```

#### Names and Text
```python
name: str = Field(..., min_length=1, max_length=100)
abbreviation: str = Field(..., min_length=2, max_length=5)
description: Optional[str] = Field(None, max_length=500)
```

#### Statistics
```python
games_played: int = Field(ge=0, description="Games played (non-negative)")
batting_average: Optional[float] = Field(None, ge=0.0, le=1.0)
era: Optional[float] = Field(None, ge=0.0, description="Earned run average")
```

#### Dates and Times
```python
game_date: Optional[datetime] = None
created_at: Optional[datetime] = None
season_year: int = Field(..., ge=1900, le=2100)
```

## Model Relationships

### Foreign Key Patterns
Models reference related entities via ID fields:

```python
class Player(SBABaseModel):
    id: int
    team_id: Optional[int] = None  # References Team.id

class BattingStats(SBABaseModel):
    player_id: int  # References Player.id
    season: int
    team_id: int    # References Team.id
```

### Nested Objects
Some models contain nested structures:

```python
class CustomCommand(SBABaseModel):
    name: str
    creator: Manager  # Nested Manager object
    response: str

class DraftPick(SBABaseModel):
    pick_number: int
    player: Optional[Player] = None  # Optional nested Player
    team: Team                       # Required nested Team
```

## Validation Error Handling

### Common Validation Errors
- **Missing required fields** - Provide all required model fields
- **Type mismatches** - Ensure field types match model definitions
- **Constraint violations** - Check field validators and constraints
- **Invalid nested objects** - Validate all nested model data

### Error Examples
```python
try:
    player = Player(name="Test")  # Missing required id
except ValidationError as e:
    print(e.errors())
    # [{'type': 'missing', 'loc': ('id',), 'msg': 'Field required'}]

try:
    stats = BattingStats(hits=5, at_bats=3)  # hits > at_bats
except ValidationError as e:
    print(e.errors())
    # Constraint violation error
```

## Performance Considerations

### Model Instantiation
- Use `model_validate()` for external data
- Use `model_construct()` for trusted internal data (faster)
- Cache model instances when possible
- Avoid repeated validation of the same data

### Memory Usage
- Models are relatively lightweight
- Nested objects can increase memory footprint
- Consider using `__slots__` for high-volume models
- Use `exclude_none=True` to reduce serialization size

## Development Guidelines

### Adding New Models
1. **Inherit from SBABaseModel** for consistency
2. **Define required fields explicitly** with proper types
3. **Add field descriptions** for documentation
4. **Include validation rules** for data integrity
5. **Provide `from_api_data()` class method** if needed
6. **Write comprehensive tests** covering edge cases

### Model Evolution
- **Backward compatibility** - Add optional fields for new features
- **Migration patterns** - Handle schema changes gracefully
- **Version management** - Document breaking changes
- **API alignment** - Keep models synchronized with API

### Testing Strategy
- **Unit tests** for individual model validation
- **Integration tests** with service layer
- **Edge case testing** for validation rules
- **Performance tests** for large data sets

---

**Next Steps for AI Agents:**
1. Review existing model implementations for patterns
2. Understand the validation rules and field constraints
3. Check the service layer integration in `/services`
4. Follow the testing patterns with complete model data
5. Consider the API data format when creating new models