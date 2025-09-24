# Transaction System Design - Discord Bot v2.0

## Analysis of Existing System

Based on the analysis of `../discord-app/cogs/transactions.py`, here are the key components and expected outcomes:

## Core Commands & Expected Outcomes

### 1. `/dropadd` (Primary Transaction Command)
**Purpose**: Handle free agent signings and minor league roster moves
**Expected Outcomes**:
- Create private transaction channel for team
- Guide user through interactive transaction process
- Add/drop players to/from Major League and Minor League rosters
- Validate roster limits and legality
- Schedule transactions for next week execution
- Log all moves for processing during freeze period

**User Flow**:
1. User runs `/dropadd`
2. Bot creates private channel with team permissions
3. Interactive Q&A for Minor League adds/drops
4. Interactive Q&A for Major League adds/drops
5. Roster validation and error checking
6. Transaction confirmation and scheduling

### 2. `/ilmove` (Injury List Management)
**Purpose**: Handle injured list moves during active weeks
**Expected Outcomes**:
- Move players to/from injury list immediately (not next week)
- Validate IL move legality
- Update current roster immediately
- Log IL transaction

### 3. `/rule34` (Draft Lottery)
**Purpose**: 50/50 chance between actual draft board or "rule34" redirect
**Expected Outcomes**:
- 50% chance: Redirect to legitimate draft spreadsheet
- 50% chance: Redirect to rule34 search (league humor)

### 4. `/mymoves` (Transaction Status)
**Purpose**: Show user's pending and scheduled transactions
**Expected Outcomes**:
- Display current week pending moves
- Display next week scheduled moves
- Show frozen/processed moves
- Option to show cancelled moves
- Organized by week and status

### 5. `/legal` (Roster Validation)
**Purpose**: Check roster legality for current and next week
**Expected Outcomes**:
- Validate current week roster
- Validate next week roster (with pending transactions)
- Check roster limits (players, positions, salary, etc.)
- Display violations with clear error messages
- Show WARA totals and roster breakdowns

### 6. `/tomil` (Post-Draft Demotions)
**Purpose**: Move players to minor leagues immediately after draft (Week 0 only)
**Expected Outcomes**:
- Only works during Week 0 (post-draft)
- Immediate player moves to MiL team
- Validate moves are legal
- Punishment mechanism for use outside Week 0 (role removal)

## Background Processing

### 7. Weekly Transaction Processing
**Purpose**: Automated transaction execution during freeze periods
**Expected Outcomes**:
- Freeze period begins: Monday 12:00 AM (development schedule)
- Process all pending transactions with priority system
- Resolve contested transactions (multiple teams want same player)
- Update rosters for new week
- Send transaction logs to transaction-log channel
- Freeze period ends: Saturday 12:00 AM

### 8. Transaction Priority System
**Expected Outcomes**:
- Priority 1: Major League transactions (higher priority)
- Priority 2: Minor League transactions (lower priority)
- Within priority: Worse record gets priority (lower win %)
- Tie-breaker: Random number
- Contested players go to highest priority team

## Data Models Needed

### Transaction Model
```python
@dataclass
class Transaction:
    id: str
    season: int
    week: int
    team_abbrev: str
    move_type: str  # 'dropadd', 'ilmove', 'tomil'
    moves: List[PlayerMove]
    status: str  # 'pending', 'frozen', 'processed', 'cancelled'
    created_at: datetime
    processed_at: Optional[datetime]
```

### PlayerMove Model
```python
@dataclass  
class PlayerMove:
    player_name: str
    player_id: int
    from_team: str
    to_team: str
    move_type: str  # 'add', 'drop', 'il_to_active', 'active_to_il'
```

### TransactionPriority Model (exists)
```python
@dataclass
class TransactionPriority:
    roster_priority: int  # 1=Major, 2=Minor
    win_percentage: float
    random_tiebreaker: int
    move_id: str
    major_league_team_abbrev: str
    contested_players: List[str]
```

## Services Needed

### TransactionService
- CRUD operations for transactions
- Transaction validation logic
- Roster checking and limits
- Player availability checking

### RosterService  
- Get current/next week rosters
- Validate roster legality
- Calculate roster statistics (WARA, positions, etc.)
- Handle roster updates

### TransactionProcessorService
- Weekly freeze period processing
- Priority calculation and resolution
- Contested transaction resolution
- Roster updates and notifications

## Modernization Changes

### From Old System → New System

1. **Commands**: `@commands.command` → `@app_commands.command` with `@logged_command`
2. **Error Handling**: Manual try/catch → Decorator-based standardized handling
3. **Interactive Flow**: Old Question class → Discord Views with buttons/modals
4. **Database**: Direct db_calls → Service layer with proper models
5. **Logging**: Manual logging → Automatic with trace IDs
6. **Validation**: Inline validation → Service-based validation with proper error types
7. **Channel Management**: Manual channel creation → Managed transaction sessions
8. **User Experience**: Text-based Q&A → Rich embeds with interactive components

## Pseudo-Code Design

```python
# Main Transaction Commands
class TransactionCommands(commands.Cog):
    
    @app_commands.command(name="dropadd", description="Make roster moves for next week")
    @logged_command("/dropadd")
    async def dropadd(self, interaction: discord.Interaction):
        # 1. Validate user has team and season is active
        # 2. Create transaction session with private thread/channel
        # 3. Launch TransactionFlow view with buttons for different move types
        # 4. Handle interactive transaction building
        # 5. Validate final transaction
        # 6. Save and schedule transaction
        
    @app_commands.command(name="ilmove", description="Make immediate injury list moves")
    @logged_command("/ilmove")  
    async def ilmove(self, interaction: discord.Interaction):
        # 1. Validate current week (not freeze period)
        # 2. Launch ILMoveView for player selection
        # 3. Process move immediately (no scheduling)
        # 4. Update current roster
        
    @app_commands.command(name="mymoves", description="View your pending transactions")
    @logged_command("/mymoves")
    async def mymoves(self, interaction: discord.Interaction):
        # 1. Get user's team
        # 2. Fetch pending/scheduled transactions
        # 3. Create comprehensive embed with transaction status
        
    @app_commands.command(name="legal", description="Check roster legality")
    @logged_command("/legal")
    async def legal(self, interaction: discord.Interaction, team: Optional[str] = None):
        # 1. Get target team (user's team or specified team)
        # 2. Validate current week roster
        # 3. Validate next week roster (with pending transactions)
        # 4. Create detailed legality report embed

# Interactive Views
class TransactionFlowView(discord.ui.View):
    # Modern Discord UI for transaction building
    # Buttons for: Add Player, Drop Player, Minor League, Done
    # Modal dialogs for player input
    # Real-time validation feedback

class ILMoveView(discord.ui.View):
    # Injury list move interface
    # Player selection dropdown
    # Direction buttons (IL → Active, Active → IL)

# Services
class TransactionService(BaseService[Transaction]):
    async def create_transaction(team_id: int, moves: List[PlayerMove]) -> Transaction
    async def validate_transaction(transaction: Transaction) -> ValidationResult
    async def get_pending_transactions(team_id: int) -> List[Transaction]
    
class RosterService:
    async def get_roster(team_id: int, week: str) -> TeamRoster  # 'current' or 'next'
    async def validate_roster_legality(roster: TeamRoster) -> RosterValidation
    async def apply_transaction(roster: TeamRoster, transaction: Transaction) -> TeamRoster

class TransactionProcessor:
    async def process_weekly_transactions() -> ProcessingResult
    async def calculate_priorities(transactions: List[Transaction]) -> List[TransactionPriority] 
    async def resolve_contests(transactions: List[Transaction]) -> ResolutionResult
```

## Implementation Priority

1. **Phase 1**: Basic commands (`/mymoves`, `/legal`) - Read-only functionality
2. **Phase 2**: Transaction models and services - Data layer
3. **Phase 3**: Interactive transaction creation (`/dropadd`, `/ilmove`) - Core functionality  
4. **Phase 4**: Weekly processing system - Automation
5. **Phase 5**: Advanced features (`/rule34`, `/tomil`) - Nice-to-have

## Key Modernization Benefits

- **User Experience**: Rich Discord UI instead of text-based Q&A
- **Error Handling**: Comprehensive validation with clear error messages
- **Performance**: Service layer with proper caching and concurrent operations
- **Maintainability**: Clean separation of concerns, proper models, standardized patterns
- **Reliability**: Proper transaction handling, rollback capabilities, audit logging
- **Security**: Permission validation, input sanitization, rate limiting