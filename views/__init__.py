"""
Discord UI components for Bot v2.0

Interactive views, buttons, modals, and select menus providing a modern,
consistent UI experience for the SBA Discord bot.

## Core Components

### Base Views (views.base)
- BaseView: Foundation class with error handling and user authorization
- ConfirmationView: Standard Yes/No confirmation dialogs
- PaginationView: Navigation through multiple pages of content
- SelectMenuView: Base for dropdown selection menus

### Embed Templates (views.embeds)
- EmbedTemplate: Standard embed creation with consistent styling
- SBAEmbedTemplate: SBA-specific templates for players, teams, league info
- EmbedBuilder: Fluent interface for building complex embeds
- EmbedColors: Standard color palette

### Common Views (views.common)
- PlayerSelectionView: Select from multiple players
- TeamSelectionView: Select from multiple teams
- DetailedInfoView: Information display with action buttons
- SearchResultsView: Paginated search results with selection
- QuickActionView: Quick action buttons for common operations
- SettingsView: Settings display and modification

### Modals (views.modals)
- PlayerSearchModal: Detailed player search criteria
- TeamSearchModal: Team search form
- FeedbackModal: User feedback collection
- ConfigurationModal: Settings configuration
- CustomInputModal: Flexible input collection

## Usage Examples

### Basic Confirmation
```python
from views.base import ConfirmationView
from views.embeds import EmbedTemplate

embed = EmbedTemplate.warning("Confirm Action", "Are you sure?")
view = ConfirmationView(user_id=interaction.user.id)
await interaction.response.send_message(embed=embed, view=view)
```

### Player Selection
```python
from views.common import PlayerSelectionView

view = PlayerSelectionView(
    players=found_players,
    user_id=interaction.user.id,
    callback=handle_player_selection
)
```

### Paginated Results
```python
from views.base import PaginationView
from views.embeds import SBAEmbedTemplate

pages = [SBAEmbedTemplate.team_info(...) for team in teams]
view = PaginationView(pages=pages, user_id=interaction.user.id)
```

### Custom Modal
```python
from views.modals import PlayerSearchModal

modal = PlayerSearchModal()
await interaction.response.send_modal(modal)
await modal.wait()
if modal.is_submitted:
    search_criteria = modal.result
```

## Design Principles

1. **Consistency**: All views use standard color schemes and layouts
2. **User Authorization**: Views can be restricted to specific users
3. **Error Handling**: Comprehensive error handling with user feedback
4. **Accessibility**: Clear labels, descriptions, and feedback
5. **Performance**: Efficient pagination and lazy loading
6. **Modularity**: Reusable components for common patterns

## Color Scheme

- PRIMARY (0xa6ce39): SBA green for standard content
- SUCCESS (0x28a745): Green for successful operations
- WARNING (0xffc107): Yellow for warnings and cautions
- ERROR (0xdc3545): Red for errors and failures
- INFO (0x17a2b8): Blue for informational content
- SECONDARY (0x6c757d): Gray for secondary content

## Best Practices

1. Always specify user_id for user-specific views
2. Use appropriate timeouts based on expected interaction time
3. Provide clear feedback for all user interactions
4. Handle edge cases (empty results, errors, timeouts)
5. Use consistent embed styling across related commands
6. Implement proper validation for modal inputs
7. Provide help text and examples in placeholders
"""

# Import core classes for easy access
from .base import BaseView, ConfirmationView, PaginationView, SelectMenuView
from .embeds import (
    EmbedTemplate, 
    SBAEmbedTemplate, 
    EmbedBuilder, 
    EmbedColors
)
from .common import (
    PlayerSelectionView,
    TeamSelectionView,
    DetailedInfoView,
    SearchResultsView,
    QuickActionView,
    SettingsView
)
from .modals import (
    PlayerSearchModal,
    TeamSearchModal,
    FeedbackModal,
    ConfigurationModal,
    CustomInputModal,
    validate_email,
    validate_numeric,
    validate_integer,
    validate_team_abbreviation,
    validate_season
)

__all__ = [
    # Base components
    'BaseView',
    'ConfirmationView', 
    'PaginationView',
    'SelectMenuView',
    
    # Embed templates
    'EmbedTemplate',
    'SBAEmbedTemplate',
    'EmbedBuilder',
    'EmbedColors',
    
    # Common views
    'PlayerSelectionView',
    'TeamSelectionView',
    'DetailedInfoView',
    'SearchResultsView',
    'QuickActionView',
    'SettingsView',
    
    # Modals
    'PlayerSearchModal',
    'TeamSearchModal',
    'FeedbackModal',
    'ConfigurationModal',
    'CustomInputModal',
    
    # Validators
    'validate_email',
    'validate_numeric',
    'validate_integer',
    'validate_team_abbreviation',
    'validate_season'
]