# Injury Commands

**Command Group:** `/injury`
**Permission Required:** SBA Players role (for set-new and clear)
**Subcommands:** roll, set-new, clear

## Overview

The injury command family provides comprehensive player injury management for the SBA league. Team managers can roll for injuries using official Strat-o-Matic injury tables, record confirmed injuries, and clear injuries when players return.

## Commands

### `/injury roll`

Roll for injury based on a player's injury rating using 3d6 dice and official injury tables.

**Usage:**
```
/injury roll <player_name>
```

**Parameters:**
- `player_name` (required, autocomplete): Name of the player - uses smart autocomplete prioritizing your team's players

**Injury Rating Format:**
The player's `injury_rating` field contains both the games played and rating in format `#p##`:
- **Format**: `1p70`, `4p50`, `2p65`, etc.
- **First character**: Games played in current series (1-6)
- **Remaining characters**: Injury rating (p70, p65, p60, p50, p40, p30, p20)

**Examples:**
- `1p70` = 1 game played, p70 rating
- `4p50` = 4 games played, p50 rating
- `2p65` = 2 games played, p65 rating

**Dice Roll:**
- Rolls 3d6 (3-18 range)
- Automatically extracts games played and rating from player's injury_rating field
- Looks up result in official Strat-o-Matic injury tables
- Returns injury duration based on rating and games played

**Possible Results:**
- **OK**: No injury
- **REM**: Remainder of game (batters) or Fatigued (pitchers)
- **Number**: Games player will miss (1-24 games)

**Example:**
```
/injury roll Mike Trout
```

**Response Fields:**
- **Roll**: Total rolled and individual dice (e.g., "15 (3d6: 5 + 5 + 5)")
- **Player**: Player name and position
- **Injury Rating**: Full rating with parsed details (e.g., "4p50 (p50, 4 games)")
- **Result**: Injury outcome (OK, REM, or number of games)
- **Team**: Player's current team

**Response Colors:**
- **Green**: OK (no injury)
- **Gold**: REM (remainder of game/fatigued)
- **Orange**: Number of games (injury occurred)

**Error Handling:**
If a player's `injury_rating` is not in the correct format, an error message will be displayed:
```
Invalid Injury Rating Format
{Player} has an invalid injury rating: `{rating}`

Expected format: #p## (e.g., 1p70, 4p50)
```

---

### `/injury set-new`

Record a new injury for a player on your team.

**Usage:**
```
/injury set-new <player_name> <this_week> <this_game> <injury_games>
```

**Parameters:**
- `player_name` (required): Name of the player to injure
- `this_week` (required): Current week number
- `this_game` (required): Current game number (1-4)
- `injury_games` (required): Total number of games player will be out

**Validation:**
- Player must exist in current season
- Player cannot already have an active injury
- Game number must be between 1 and 4
- Injury duration must be at least 1 game

**Automatic Calculations:**
The command automatically calculates:
1. Injury start date (adjusts for game 4 edge case)
2. Return date based on injury duration
3. Week rollover when games exceed 4 per week

**Example:**
```
/injury set-new Mike Trout 5 2 4
```
This records an injury occurring in week 5, game 2, with player out for 4 games (returns week 6, game 2).

**Response:**
- Confirmation embed with injury details
- Player's name, position, and team
- Total games missed
- Calculated return date

---

### `/injury clear`

Clear a player's active injury and mark them as eligible to play.

**Usage:**
```
/injury clear <player_name>
```

**Parameters:**
- `player_name` (required, autocomplete): Name of the player whose injury to clear - uses smart autocomplete prioritizing your team's players

**Validation:**
- Player must exist in current season
- Player must have an active injury

**User Flow:**
1. Command issued with player name
2. **Confirmation embed displayed** showing:
   - Player name and position
   - Team name and abbreviation
   - Expected return date
   - Total games missed
   - Team thumbnail (if available)
3. User prompted: "Is {Player Name} cleared to return?"
4. Two buttons presented:
   - **"Clear Injury"** → Proceeds with clearing the injury
   - **"Cancel"** → Cancels the operation
5. After confirmation, injury is cleared and success message displayed

**Example:**
```
/injury clear Mike Trout
```

**Confirmation Embed:**
- Title: Player name
- Description: "Is **{Player Name}** cleared to return?"
- Fields: Player info, team, expected return date, games missed
- Buttons: "Clear Injury" / "Cancel"
- Timeout: 3 minutes

**Success Response (after confirmation):**
- Confirmation that injury was cleared
- Shows previous return date
- Shows total games that were missed
- Player's team information

**Responders:**
- Command issuer
- Team GM(s) - can also confirm/cancel on behalf of team

---

## Date Format

All injury dates use the format `w##g#`:
- `w##` = Week number (zero-padded to 2 digits)
- `g#` = Game number (1-4)

**Examples:**
- `w05g2` = Week 5, Game 2
- `w12g4` = Week 12, Game 4
- `w01g1` = Week 1, Game 1

## Injury Calculation Logic

### Basic Calculation

For an injury of N games starting at week W, game G:

1. **Calculate weeks and remaining games:**
   ```
   out_weeks = floor(N / 4)
   out_games = N % 4
   ```

2. **Calculate return date:**
   ```
   return_week = W + out_weeks
   return_game = G + 1 + out_games
   ```

3. **Handle week rollover:**
   ```
   if return_game > 4:
       return_week += 1
       return_game -= 4
   ```

### Special Cases

#### Game 4 Edge Case
If injury occurs during game 4, the start date is adjusted:
```
start_week = W + 1
start_game = 1
```

#### Examples

**Example 1: Simple injury (same week)**
- Current: Week 5, Game 1
- Injury: 2 games
- Return: Week 5, Game 4

**Example 2: Week rollover**
- Current: Week 5, Game 3
- Injury: 3 games
- Return: Week 6, Game 3

**Example 3: Multi-week injury**
- Current: Week 5, Game 2
- Injury: 8 games
- Return: Week 7, Game 3

**Example 4: Game 4 start**
- Current: Week 5, Game 4
- Injury: 2 games
- Start: Week 6, Game 1
- Return: Week 6, Game 3

## Database Schema

### Injury Model

```python
class Injury(SBABaseModel):
    id: int                 # Injury ID
    season: int            # Season number
    player_id: int         # Player ID
    total_games: int       # Total games player will be out
    start_week: int        # Week injury started
    start_game: int        # Game number injury started (1-4)
    end_week: int          # Week player returns
    end_game: int          # Game number player returns (1-4)
    is_active: bool        # Whether injury is currently active
```

### API Integration

The commands interact with the following API endpoints:

- `GET /api/v3/injuries` - Query injuries with filters
- `POST /api/v3/injuries` - Create new injury record
- `PATCH /api/v3/injuries/{id}` - Update injury (clear active status)
- `PATCH /api/v3/players/{id}` - Update player's il_return field

## Service Layer

### InjuryService

**Location:** `services/injury_service.py`

**Key Methods:**
- `get_active_injury(player_id, season)` - Get active injury for player
- `get_injuries_by_player(player_id, season, active_only)` - Get all injuries for player
- `get_injuries_by_team(team_id, season, active_only)` - Get team injuries
- `create_injury(...)` - Create new injury record
- `clear_injury(injury_id)` - Deactivate injury

## Permissions

### Required Roles

**For `/injury check`:**
- No role required (available to all users)

**For `/injury set-new` and `/injury clear`:**
- **SBA Players** role required
- Configured via `SBA_PLAYERS_ROLE_NAME` environment variable

### Permission Checks

The commands use `has_player_role()` method to verify user has appropriate role:

```python
def has_player_role(self, interaction: discord.Interaction) -> bool:
    """Check if user has the SBA Players role."""
    player_role = discord.utils.get(
        interaction.guild.roles,
        name=get_config().sba_players_role_name
    )
    return player_role in interaction.user.roles if player_role else False
```

## Error Handling

### Common Errors

**Player Not Found:**
```
❌ Player Not Found
I did not find anybody named **{player_name}**.
```

**Already Injured:**
```
❌ Already Injured
Hm. It looks like {player_name} is already hurt.
```

**Not Injured:**
```
❌ No Active Injury
{player_name} isn't injured.
```

**Invalid Input:**
```
❌ Invalid Input
Game number must be between 1 and 4.
```

**Permission Denied:**
```
❌ Permission Denied
This command requires the **SBA Players** role.
```

## Logging

All injury commands use the `@logged_command` decorator for automatic logging:

```python
@app_commands.command(name="check")
@logged_command("/injury check")
async def injury_check(self, interaction, player_name: str):
    # Command implementation
```

**Log Context:**
- Command name
- User ID and username
- Player name
- Season
- Injury details (duration, dates)
- Success/failure status

**Example Log:**
```json
{
  "level": "INFO",
  "command": "/injury set-new",
  "user_id": "123456789",
  "player_name": "Mike Trout",
  "season": 12,
  "injury_games": 4,
  "return_date": "w06g2",
  "message": "Injury set for Mike Trout"
}
```

## Testing

### Test Coverage

**Location:** `tests/test_services_injury.py`

**Test Categories:**
1. **Model Tests** (5 tests) - Injury model creation and properties
2. **Service Tests** (8 tests) - InjuryService CRUD operations with API mocking
3. **Roll Logic Tests** (8 tests) - Injury rating parsing, table lookup, and dice roll logic
4. **Calculation Tests** (5 tests) - Date calculation logic for injury duration

**Total:** 26 comprehensive tests

**Running Tests:**
```bash
# Run all injury tests
python -m pytest tests/test_services_injury.py -v

# Run specific test class
python -m pytest tests/test_services_injury.py::TestInjuryService -v
python -m pytest tests/test_services_injury.py::TestInjuryRollLogic -v

# Run with coverage
python -m pytest tests/test_services_injury.py --cov=services.injury_service --cov=commands.injuries
```

## Injury Roll Tables

### Table Structure

The injury tables are based on official Strat-o-Matic rules with the following structure:

**Ratings:** p70, p65, p60, p50, p40, p30, p20 (higher is better)
**Games Played:** 1-6 games in current series
**Roll:** 3d6 (results from 3-18)

### Rating Availability by Games Played

Not all ratings are available for all games played combinations:

- **1 game**: All ratings (p70-p20)
- **2 games**: All ratings (p70-p20)
- **3 games**: p65-p20 (p70 exempt)
- **4 games**: p60-p20 (p70, p65 exempt)
- **5 games**: p60-p20 (p70, p65 exempt)
- **6 games**: p40-p20 (p70, p65, p60, p50 exempt)

When a rating/games combination has no table, the result is automatically "OK" (no injury).

### Example Table (p65, 1 game):

| Roll | Result |
|------|--------|
| 3    | 2      |
| 4    | 2      |
| 5    | OK     |
| 6    | REM    |
| 7    | 1      |
| ...  | ...    |
| 18   | 12     |

## UI/UX Design

### Embed Colors

- **Roll (OK):** Green - No injury
- **Roll (REM):** Gold - Remainder of game/Fatigued
- **Roll (Injury):** Orange - Number of games
- **Set New:** Success (green) - `EmbedTemplate.success()`
- **Clear:** Success (green) - `EmbedTemplate.success()`
- **Errors:** Error (red) - `EmbedTemplate.error()`

### Response Format

All successful responses use Discord embeds with:
- Clear title indicating action/status
- Well-organized field layout
- Team information when applicable
- Consistent formatting for dates

## Integration with Player Model

The Player model includes injury-related fields:

```python
class Player(SBABaseModel):
    # ... other fields ...
    pitcher_injury: Optional[int]      # Pitcher injury rating
    injury_rating: Optional[str]       # General injury rating
    il_return: Optional[str]           # Injured list return date (w##g#)
```

When an injury is set or cleared, the player's `il_return` field is automatically updated via PlayerService.

## Future Enhancements

Possible improvements for future versions:

1. **Injury History** - View player's injury history for a season
2. **Team Injury Report** - List all injuries for a team
3. **Injury Notifications** - Automatic notifications when players return from injury
4. **Injury Statistics** - Track injury trends and statistics
5. **Injury Chart Image** - Display the official injury chart as an embed image

## Migration from Legacy

### Legacy Commands

The legacy injury commands were located in:
- `discord-app/cogs/players.py` - `set_injury_slash()` and `clear_injury_slash()`
- `discord-app/cogs/players.py` - `injury_roll_slash()` with manual rating/games input

### Key Improvements

1. **Cleaner Command Structure:** Using GroupCog for organized subcommands (`/injury roll`, `/injury set-new`, `/injury clear`)
2. **Simplified Interface:** Single parameter for injury roll - games played automatically extracted from player data
3. **Smart Injury Ratings:** Automatically reads and parses player's injury rating from database
4. **Player Autocomplete:** Modern autocomplete with team prioritization for better UX
5. **Better Error Handling:** User-friendly error messages via EmbedTemplate with format validation
6. **Improved Logging:** Automatic logging via @logged_command decorator
7. **Service Layer:** Separated business logic from command handlers
8. **Type Safety:** Full type hints and Pydantic models
9. **Testability:** Comprehensive unit tests (26 tests) with mocked API calls
10. **Modern UI:** Consistent embed-based responses with color coding
11. **Official Tables:** Complete Strat-o-Matic injury tables built into the command

### Migration Details

**Old:** `/injuryroll <rating> <games>` - Manual rating and games selection
**New:** `/injury roll <player>` - Single parameter, automatic rating and games extraction from player's `injury_rating` field

**Old:** `/setinjury <player> <week> <game> <duration>`
**New:** `/injury set-new <player> <week> <game> <duration>` - Same functionality, better naming

**Old:** `/clearinjury <player>`
**New:** `/injury clear <player>` - Same functionality, better naming

### Database Field Update

The `injury_rating` field format has changed to include games played:
- **Old Format**: `p65`, `p70`, etc. (rating only)
- **New Format**: `1p70`, `4p50`, `2p65`, etc. (games + rating)

Players must have their `injury_rating` field updated to the new format for the `/injury roll` command to work.

---

**Last Updated:** January 2025
**Version:** 2.0
**Status:** Active
