# Help Commands System

**Last Updated:** January 2025
**Status:** ✅ Fully Implemented
**Location:** `commands/help/`

## Overview

The Help Commands System provides a comprehensive, admin-managed help system for the Discord server. Administrators and designated "Help Editors" can create, edit, and manage custom help topics covering league documentation, resources, FAQs, links, and guides. This system replaces the originally planned `/links` command with a more flexible and powerful solution.

## Commands

### `/help [topic]`
**Description:** View a help topic or list all available topics
**Parameters:**
- `topic` (optional): Name of the help topic to view

**Behavior:**
- **With topic**: Displays the specified help topic with formatted content
- **Without topic**: Shows a paginated list of all available help topics organized by category
- Automatically increments view count when a topic is viewed

**Permissions:** Available to all server members

**Examples:**
```
/help trading-rules
/help
```

### `/help-create`
**Description:** Create a new help topic
**Permissions:** Administrators + "Help Editor" role

**Modal Fields:**
- **Topic Name**: URL-safe name (2-32 chars, letters/numbers/dashes only)
- **Display Title**: Human-readable title (1-200 chars)
- **Category**: Optional category (rules/guides/resources/info/faq)
- **Content**: Help content with markdown support (1-4000 chars)

**Features:**
- Real-time validation of all fields
- Preview before final creation
- Automatic duplicate detection

**Example:**
```
Topic Name: trading-rules
Display Title: Trading Rules & Guidelines
Category: rules
Content: [Detailed trading rules with markdown formatting]
```

### `/help-edit <topic>`
**Description:** Edit an existing help topic
**Parameters:**
- `topic` (required): Name of the help topic to edit

**Permissions:** Administrators + "Help Editor" role

**Features:**
- Pre-populated modal with current values
- Shows preview of changes before saving
- Tracks last editor and update timestamp
- Autocomplete for topic names

**Example:**
```
/help-edit trading-rules
```

### `/help-delete <topic>`
**Description:** Delete a help topic (soft delete)
**Parameters:**
- `topic` (required): Name of the help topic to delete

**Permissions:** Administrators + "Help Editor" role

**Features:**
- Confirmation dialog before deletion
- Shows topic statistics (view count)
- Soft delete (can be restored later)
- Autocomplete for topic names

**Example:**
```
/help-delete trading-rules
```

### `/help-list [category] [show_deleted]`
**Description:** Browse all help topics
**Parameters:**
- `category` (optional): Filter by category
- `show_deleted` (optional): Show soft-deleted topics (admin only)

**Permissions:** Available to all (show_deleted requires admin/help editor)

**Features:**
- Organized display by category
- Shows view counts
- Paginated interface for many topics
- Filtered views by category

**Examples:**
```
/help-list
/help-list category:rules
/help-list show_deleted:true
```

## Permission System

### Roles with Help Edit Permissions
1. **Server Administrators** - Full access to all help commands
2. **Help Editor Role** - Designated role with editing permissions
   - Role name: "Help Editor" (configurable in `constants.py`)
   - Can create, edit, and delete help topics
   - Cannot view deleted topics unless also admin

### Permission Checks
```python
def has_help_edit_permission(interaction: discord.Interaction) -> bool:
    """Check if user can edit help commands."""
    # Admin check
    if interaction.user.guild_permissions.administrator:
        return True

    # Help Editor role check
    role = discord.utils.get(interaction.guild.roles, name=HELP_EDITOR_ROLE_NAME)
    if role and role in interaction.user.roles:
        return True

    return False
```

## Architecture

### Components

**Models** (`models/help_command.py`):
- `HelpCommand`: Main data model with validation
- `HelpCommandSearchFilters`: Search/filtering parameters
- `HelpCommandSearchResult`: Paginated search results
- `HelpCommandStats`: Statistics and analytics

**Service Layer** (`services/help_commands_service.py`):
- `HelpCommandsService`: CRUD operations and business logic
- `help_commands_service`: Global service instance
- Integrates with BaseService for API calls

**Views** (`views/help_commands.py`):
- `HelpCommandCreateModal`: Interactive creation modal
- `HelpCommandEditModal`: Interactive editing modal
- `HelpCommandDeleteConfirmView`: Deletion confirmation
- `HelpCommandListView`: Paginated topic browser
- `create_help_topic_embed()`: Formatted topic display

**Commands** (`commands/help/main.py`):
- `HelpCommands`: Cog with all command handlers
- Permission checking integration
- Autocomplete for topic names
- Error handling and user feedback

### Data Flow

1. **User Interaction** → Discord slash command
2. **Permission Check** → Validate user permissions
3. **Modal Display** → Interactive data input (for create/edit)
4. **Service Call** → Business logic and validation
5. **API Request** → Database operations via API
6. **Response** → Formatted embed with success/error message

### Database Integration

**API Endpoints** (via `../database/app/routers_v3/help_commands.py`):
- `GET /api/v3/help_commands` - List with filters
- `GET /api/v3/help_commands/{id}` - Get by ID
- `GET /api/v3/help_commands/by_name/{name}` - Get by name
- `POST /api/v3/help_commands` - Create
- `PUT /api/v3/help_commands/{id}` - Update
- `DELETE /api/v3/help_commands/{id}` - Soft delete
- `PATCH /api/v3/help_commands/{id}/restore` - Restore
- `PATCH /api/v3/help_commands/by_name/{name}/view` - Increment views
- `GET /api/v3/help_commands/autocomplete` - Autocomplete
- `GET /api/v3/help_commands/stats` - Statistics

**Database Table** (`help_commands`):
```sql
CREATE TABLE help_commands (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT,
    created_by_discord_id BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    last_modified_by BIGINT,
    is_active BOOLEAN DEFAULT TRUE,
    view_count INTEGER DEFAULT 0,
    display_order INTEGER DEFAULT 0
);
```

## Features

### Soft Delete
- Topics are never permanently deleted from the database
- `is_active` flag controls visibility
- Admins can restore deleted topics (future enhancement)
- Full audit trail preserved

### View Tracking
- Automatic view count increment when topics are accessed
- Statistics available via API
- Most viewed topics tracked

### Category Organization
- Optional categorization of topics
- Suggested categories:
  - `rules` - League rules and regulations
  - `guides` - How-to guides and tutorials
  - `resources` - Links to external resources
  - `info` - General league information
  - `faq` - Frequently asked questions

### Markdown Support
- Full markdown formatting in content
- Support for:
  - Headers
  - Bold/italic text
  - Lists (ordered and unordered)
  - Links
  - Code blocks
  - Blockquotes

### Autocomplete
- Fast topic name suggestions
- Searches across names and titles
- Limited to 25 suggestions for performance

## Use Cases

### Example Help Topics

**Trading Rules** (`/help trading-rules`):
```markdown
# Trading Rules & Guidelines

## Trade Deadline
All trades must be completed by Week 15 of the regular season.

## Restrictions
- Maximum 3 trades per team per season
- All trades must be approved by league commissioner
- No trading draft picks beyond 2 seasons ahead

## How to Propose a Trade
Use the `/trade` command to propose a trade. Both teams must accept before the trade is processed.
```

**Discord Links** (`/help links`):
```markdown
# Important League Links

## Website
https://sba-league.com

## Google Sheet
https://docs.google.com/spreadsheets/...

## Discord Invite
https://discord.gg/...

## Rules Document
https://docs.google.com/document/...
```

**How to Trade** (`/help how-to-trade`):
```markdown
# How to Use the Trade System

1. Type `/trade` to start a new trade proposal
2. Select the team you want to trade with
3. Add players/picks to the trade
4. Submit for review
5. Both teams must accept
6. Commissioner approves
7. Trade is processed!

For more information, see `/help trading-rules`
```

## Error Handling

### Common Errors

**Topic Not Found**:
```
❌ Topic Not Found
No help topic named 'xyz' exists.
Use /help to see available topics.
```

**Permission Denied**:
```
❌ Permission Denied
Only administrators and users with the Help Editor role can create help topics.
```

**Topic Already Exists**:
```
❌ Topic Already Exists
A help topic named 'trading-rules' already exists.
Try a different name.
```

**Validation Errors**:
- Topic name too short/long
- Invalid characters in topic name
- Content too long (>4000 chars)
- Title too long (>200 chars)

## Best Practices

### For Administrators

1. **Use Clear Topic Names**
   - Use lowercase with hyphens: `trading-rules`, `how-to-draft`
   - Keep names short but descriptive
   - Avoid special characters

2. **Organize by Category**
   - Consistent category naming
   - Group related topics together
   - Use standard categories (rules, guides, resources, info, faq)

3. **Write Clear Content**
   - Use markdown formatting for readability
   - Keep content concise and focused
   - Link to related topics when appropriate
   - Update regularly to keep information current

4. **Monitor Usage**
   - Check view counts to see popular topics
   - Update frequently accessed topics
   - Archive outdated information

### For Users

1. **Browse Topics**
   - Use `/help` to see all available topics
   - Use `/help-list` to browse by category
   - Use autocomplete to find topics quickly

2. **Request New Topics**
   - Contact admins or help editors
   - Suggest topics that would be useful
   - Provide draft content if possible

## Testing

### Test Coverage
- ✅ Model validation tests
- ✅ Service layer CRUD operations
- ✅ Permission checking
- ✅ Autocomplete functionality
- ✅ Soft delete behavior
- ✅ View count incrementing

### Test Files
- `tests/test_models_help_command.py`
- `tests/test_services_help_commands.py`
- `tests/test_commands_help.py`

## Future Enhancements

### Planned Features (Post-Launch)
- Restore command for deleted topics (`/help-restore <topic>`)
- Statistics dashboard (`/help-stats`)
- Search functionality across all content
- Topic versioning and change history
- Attachments support (images, files)
- Related topics linking
- User feedback and ratings
- Full-text search in content

### Potential Improvements
- Rich embed support with custom colors
- Topic aliases (multiple names for same topic)
- Scheduled topic updates
- Topic templates for common formats
- Import/export functionality
- Bulk operations for admins

## Migration from Legacy System

If migrating from an older help/links system:

1. **Export existing content** from old system
2. **Create help topics** using `/help-create`
3. **Test all topics** for formatting and accuracy
4. **Update documentation** to reference new commands
5. **Train help editors** on new system
6. **Announce to users** with usage instructions

## Support

### For Users
- Use `/help` to browse available topics
- Contact server admins for topic requests
- Report broken links or outdated information

### For Administrators
- Review the implementation plan in `.claude/HELP_COMMANDS_PLAN.md`
- Check database migration docs in `.claude/DATABASE_MIGRATION_HELP_COMMANDS.md`
- See main project documentation in `CLAUDE.md`

---

**Implementation Details:**
- **Models:** `models/help_command.py`
- **Service:** `services/help_commands_service.py`
- **Views:** `views/help_commands.py`
- **Commands:** `commands/help/main.py`
- **Constants:** `constants.py` (HELP_EDITOR_ROLE_NAME)
- **Tests:** `tests/test_*_help*.py`

**Related Documentation:**
- Implementation Plan: `.claude/HELP_COMMANDS_PLAN.md`
- Database Migration: `.claude/DATABASE_MIGRATION_HELP_COMMANDS.md`
- Project Overview: `CLAUDE.md`
- Roadmap: `PRE_LAUNCH_ROADMAP.md`
