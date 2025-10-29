# Transaction Commands

This directory contains Discord slash commands for transaction management and roster legality checking.

## Files

### `management.py`
- **Commands**:
  - `/mymoves` - View user's pending and scheduled transactions
  - `/legal` - Check roster legality for current and next week
- **Service Dependencies**:
  - `transaction_service` (multiple methods for transaction retrieval)
  - `roster_service` (roster validation and retrieval)
  - `team_service.get_teams_by_owner()` and `get_team_by_abbrev()`

### `dropadd.py`
- **Commands**:
  - `/dropadd` - Interactive transaction builder for single-team roster moves (scheduled for next week)
  - `/cleartransaction` - Clear current transaction builder
- **Service Dependencies**:
  - `transaction_builder` (transaction creation and validation)
  - `player_service.search_players()` (player autocomplete)
  - `team_service.get_teams_by_owner()`

### `ilmove.py` *(NEW - October 2025)*
- **Commands**:
  - `/ilmove` - Interactive transaction builder for **real-time** roster moves (executed immediately for THIS week)
  - `/clearilmove` - Clear current IL move transaction builder
- **Service Dependencies**:
  - `transaction_builder` (transaction creation and validation - **shared with /dropadd**)
  - `transaction_service.create_transaction_batch()` (POST transactions to database)
  - `player_service.search_players()` (player autocomplete)
  - `player_service.update_player_team()` (immediate team assignment updates)
  - `team_service.get_teams_by_owner()`
- **Key Differences from /dropadd**:
  - **Week**: Creates transactions for THIS week (current) instead of next week
  - **Execution**: Immediately POSTs to database and updates player teams
  - **Use Case**: Real-time IL moves, activations, emergency roster changes
  - **UI**: Same interactive transaction builder with "immediate" submission handler

### `trade.py`
- **Commands**:
  - `/trade initiate` - Start a new multi-team trade
  - `/trade add-team` - Add additional teams to trade (3+ team trades)
  - `/trade add-player` - Add player exchanges between teams
  - `/trade supplementary` - Add internal organizational moves for roster legality
  - `/trade view` - View current trade status
  - `/trade clear` - Clear current trade
- **Service Dependencies**:
  - `trade_builder` (multi-team trade management)
  - `player_service.search_players()` (player autocomplete)
  - `team_service.get_teams_by_owner()`, `get_team_by_abbrev()`, and `get_team()`
- **Channel Management**:
  - Automatically creates private discussion channels for trades
  - Uses `TradeChannelManager` and `TradeChannelTracker` for channel lifecycle
  - Requires bot to have `Manage Channels` permission at server level

## Key Features

### Transaction Status Display (`/mymoves`)
- **User Team Detection**: Automatically finds user's team by Discord ID
- **Transaction Categories**:
  - **Pending**: Transactions awaiting processing
  - **Frozen**: Scheduled transactions ready for processing
  - **Processed**: Recently completed transactions
  - **Cancelled**: Optional display of cancelled transactions
- **Status Visualization**:
  - Status emojis for each transaction type
  - Week numbering and move descriptions
  - Transaction count summaries
- **Smart Limiting**: Shows recent transactions (last 5 pending, 3 frozen/processed, 2 cancelled)

### Roster Legality Checking (`/legal`)
- **Dual Roster Validation**: Checks both current and next week rosters
- **Flexible Team Selection**:
  - Auto-detects user's team
  - Allows manual team specification via abbreviation
- **Comprehensive Validation**:
  - Player count verification (active roster + IL)
  - sWAR calculations and limits
  - League rule compliance checking
  - Error and warning categorization
- **Parallel Processing**: Roster retrieval and validation run concurrently

### Real-Time IL Move System (`/ilmove`) *(NEW - October 2025)*
- **Immediate Execution**: Transactions posted to database and players moved in real-time
- **Current Week Transactions**: All moves effective for THIS week, not next week
- **Shared Transaction Builder**: Uses same builder as `/dropadd` for consistency
- **Interactive UI**: Identical transaction builder interface with validation
- **Maximum Code Reuse**: 95% code shared with `/dropadd`, only submission differs

#### IL Move Command Workflow:
1. **`/ilmove player:"Mike Trout" destination:"Injured List"`** - Add first move
   - Shows transaction builder with current move
   - Validates roster legality in real-time
   - Instructions say "Use `/ilmove` to add more moves"
2. **`/ilmove player:"Shohei Ohtani" destination:"Major League"`** - Add second move
   - Adds to same transaction builder (shared with user)
   - Shows updated roster projections with both moves
   - Validates combined impact on roster limits
3. **Submit via "Submit Transaction" button** - Click to execute
   - Shows CONFIRM modal (type "CONFIRM")
   - **Immediately POSTs** all transactions to database API
   - **Immediately updates** each player's team_id in database
   - Success message shows database transaction IDs
4. **Players show on new teams instantly** - Real-time roster changes

#### IL Move vs Drop/Add Comparison:
| Feature | `/dropadd` | `/ilmove` |
|---------|------------|-----------|
| **Effective Week** | Next week (current + 1) | THIS week (current) |
| **Execution** | Scheduled (background task) | **Immediate** (real-time) |
| **Database POST** | No (builder only) | **Yes** (POSTs to API) |
| **Player Teams** | Unchanged until processing | **Updated immediately** |
| **Use Case** | Future planning | IL moves, activations |
| **Destination Options** | ML, MiL, FA | ML, MiL, **IL** |
| **Builder Shared** | Yes (same TransactionBuilder) | Yes (same TransactionBuilder) |

#### Real-Time Execution Flow:
1. **User submits transaction** → Modal confirmation
2. **Create Transaction objects** → For current week
3. **POST to database API** → `transaction_service.create_transaction_batch()`
4. **Update player teams** → `player_service.update_player_team()` for each player
5. **Success confirmation** → Shows actual database IDs and completed status

**Important Notes**:
- `/ilmove` only works for players **on your roster** (not FA signings)
- Players must exist on ML, MiL, or IL rosters
- Cannot use `/ilmove` to sign free agents (use `/dropadd` for that)
- All roster legality rules still apply (limits, sWAR, etc.)

### Multi-Team Trade System (`/trade`)
- **Trade Initiation**: Start trades between multiple teams using proper Discord command groups
- **Team Management**: Add/remove teams to create complex multi-team trades (2+ teams supported)
- **Player Exchanges**: Add cross-team player movements with source and destination validation
- **Supplementary Moves**: Add internal organizational moves for roster legality compliance
- **Interactive UI**: Rich Discord embeds with validation feedback and trade status
- **Real-time Validation**: Live roster checking across all participating teams
- **Authority Model**: Major League team owners control all players in their organization (ML/MiL/IL)

#### Trade Command Workflow:
1. **`/trade initiate other_team:LAA`** - Start trade between your team and LAA
   - Creates a private discussion channel for the trade
   - Only you see the ephemeral response
2. **`/trade add-team other_team:BOS`** - Add BOS for 3-team trade
   - Updates are posted to the trade channel if executed elsewhere
   - Other team members can see the progress
3. **`/trade add-player player_name:"Mike Trout" destination_team:BOS`** - Exchange players
   - Trade embed updates posted to dedicated channel automatically
   - Keeps all participants informed of changes
4. **`/trade supplementary player_name:"Player X" destination:ml`** - Internal roster moves
   - Channel receives real-time updates
5. **`/trade view`** - Review complete trade with validation
   - Posts current state to trade channel if viewed elsewhere
6. **Submit via interactive UI** - Trade submission through Discord buttons

**Channel Behavior**:
- Commands executed **in** the trade channel: Only ephemeral response to user
- Commands executed **outside** trade channel: Ephemeral response to user + public post to trade channel
- This ensures all participating teams stay informed of trade progress

#### Autocomplete System:
- **Team Initiation**: Only Major League teams (ML team owners initiate trades)
- **Player Destinations**: All roster types (ML/MiL/IL) available for player placement
- **Player Search**: Prioritizes user's team players, supports fuzzy name matching
- **Smart Filtering**: Context-aware suggestions based on user permissions

#### Trade Channel Management (`trade_channels.py`, `trade_channel_tracker.py`):
- **Automatic Channel Creation**: Private discussion channels created when trades are initiated
- **Channel Naming**: Format `trade-{team1}-{team2}-{short_id}` (e.g., `trade-wv-por-681f`)
- **Permission Management**:
  - Channel hidden from @everyone
  - Only participating team roles can view/message
  - Bot has view and send message permissions
  - Created in "Transactions" category (if it exists)
- **Channel Tracking**: JSON-based persistence for cleanup and management
- **Multi-Team Support**: Channels automatically update when teams are added to trades
- **Automatic Cleanup**: Channels deleted when trades are cleared
- **Smart Updates**: When trade commands are executed outside the dedicated trade channel, the trade embed is automatically posted to the trade channel (non-ephemeral) for visibility

**Bot Permission Requirements**:
- Server-level `Manage Channels` - Required to create/delete trade channels
- Server-level `Manage Permissions` - Optional, for enhanced permission management
- **Note**: Bot should NOT have these permissions in channel-specific overwrites (causes Discord API error 50013)

**Recent Fix (January 2025)**:
- Removed `manage_channels` and `manage_permissions` from bot's channel-specific overwrites
- Discord prohibits bots from granting themselves elevated permissions in channel overwrites
- Server-level permissions are sufficient for all channel management operations

### Advanced Transaction Features
- **Concurrent Data Fetching**: Multiple transaction types retrieved in parallel
- **Owner-Based Filtering**: Transactions filtered by team ownership
- **Status Tracking**: Real-time transaction status with emoji indicators
- **Team Integration**: Team logos and colors in transaction displays

## Architecture Notes

### Permission Model
- **Team Ownership**: Commands use Discord user ID to determine team ownership
- **Cross-Team Viewing**: `/legal` allows checking other teams' roster status
- **Access Control**: Users can only view their own transactions via `/mymoves`

### Data Processing
- **Async Operations**: Heavy use of `asyncio.gather()` for performance
- **Error Resilience**: Graceful handling of missing roster data
- **Validation Pipeline**: Multi-step roster validation with detailed feedback

### Embed Structure
- **Status-Based Coloring**: Success (green) vs Error (red) color coding
- **Information Hierarchy**: Important information prioritized in embed layout
- **Team Branding**: Consistent use of team thumbnails and colors

## Troubleshooting

### Common Issues

1. **User team not found**:
   - Verify user has team ownership record in database
   - Check Discord user ID mapping to team ownership
   - Ensure current season team assignments are correct

2. **Transaction data missing**:
   - Verify `transaction_service` API endpoints are functional
   - Check transaction status filtering logic
   - Ensure transaction records exist for the team/season

3. **Roster validation failing**:
   - Check `roster_service.get_current_roster()` and `get_next_roster()` responses
   - Verify roster validation rules and logic
   - Ensure player data integrity in roster records

4. **Legal command errors**:
   - Verify team abbreviation exists in database
   - Check roster data availability for both current and next weeks
   - Ensure validation service handles edge cases properly

5. **Trade channel creation fails** *(Fixed January 2025)*:
   - Error: `Discord error: Missing Permissions. Code: 50013`
   - **Root Cause**: Bot was trying to grant itself `manage_channels` and `manage_permissions` in channel-specific permission overwrites
   - **Fix**: Removed elevated permissions from channel overwrites (line 74-77 in `trade_channels.py`)
   - **Verification**: Bot only needs server-level `Manage Channels` permission
   - Channels now create successfully with basic bot permissions (view, send messages, read history)

6. **AttributeError when adding players to trades** *(Fixed January 2025)*:
   - Error: `'TeamService' object has no attribute 'get_team_by_id'`
   - **Root Cause**: Code was calling non-existent method `team_service.get_team_by_id()`
   - **Fix**: Changed to correct method name `team_service.get_team()` (line 201 in `trade_builder.py`)
   - **Location**: `services/trade_builder.py` and test mocks in `tests/test_services_trade_builder.py`
   - All 18 trade builder tests pass after fix

### Service Dependencies
- `services.transaction_service`:
  - `get_pending_transactions()`
  - `get_frozen_transactions()`
  - `get_processed_transactions()`
  - `get_team_transactions()`
  - `create_transaction_batch()` *(NEW - for /ilmove)* - POST transactions to database
- `services.roster_service`:
  - `get_current_roster()`
  - `get_next_roster()`
  - `validate_roster()`
- `services.team_service`:
  - `get_teams_by_owner()`
  - `get_team_by_abbrev()`
  - `get_teams_by_season()` *(trade autocomplete)*
- `services.trade_builder`:
  - `TradeBuilder` class for multi-team transaction management
  - `get_trade_builder()` and `clear_trade_builder()` cache functions
  - `TradeValidationResult` for comprehensive trade validation
- `services.transaction_builder`:
  - `TransactionBuilder` class for single-team roster moves (shared by /dropadd and /ilmove)
  - `get_transaction_builder()` and `clear_transaction_builder()` cache functions
  - `RosterValidationResult` for roster legality validation
- `services.player_service`:
  - `search_players()` for autocomplete functionality
  - `update_player_team()` *(NEW - for /ilmove)* - Update player team assignments

### Core Dependencies
- `utils.decorators.logged_command`
- `views.embeds.EmbedTemplate`
- `views.trade_embed` *(NEW)*: Trade-specific UI components
- `utils.autocomplete` *(ENHANCED)*: Player and team autocomplete functions
- `utils.team_utils` *(NEW)*: Shared team validation utilities
- `constants.SBA_CURRENT_SEASON`

### Testing
Run tests with:
- `python -m pytest tests/test_commands_transactions.py -v` (management commands)
- `python -m pytest tests/test_models_trade.py -v` *(NEW)* (trade models)
- `python -m pytest tests/test_services_trade_builder.py -v` *(NEW)* (trade builder service)

## Database Requirements
- Team ownership mapping (Discord user ID to team)
- Transaction records with status tracking
- Roster data for current and next weeks
- Player assignments and position information
- League rules and validation criteria

## Recent Enhancements

### October 2025
- ✅ **Real-Time IL Move System (`/ilmove`)**: Immediate transaction execution for current week roster changes
  - 95% code reuse with `/dropadd` via shared `TransactionBuilder`
  - Immediate database POST and player team updates
  - Same interactive UI with "immediate" submission handler
  - Supports multiple moves in single transaction
- ✅ **CRITICAL FIX: Scheduled Transaction Database Persistence** (October 2025)
  - **Bug**: `/dropadd` transactions were posted to Discord but NEVER saved to database
  - **Impact**: Week 19 transactions were completely lost - posted to Discord but freeze task found 0 transactions
  - **Root Cause**: `submit_transaction()` only created Transaction objects in memory without database POST
  - **Fix**: Added `create_transaction_batch()` call with `frozen=True` flag in scheduled submission handler
  - **Result**: Transactions now properly persist to database for weekly freeze processing
  - **Files Changed**: `views/transaction_embed.py:243-248`, `tests/test_views_transaction_embed.py:255-285`

### Previous Enhancements
- ✅ **Multi-Team Trade System**: Complete `/trade` command group for 2+ team trades
- ✅ **Enhanced Autocomplete**: Major League team filtering and smart player suggestions
- ✅ **Shared Utilities**: Reusable team validation and autocomplete functions
- ✅ **Comprehensive Testing**: Factory-based tests for trade models and services
- ✅ **Interactive Trade UI**: Rich Discord embeds with real-time validation

## Future Enhancements
- **Trade Submission Integration**: Connect trade system to transaction processing pipeline
- **Advanced transaction analytics and history
- **Trade Approval Workflow**: Multi-party trade approval system
- **Roster optimization suggestions
- **Automated roster validation alerts
- **Trade History Tracking**: Complete audit trail for multi-team trades

## Security Considerations
- User authentication via Discord IDs
- Team ownership verification for sensitive operations
- Transaction privacy (users can only see their own transactions)
- Input validation for team abbreviations and parameters