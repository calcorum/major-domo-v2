# Views Directory

The views directory contains Discord UI components for Discord Bot v2.0, providing consistent visual interfaces and interactive elements. This includes embeds, modals, buttons, select menus, and other Discord UI components.

## Architecture

### Component-Based UI Design
Views in Discord Bot v2.0 follow these principles:
- **Consistent styling** via centralized templates
- **Reusable components** for common UI patterns
- **Error handling** with graceful degradation
- **User interaction tracking** and validation
- **Accessibility** with proper labeling and feedback

### Base Components
All view components inherit from Discord.py base classes with enhanced functionality:
- **BaseView** - Enhanced discord.ui.View with logging and user validation
- **BaseModal** - Enhanced discord.ui.Modal with error handling
- **EmbedTemplate** - Centralized embed creation with consistent styling

## View Components

### Base View System (`base.py`)

#### BaseView Class
Foundation for all interactive views:

```python
class BaseView(discord.ui.View):
    def __init__(self, timeout=180.0, user_id=None):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.logger = get_contextual_logger(f'{__name__}.BaseView')

    async def interaction_check(self, interaction) -> bool:
        """Validate user permissions for interaction."""

    async def on_timeout(self) -> None:
        """Handle view timeout gracefully."""

    async def on_error(self, interaction, error, item) -> None:
        """Handle view errors with user feedback."""
```

#### ConfirmationView Class (Updated January 2025)
Reusable confirmation dialog with Confirm/Cancel buttons (`confirmations.py`):

**Key Features:**
- **User restriction**: Only specified users can interact
- **Customizable labels and styles**: Flexible button appearance
- **Timeout handling**: Automatic cleanup after timeout
- **Three-state result**: `True` (confirmed), `False` (cancelled), `None` (timeout)
- **Clean interface**: Automatically removes buttons after interaction

**Usage Pattern:**
```python
from views.confirmations import ConfirmationView

# Create confirmation dialog
view = ConfirmationView(
    responders=[interaction.user],  # Only this user can interact
    timeout=30.0,                    # 30 second timeout
    confirm_label="Yes, delete",    # Custom label
    cancel_label="No, keep it"      # Custom label
)

# Send confirmation
await interaction.edit_original_response(
    content="⚠️ Are you sure you want to delete this?",
    view=view
)

# Wait for user response
await view.wait()

# Check result
if view.confirmed is True:
    # User clicked Confirm
    await interaction.edit_original_response(
        content="✅ Deleted successfully",
        view=None
    )
elif view.confirmed is False:
    # User clicked Cancel
    await interaction.edit_original_response(
        content="❌ Cancelled",
        view=None
    )
else:
    # Timeout occurred (view.confirmed is None)
    await interaction.edit_original_response(
        content="⏱️ Request timed out",
        view=None
    )
```

**Real-World Example (Scorecard Submission):**
```python
# From commands/league/submit_scorecard.py
if duplicate_game:
    view = ConfirmationView(
        responders=[interaction.user],
        timeout=30.0
    )
    await interaction.edit_original_response(
        content=(
            f"⚠️ This game has already been played!\n"
            f"Would you like me to wipe the old one and re-submit?"
        ),
        view=view
    )
    await view.wait()

    if view.confirmed:
        # User confirmed - proceed with wipe and resubmit
        await wipe_old_data()
    else:
        # User cancelled - exit gracefully
        return
```

**Configuration Options:**
```python
ConfirmationView(
    responders=[user1, user2],              # Multiple users allowed
    timeout=60.0,                           # Custom timeout
    confirm_label="Approve",                # Custom confirm text
    cancel_label="Reject",                  # Custom cancel text
    confirm_style=discord.ButtonStyle.red,  # Custom button style
    cancel_style=discord.ButtonStyle.grey   # Custom button style
)
```

#### PaginationView Class
Multi-page navigation for large datasets:

```python
pages = [embed1, embed2, embed3]
pagination = PaginationView(
    pages=pages,
    user_id=interaction.user.id,
    show_page_numbers=True
)
await interaction.followup.send(embed=pagination.get_current_embed(), view=pagination)
```

### Embed Templates (`embeds.py`)

#### EmbedTemplate Class
Centralized embed creation with consistent styling:

```python
# Success embed
embed = EmbedTemplate.success(
    title="Operation Completed",
    description="Your request was processed successfully."
)

# Error embed
embed = EmbedTemplate.error(
    title="Operation Failed",
    description="Please check your input and try again."
)

# Warning embed
embed = EmbedTemplate.warning(
    title="Careful!",
    description="This action cannot be undone."
)

# Info embed
embed = EmbedTemplate.info(
    title="Information",
    description="Here's what you need to know."
)
```

#### EmbedColors Dataclass
Consistent color scheme across all embeds:

```python
@dataclass(frozen=True)
class EmbedColors:
    PRIMARY: int = 0xa6ce39      # SBA green
    SUCCESS: int = 0x28a745      # Green
    WARNING: int = 0xffc107      # Yellow
    ERROR: int = 0xdc3545        # Red
    INFO: int = 0x17a2b8         # Blue
    SECONDARY: int = 0x6c757d    # Gray
```

### Modal Forms (`modals.py`)

#### BaseModal Class
Foundation for interactive forms:

```python
class BaseModal(discord.ui.Modal):
    def __init__(self, title: str, timeout=300.0):
        super().__init__(title=title, timeout=timeout)
        self.logger = get_contextual_logger(f'{__name__}.BaseModal')
        self.result = None

    async def on_submit(self, interaction):
        """Handle form submission."""

    async def on_error(self, interaction, error):
        """Handle form errors."""
```

#### Usage Pattern
```python
class CustomCommandModal(BaseModal):
    def __init__(self):
        super().__init__(title="Create Custom Command")

    name = discord.ui.TextInput(
        label="Command Name",
        placeholder="Enter command name...",
        required=True,
        max_length=50
    )

    response = discord.ui.TextInput(
        label="Response",
        placeholder="Enter command response...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000
    )

    async def on_submit(self, interaction):
        # Process form data
        command_data = {
            "name": self.name.value,
            "response": self.response.value
        }
        # Handle creation logic
```

### Common UI Elements (`common.py`)

#### Shared Components
- **Loading indicators** for async operations
- **Status messages** for operation feedback
- **Navigation elements** for multi-step processes
- **Validation displays** for form errors

### Specialized Views

#### Custom Commands (`custom_commands.py`)
Views specific to custom command management:
- Command creation forms
- Command listing with actions
- Bulk management interfaces

#### Player Information (`players.py`)
Interactive views for player information display with toggleable statistics:

**PlayerStatsView** - Toggle batting and pitching statistics independently

```python
from views.players import PlayerStatsView

# Create interactive player stats view
view = PlayerStatsView(
    player=player_with_team,
    season=search_season,
    batting_stats=batting_stats,
    pitching_stats=pitching_stats,
    user_id=interaction.user.id
)

# Get initial embed with stats hidden
embed = await view.get_initial_embed()

# Send with interactive view
await interaction.followup.send(embed=embed, view=view)
```

**Key Features:**
- **Basic Info Always Visible**: Name, position, team, sWAR, injury status displayed by default
- **Stats Hidden by Default**: Batting and pitching stats are hidden until user clicks toggle buttons
- **Independent Toggles**: Users can show/hide batting and pitching stats separately
- **Conditional Buttons**: Buttons only appear if corresponding stats are available
- **User Restriction**: Only the user who ran the command can toggle stats
- **Timeout Handling**: View times out after 5 minutes with graceful cleanup
- **Professional UI**: Uses baseball emojis (💥 batting impact, ⚾ pitching) and primary button style
- **Dynamic Updates**: Embed updates in-place when buttons are clicked

**Button Behavior:**
- **Initial State**: "Show Batting Stats" and "Show Pitching Stats"
- **Toggled State**: "Hide Batting Stats" and "Hide Pitching Stats"
- **Visual Feedback**: Button labels change to reflect current state
- **Clean Interface**: Only relevant buttons are shown based on available data

**Implementation Notes:**
- Inherits from `BaseView` for consistent error handling and logging
- Stats formatting matches existing player card design with rounded box code blocks
- Preserves all player card features (images, thumbnails, team colors)
- Comprehensive logging for debugging and monitoring

#### Transaction Management (`transaction_embed.py`) (Updated October 2025)
Views for player transaction interfaces with dual-mode submission support:
- **Transaction builder** with interactive controls
- **Comprehensive validation** and sWAR display
- **Pre-existing transaction** context
- **Dual submission modes**: Scheduled (/dropadd) and Immediate (/ilmove)
- **Dynamic UI instructions**: Context-aware command references

**Key Classes:**
```python
class TransactionEmbedView(discord.ui.View):
    def __init__(
        self,
        builder: TransactionBuilder,
        user_id: int,
        submission_handler: str = "scheduled",  # "scheduled" or "immediate"
        command_name: str = "/dropadd"           # Command for UI instructions
    ):
        """
        Interactive transaction builder view supporting both scheduled and immediate execution.

        Args:
            builder: TransactionBuilder instance
            user_id: Discord user ID (for permission checking)
            submission_handler: "scheduled" for /dropadd, "immediate" for /ilmove
            command_name: Command name shown in "Add More Moves" instructions
        """

async def create_transaction_embed(
    builder: TransactionBuilder,
    command_name: str = "/dropadd"
) -> discord.Embed:
    """
    Create transaction builder embed with context-aware instructions.

    Args:
        builder: TransactionBuilder instance
        command_name: Command name for "Add More Moves" instruction

    Returns:
        Discord embed showing transaction state with appropriate instructions
    """
```

**Submission Handler Behavior:**
- **"scheduled" mode** (/dropadd):
  - Creates transactions for NEXT week
  - No database POST - stays in memory
  - Background task processes later
  - Instructions say "Use `/dropadd` to add more moves"

- **"immediate" mode** (/ilmove):
  - Creates transactions for THIS week
  - Immediately POSTs to database API
  - Immediately updates player teams
  - Instructions say "Use `/ilmove` to add more moves"

**Usage Examples:**
```python
# For /dropadd (scheduled submission)
embed = await create_transaction_embed(builder, command_name="/dropadd")
view = TransactionEmbedView(
    builder,
    user_id,
    submission_handler="scheduled",
    command_name="/dropadd"
)

# For /ilmove (immediate submission)
embed = await create_transaction_embed(builder, command_name="/ilmove")
view = TransactionEmbedView(
    builder,
    user_id,
    submission_handler="immediate",
    command_name="/ilmove"
)
```

**Implementation Notes:**
- **95% code reuse** between /dropadd and /ilmove
- **Same TransactionBuilder** instance shared between both commands
- **Dynamic embed description**: Changes based on command_name
- **Context propagation**: command_name passed through all UI components
- **Backwards compatible**: Default parameters maintain /dropadd behavior

## Styling Guidelines

### Embed Consistency
All embeds should use EmbedTemplate methods:

```python
# ✅ Consistent styling
embed = EmbedTemplate.success("Player Added", "Player successfully added to roster")

# ❌ Inconsistent styling
embed = discord.Embed(title="Player Added", color=0x00ff00)
```

### Color Usage
Use the standard color palette:
- **PRIMARY (SBA Green)** - Default for neutral information
- **SUCCESS (Green)** - Successful operations
- **ERROR (Red)** - Errors and failures
- **WARNING (Yellow)** - Warnings and cautions
- **INFO (Blue)** - General information
- **SECONDARY (Gray)** - Less important information

### User Feedback
Provide clear feedback for all user interactions:

```python
# Loading state
embed = EmbedTemplate.info("Processing", "Please wait while we process your request...")

# Success state
embed = EmbedTemplate.success("Complete", "Your request has been processed successfully.")

# Error state with helpful information
embed = EmbedTemplate.error(
    "Request Failed",
    "The player name was not found. Please check your spelling and try again."
)
```

## Interactive Components

### Button Patterns

#### Action Buttons
```python
@discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
async def confirm_button(self, interaction, button):
    self.increment_interaction_count()
    # Handle confirmation
    await interaction.response.edit_message(content="Confirmed!", view=None)
```

#### Navigation Buttons
```python
@discord.ui.button(emoji="◀️", style=discord.ButtonStyle.primary)
async def previous_page(self, interaction, button):
    self.current_page = max(0, self.current_page - 1)
    await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
```

### Select Menu Patterns

#### Option Selection
```python
@discord.ui.select(placeholder="Choose an option...")
async def select_option(self, interaction, select):
    selected_value = select.values[0]
    # Handle selection
    await interaction.response.send_message(f"You selected: {selected_value}")
```

#### Dynamic Options
```python
class PlayerSelectMenu(discord.ui.Select):
    def __init__(self, players: List[Player]):
        options = [
            discord.SelectOption(
                label=player.name,
                value=str(player.id),
                description=f"{player.position} - {player.team.abbrev}"
            )
            for player in players[:25]  # Discord limit
        ]
        super().__init__(placeholder="Select a player...", options=options)
```

## Error Handling

### View Error Handling
All views implement comprehensive error handling:

```python
async def on_error(self, interaction, error, item):
    """Handle view errors gracefully."""
    self.logger.error("View error", error=error, item_type=type(item).__name__)

    try:
        embed = EmbedTemplate.error(
            "Interaction Error",
            "Something went wrong. Please try again."
        )

        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        self.logger.error("Failed to send error message", error=e)
```

### User Input Validation
Forms validate user input before processing:

```python
async def on_submit(self, interaction):
    # Validate input
    if len(self.name.value) < 2:
        embed = EmbedTemplate.error(
            "Invalid Input",
            "Command name must be at least 2 characters long."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Process valid input
    await self.create_command(interaction)
```

## Accessibility Features

### User-Friendly Labels
- **Clear button labels** with descriptive text
- **Helpful placeholders** in form fields
- **Descriptive error messages** with actionable guidance
- **Consistent emoji usage** for visual recognition

### Permission Validation
Views respect user permissions and provide appropriate feedback:

```python
async def interaction_check(self, interaction) -> bool:
    """Check if user can interact with this view."""
    if self.user_id and interaction.user.id != self.user_id:
        await interaction.response.send_message(
            "❌ You cannot interact with this menu.",
            ephemeral=True
        )
        return False
    return True
```

## Performance Considerations

### View Lifecycle Management
- **Timeout handling** prevents orphaned views
- **Resource cleanup** in view destructors
- **Interaction tracking** for usage analytics
- **Memory management** for large datasets

### Efficient Updates
```python
# ✅ Efficient - Only update what changed
await interaction.response.edit_message(embed=new_embed, view=self)

# ❌ Inefficient - Sends new message
await interaction.response.send_message(embed=new_embed, view=new_view)
```

## Testing Strategies

### View Testing
```python
@pytest.mark.asyncio
async def test_confirmation_view():
    view = ConfirmationView(user_id=123)

    # Mock interaction
    interaction = Mock()
    interaction.user.id = 123

    # Test button click
    await view.confirm_button.callback(interaction)

    assert view.result is True
```

### Modal Testing
```python
@pytest.mark.asyncio
async def test_custom_command_modal():
    modal = CustomCommandModal()

    # Set form values
    modal.name.value = "test"
    modal.response.value = "Test response"

    # Mock interaction
    interaction = Mock()

    # Test form submission
    await modal.on_submit(interaction)

    # Verify processing
    assert modal.result is not None
```

## Development Guidelines

### Creating New Views
1. **Inherit from base classes** for consistency
2. **Use EmbedTemplate** for all embed creation
3. **Implement proper error handling** in all interactions
4. **Add user permission checks** where appropriate
5. **Include comprehensive logging** with context
6. **Follow timeout patterns** to prevent resource leaks

### View Composition
- **Keep views focused** on single responsibilities
- **Use composition** over complex inheritance
- **Separate business logic** from UI logic
- **Make views testable** with dependency injection

### UI Guidelines
- **Follow Discord design patterns** for familiarity
- **Use consistent colors** from EmbedColors
- **Provide clear user feedback** for all actions
- **Handle edge cases** gracefully
- **Consider mobile users** in layout design

## Transaction Embed Enhancements (January 2025)

### Enhanced Display Features
The transaction embed now provides comprehensive information for better decision-making:

#### New Embed Sections
```python
async def create_transaction_embed(builder: TransactionBuilder) -> discord.Embed:
    """
    Creates enhanced transaction embed with sWAR and pre-existing transaction context.
    """
    # Existing sections...

    # NEW: Team Cost (sWAR) Display
    swar_status = f"{validation.major_league_swar_status}\n{validation.minor_league_swar_status}"
    embed.add_field(name="Team sWAR", value=swar_status, inline=False)

    # NEW: Pre-existing Transaction Context (when applicable)
    if validation.pre_existing_transactions_note:
        embed.add_field(
            name="📋 Transaction Context",
            value=validation.pre_existing_transactions_note,
            inline=False
        )
```

### Enhanced Information Display

#### sWAR Tracking
- **Major League sWAR**: Projected team cost for ML roster
- **Minor League sWAR**: Projected team cost for MiL roster
- **Formatted Display**: Uses 📊 emoji with 1 decimal precision

#### Pre-existing Transaction Context
Dynamic context display based on scheduled moves:

```python
# Example displays:
"ℹ️ **Pre-existing Moves**: 3 scheduled moves (+3.7 sWAR)"
"ℹ️ **Pre-existing Moves**: 2 scheduled moves (-2.5 sWAR)"
"ℹ️ **Pre-existing Moves**: 1 scheduled moves (no sWAR impact)"
# No display when no pre-existing moves (clean interface)
```

### Complete Embed Structure
The enhanced transaction embed now includes:

1. **Current Moves** - List of moves in transaction builder
2. **Roster Status** - Legal/illegal roster counts with limits
3. **Team Cost (sWAR)** - sWAR for both rosters
4. **Transaction Context** - Pre-existing moves impact (conditional)
5. **Errors/Suggestions** - Validation feedback and recommendations

### Usage Examples

#### Basic Transaction Display
```python
# Standard transaction without pre-existing moves
builder = get_transaction_builder(user_id, team)
embed = await create_transaction_embed(builder)
# Shows: moves, roster status, sWAR, errors/suggestions
```

#### Enhanced Context Display
```python
# Transaction with pre-existing moves context
validation = await builder.validate_transaction(next_week=current_week + 1)
embed = await create_transaction_embed(builder)
# Shows: all above + pre-existing transaction impact
```

### User Experience Improvements
- **Complete Context**: Users see full impact including scheduled moves
- **Visual Clarity**: Consistent emoji usage and formatting
- **Conditional Display**: Context only shown when relevant
- **Decision Support**: sWAR projections help strategic planning

### Implementation Notes
- **Backwards Compatible**: Existing embed functionality preserved
- **Conditional Sections**: Pre-existing context only appears when applicable
- **Performance**: Validation data cached to avoid repeated calculations
- **Accessibility**: Clear visual hierarchy with emojis and formatting

---

**Next Steps for AI Agents:**
1. Review existing view implementations for patterns
2. Understand the Discord UI component system
3. Follow the EmbedTemplate system for consistent styling
4. Implement proper error handling and user validation
5. Test interactive components thoroughly
6. Consider accessibility and user experience in design
7. Leverage enhanced transaction context for better user guidance