# Discord Bot v2.0 - Complete Command List

**Generated:** January 2025
**Bot Version:** 2.0
**Total Commands:** 55+ slash commands

---

## 📊 League Information Commands

### `/league`
Display current league status and information

### `/standings`
Display league standings

### `/playoff-picture`
Display current playoff picture

### `/schedule`
Display game schedule

### `/results`
Display recent game results

---

## 👥 Player Commands

### `/player <name>`
Display player information and statistics
- **Parameters:** Player name (autocomplete enabled)

---

## 🏟️ Team Commands

### `/team <abbrev> [season]`
Display team information
- **Parameters:**
  - `abbrev`: Team abbreviation (e.g., NYY, BOS, LAD)
  - `season`: Season to show (optional, defaults to current)

### `/teams [season]`
List all teams in a season
- **Parameters:**
  - `season`: Season to list (optional, defaults to current)

### `/roster <abbrev> [roster_type]`
Display team roster
- **Parameters:**
  - `abbrev`: Team abbreviation
  - `roster_type`: Current or Next week (optional)

---

## 🔄 Transaction Commands

### `/mymoves`
View your pending and scheduled transactions

### `/legal`
Check roster legality for current and next week

### `/dropadd`
Build a transaction for next week

### `/cleartransaction`
Clear your current transaction builder

---

## 🤝 Trade Commands

### `/trade initiate <other_team>`
Start a new trade with another team
- **Parameters:**
  - `other_team`: Team abbreviation (autocomplete enabled)
- **Creates:** Dedicated trade discussion channel

### `/trade add-team <other_team>`
Add another team to your current trade (for 3+ team trades)
- **Parameters:**
  - `other_team`: Team abbreviation (autocomplete enabled)

### `/trade add-player <player_name> <destination_team>`
Add a player to the trade
- **Parameters:**
  - `player_name`: Player name (autocomplete enabled)
  - `destination_team`: Team abbreviation (autocomplete enabled)

### `/trade supplementary <player_name> <destination>`
Add a supplementary move within your organization for roster legality
- **Parameters:**
  - `player_name`: Player name (autocomplete enabled)
  - `destination`: Major League, Minor League, or Free Agency

### `/trade view`
View your current trade

### `/trade clear`
Clear your current trade and delete associated channel

---

## 🎲 Dice Rolling Commands

### `/roll <dice>`
Roll polyhedral dice using XdY notation (e.g., 2d6, 1d20, 3d8)
- **Parameters:**
  - `dice`: Dice notation (e.g., "2d6", "1d6;2d6;1d20")

### `/ab`
Roll baseball at-bat dice (1d6;2d6;1d20)

### `/scout <card_type>`
Roll weighted scouting dice (1d6;2d6;1d20) based on card type
- **Parameters:**
  - `card_type`: Batter (1-3 first d6) or Pitcher (4-6 first d6)

### `/fielding <position>`
Roll Super Advanced fielding dice for a defensive position
- **Parameters:**
  - `position`: C, 1B, 2B, 3B, SS, LF, CF, RF

---

## ⚙️ Utility Commands

### `/weather [team_abbrev]`
Roll ballpark weather for a team
- **Parameters:**
  - `team_abbrev`: Team abbreviation (optional, auto-detects from channel/user)

### `/charts <chart_name>`
Display a gameplay chart or infographic
- **Parameters:**
  - `chart_nam  e`: Name of chart (autocomplete enabled)

---

## 🗣️ Voice Channel Commands

### `/voice-channel public`
Create a public voice channel for gameplay
- **Auto-cleanup:** Deletes after 15 minutes of being empty

### `/voice-channel private`
Create a private team vs team voice channel
- **Permissions:** Only team members can speak, others can listen
- **Auto-detection:** Automatically finds your opponent from schedule
- **Auto-cleanup:** Deletes after 15 minutes of being empty

---

## 📝 Custom Commands

### `/cc <name>`
Execute a custom command
- **Parameters:**
  - `name`: Name of custom command to execute

### `/cc-create`
Create a new custom command
- Opens interactive modal for input

### `/cc-edit <name>`
Edit one of your custom commands
- **Parameters:**
  - `name`: Name of command to edit

### `/cc-delete <name>`
Delete one of your custom commands
- **Parameters:**
  - `name`: Name of command to delete

### `/cc-mine`
View and manage your custom commands

### `/cc-list`
Browse all custom commands

### `/cc-search`
Advanced search for custom commands

### `/cc-info <name>`
Get detailed information about a custom command
- **Parameters:**
  - `name`: Name of command

---

## 📚 Help System Commands

### `/help [topic]`
View help topics or list all available help
- **Parameters:**
  - `topic`: Specific help topic (optional, autocomplete enabled)

### `/help-create`
Create a new help topic (admin/help editor only)
- Opens interactive modal for input

### `/help-edit <topic>`
Edit an existing help topic (admin/help editor only)
- **Parameters:**
  - `topic`: Topic name to edit (autocomplete enabled)

### `/help-delete <topic>`
Delete a help topic (admin/help editor only)
- **Parameters:**
  - `topic`: Topic name to delete (autocomplete enabled)

### `/help-list [category] [show_deleted]`
Browse all help topics
- **Parameters:**
  - `category`: Filter by category (optional)
  - `show_deleted`: Include deleted topics (optional, admin only)

---

## 🖼️ Profile Management Commands

### `/set-image <image_type> <player_name> <image_url>`
Update a player's fancy card or headshot image
- **Parameters:**
  - `image_type`: Fancy Card or Headshot
  - `player_name`: Player name (autocomplete enabled)
  - `image_url`: URL to image
- **Permissions:**
  - Regular users: Can update players in their organization (ML/MiL/IL)
  - Administrators: Can update any player
- **Validation:** Checks URL accessibility and content-type

---

## 🎭 Meme Commands

### `/lastsoak`
Get information about the last soak mention
- Displays last player to say the forbidden word
- Shows disappointment GIF
- Tracks total mentions

---

## 🔧 Admin Commands

### `/admin-status`
Display bot status and system information

### `/admin-help`
Display available admin commands and their usage

### `/admin-reload <cog>`
Reload a specific bot cog
- **Parameters:**
  - `cog`: Name of cog to reload

### `/admin-sync`
Sync application commands with Discord

### `/admin-clear <amount>`
Clear messages from the current channel
- **Parameters:**
  - `amount`: Number of messages to clear

### `/admin-announce <message>`
Send an announcement to the current channel
- **Parameters:**
  - `message`: Announcement text

### `/admin-maintenance`
Toggle maintenance mode for the bot

### `/admin-timeout <user> <duration> [reason]`
Timeout a user for a specified duration
- **Parameters:**
  - `user`: User to timeout
  - `duration`: Duration (e.g., "10m", "1h", "1d")
  - `reason`: Optional reason

### `/admin-untimeout <user>`
Remove timeout from a user
- **Parameters:**
  - `user`: User to remove timeout from

### `/admin-kick <user> [reason]`
Kick a user from the server
- **Parameters:**
  - `user`: User to kick
  - `reason`: Optional reason

### `/admin-ban <user> [reason]`
Ban a user from the server
- **Parameters:**
  - `user`: User to ban
  - `reason`: Optional reason

### `/admin-unban <user_id>`
Unban a user from the server
- **Parameters:**
  - `user_id`: Discord user ID to unban

### `/admin-userinfo <user>`
Display detailed information about a user
- **Parameters:**
  - `user`: User to get info about

---

## 🛠️ Admin - Chart Management Commands

### `/chart-add <key> <name> <category> <url> [description]`
[Admin] Add a new chart to the library
- **Parameters:**
  - `key`: Unique identifier (e.g., 'rest', 'sac-bunt')
  - `name`: Display name
  - `category`: gameplay, defense, reference, stats
  - `url`: Image URL
  - `description`: Optional description

### `/chart-remove <key>`
[Admin] Remove a chart from the library
- **Parameters:**
  - `key`: Chart key to remove

### `/chart-list [category]`
[Admin] List all available charts
- **Parameters:**
  - `category`: Filter by category (optional)

### `/chart-update <key> [name] [category] [url] [description]`
[Admin] Update a chart's properties
- **Parameters:**
  - `key`: Chart key to update
  - All other parameters are optional updates

---

## 📊 Command Statistics

- **Total Slash Commands:** 55+
- **Command Groups:** 2 (`/voice-channel`, `/trade`)
- **Admin Commands:** 16
- **User Commands:** 39+
- **Autocomplete Enabled:** 15+ commands
- **Interactive Modals:** 4 commands (cc-create, cc-edit, help-create, help-edit)

---

## 🎯 Key Features

### Autocomplete Support
Commands with autocomplete for better UX:
- Player names
- Team abbreviations
- Chart names
- Help topics
- Custom command names

### Interactive Features
- Trade builder with real-time validation
- Trade discussion channels
- Custom command modals
- Help topic modals
- Confirmation dialogs

### Auto-cleanup Services
- Voice channels (15 min empty threshold)
- Trade discussion channels (on trade clear)

### Permission System
- User-level permissions (own organization players)
- Admin-level permissions (full access)
- Role-based permissions (Help Editor role)

---

## 📝 Notes

- All commands use modern Discord slash command syntax (`/command`)
- Deprecated prefix commands (`!command`) show migration messages
- Most commands use ephemeral responses for privacy
- Comprehensive error handling and validation
- Full logging with trace IDs for debugging
