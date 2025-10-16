# Utility Commands

This directory contains general utility commands that enhance the user experience for the SBA Discord bot.

## Commands

### `/weather [team_abbrev]`

**Description**: Roll ballpark weather for gameplay.

**Usage**:
- `/weather` - Roll weather for your team or current channel's team
- `/weather NYY` - Roll weather for a specific team

**Features**:
- **Smart Team Resolution** (3-tier priority):
  1. Explicit team abbreviation parameter
  2. Channel name parsing (e.g., `NYY-Yankee Stadium` → `NYY`)
  3. User's owned team (fallback)

- **Season Display**:
  - Weeks 1-5: 🌼 Spring
  - Weeks 6-14: 🏖️ Summer
  - Weeks 15+: 🍂 Fall

- **Time of Day Logic**:
  - Based on games played this week
  - Division weeks: [1, 3, 6, 14, 16, 18]
  - 0/2 games OR (1 game in division week): 🌙 Night
  - 1/3 games: 🌞 Day
  - 4+ games: 🕸️ Spidey Time (special case)

- **Weather Roll**: Random d20 (1-20) displayed in markdown format

**Embed Layout**:
```
┌─────────────────────────────────┐
│ 🌤️ Weather Check               │
│ [Team Colors]                   │
├─────────────────────────────────┤
│ Season: 🌼 Spring               │
│ Time of Day: 🌙 Night           │
│ Week: 5 | Games Played: 2/4     │
├─────────────────────────────────┤
│ Weather Roll                    │
│ ```md                           │
│ # 14                            │
│ Details: [1d20 (14)]            │
│ ```                             │
├─────────────────────────────────┤
│ [Stadium Image]                 │
└─────────────────────────────────┘
```

**Implementation Details**:
- **File**: `commands/utilities/weather.py`
- **Service Dependencies**:
  - `LeagueService` - Current league state
  - `ScheduleService` - Week schedule and games
  - `TeamService` - Team resolution
- **Logging**: Uses `@logged_command` decorator for automatic logging
- **Error Handling**: Graceful fallback with user-friendly error messages

**Examples**:

1. In a team channel (`#NYY-Yankee-Stadium`):
   ```
   /weather
   → Automatically uses NYY from channel name
   ```

2. Explicit team:
   ```
   /weather BOS
   → Shows weather for Boston team
   ```

3. As team owner:
   ```
   /weather
   → Defaults to your owned team if not in a team channel
   ```

## Architecture

### Command Pattern

All utility commands follow the standard bot architecture:

```python
@discord.app_commands.command(name="command")
@discord.app_commands.describe(param="Description")
@logged_command("/command")
async def command_handler(self, interaction, param: str):
    await interaction.response.defer()
    # Command logic using services
    await interaction.followup.send(embed=embed)
```

### Service Layer

Utility commands leverage the service layer for all data access:
- **No direct database calls** - all data through services
- **Async operations** - proper async/await patterns
- **Error handling** - graceful degradation with user feedback

### Embed Templates

Use `EmbedTemplate` from `views.embeds` for consistent styling:
- Team colors via `team.color`
- Standard error/success/info templates
- Image support (thumbnails and full images)

## Testing

All utility commands have comprehensive test coverage:

**Weather Command** (`tests/test_commands_weather.py` - 20 tests):
- Team resolution (3-tier priority)
- Season calculation
- Time of day logic (including division weeks)
- Weather roll randomization
- Embed formatting and layout
- Error handling scenarios

**Charts Command** (`tests/test_commands_charts.py` - 26 tests):
- Chart service operations (loading, adding, updating, removing)
- Chart display (single and multi-image)
- Autocomplete functionality
- Admin command operations
- Error handling (invalid charts, categories)
- JSON persistence

### `/charts <chart-name>`

**Description**: Display gameplay charts and infographics from the league library.

**Usage**:
- `/charts rest` - Display pitcher rest chart
- `/charts defense` - Display defense chart
- `/charts hit-and-run` - Display hit and run strategy chart

**Features**:
- **Autocomplete**: Smart chart name suggestions with category display
- **Multi-image Support**: Automatically sends multiple images for complex charts
- **Categorized Library**: Charts organized by gameplay, defense, reference, and stats
- **Proper Embeds**: Charts displayed in formatted Discord embeds with descriptions

**Available Charts** (12 total):
- **Gameplay**: rest, sac-bunt, squeeze-bunt, hit-and-run, g1, g2, g3, groundball, fly-b
- **Defense**: rob-hr, defense, block-plate

**Admin Commands**:

Administrators can manage the chart library using these commands:

- `/chart-add <key> <name> <category> <url> [description]` - Add a new chart
- `/chart-remove <key>` - Remove a chart from the library
- `/chart-list [category]` - List all charts (optionally filtered by category)
- `/chart-update <key> [name] [category] [url] [description]` - Update chart properties

**Implementation Details**:
- **Files**:
  - `commands/utilities/charts.py` - Command handlers
  - `services/chart_service.py` - Chart management service
  - `data/charts.json` - Chart definitions storage
- **Service**: `ChartService` - Manages chart loading, saving, and retrieval
- **Categories**: gameplay, defense, reference, stats
- **Logging**: Uses `@logged_command` decorator for automatic logging

**Examples**:

1. Display a single-image chart:
   ```
   /charts defense
   → Shows defense chart embed with image
   ```

2. Display multi-image chart:
   ```
   /charts hit-and-run
   → Shows first image in response, additional images in followups
   ```

3. Admin: Add new chart:
   ```
   /chart-add steal-chart "Steal Chart" gameplay https://example.com/steal.png
   → Adds new chart to the library
   ```

4. Admin: List charts by category:
   ```
   /chart-list gameplay
   → Shows all gameplay charts
   ```

**Data Structure** (`data/charts.json`):
```json
{
  "charts": {
    "chart-key": {
      "name": "Display Name",
      "category": "gameplay",
      "description": "Chart description",
      "urls": ["https://example.com/image.png"]
    }
  },
  "categories": {
    "gameplay": "Gameplay Mechanics",
    "defense": "Defensive Play"
  }
}
```

## Future Commands

Planned utility commands (see PRE_LAUNCH_ROADMAP.md):

- `/links <resource-name>` - Quick access to league resources

## Development Guidelines

When adding new utility commands:

1. **Follow existing patterns** - Use weather.py as a reference
2. **Use @logged_command** - Automatic logging and error handling
3. **Service layer only** - No direct database access
4. **Comprehensive tests** - Cover all edge cases
5. **User-friendly errors** - Clear, actionable error messages
6. **Document in README** - Update this file with new commands

---

**Last Updated**: January 2025
**Maintainer**: Major Domo Bot Development Team
