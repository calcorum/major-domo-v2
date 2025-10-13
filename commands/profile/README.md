# Player Image Management Commands

**Last Updated:** January 2025
**Status:** ✅ Fully Implemented
**Location:** `commands/profile/`

## Overview

The Player Image Management system allows users to update player fancy card and headshot images for players on teams they own. Administrators can update any player's images.

## Commands

### `/set-image <image_type> <player_name> <image_url>`
**Description:** Update a player's fancy card or headshot image

**Parameters:**
- `image_type` (choice): Choose "Fancy Card" or "Headshot"
  - **Fancy Card**: Shows as thumbnail in player cards (takes priority)
  - **Headshot**: Shows as thumbnail if no fancy card exists
- `player_name` (string with autocomplete): Player to update
- `image_url` (string): Direct URL to the image file

**Permissions:**
- **Regular Users**: Can update images for players on teams they own (ML/MiL/IL)
- **Administrators**: Can update any player's images (bypasses organization check)

**Usage Examples:**
```
/set-image fancy-card "Mike Trout" https://example.com/cards/trout.png
/set-image headshot "Shohei Ohtani" https://example.com/headshots/ohtani.jpg
```

## Permission System

### Regular Users
Users can update images for players in their organization:
- **Major League team players** - Direct team ownership
- **Minor League team players** - Owned via organizational affiliation
- **Injured List team players** - Owned via organizational affiliation

**Example:**
If you own the NYY team, you can update images for players on:
- NYY (Major League)
- NYYMIL (Minor League)
- NYYIL (Injured List)

### Administrators
Administrators have unrestricted access to update any player's images regardless of team ownership.

### Permission Check Logic
```python
# Check order:
1. Is user an administrator? → Grant access
2. Does user own any teams? → Continue check
3. Does player belong to user's organization? → Grant access
4. Otherwise → Deny access
```

## URL Requirements

### Format Validation
URLs must meet the following criteria:
- **Protocol**: Must start with `http://` or `https://`
- **Extension**: Must end with valid image extension:
  - `.jpg`, `.jpeg` - JPEG format
  - `.png` - PNG format
  - `.gif` - GIF format (includes animated GIFs)
  - `.webp` - WebP format
- **Length**: Maximum 500 characters
- **Query parameters**: Allowed (e.g., `?size=large`)

**Valid Examples:**
```
https://example.com/image.jpg
https://cdn.discord.com/attachments/123/456/player.png
https://i.imgur.com/abc123.webp
https://example.com/image.jpg?size=large&format=original
```

**Invalid Examples:**
```
example.com/image.jpg                    ❌ Missing protocol
ftp://example.com/image.jpg              ❌ Wrong protocol
https://example.com/document.pdf         ❌ Wrong extension
https://example.com/page                 ❌ No extension
```

### Accessibility Testing
After format validation, the bot tests URL accessibility:
- **HTTP HEAD Request**: Checks if URL is reachable
- **Status Code**: Must return 200 OK
- **Content-Type**: Must return `image/*` header
- **Timeout**: 5 seconds maximum

**Common Accessibility Errors:**
- `404 Not Found` - Image doesn't exist at URL
- `403 Forbidden` - Permission denied
- `Timeout` - Server too slow or unresponsive
- `Wrong content-type` - URL points to webpage, not image

## Workflow

### Step-by-Step Process

1. **User invokes command**
   ```
   /set-image fancy-card "Mike Trout" https://example.com/card.png
   ```

2. **URL Format Validation**
   - Checks protocol, extension, length
   - If invalid: Shows error with requirements

3. **URL Accessibility Test**
   - HTTP HEAD request to URL
   - Checks status code and content-type
   - If inaccessible: Shows error with troubleshooting tips

4. **Player Lookup**
   - Searches for player by name
   - Handles multiple matches (asks for exact name)
   - If not found: Shows error

5. **Permission Check**
   - Admin check → Grant access
   - Organization ownership check → Grant/deny access
   - If denied: Shows permission error

6. **Preview with Confirmation**
   - Shows embed with new image as thumbnail
   - Displays current vs new image info
   - **Confirm Update** button → Proceed
   - **Cancel** button → Abort

7. **Database Update**
   - Updates `vanity_card` or `headshot` field
   - If failure: Shows error

8. **Success Message**
   - Confirms update
   - Shows new image
   - Displays updated player info

## Field Mapping

| Choice | Database Field | Display Priority | Notes |
|--------|----------------|------------------|-------|
| Fancy Card | `vanity_card` | 1st (highest) | Custom fancy player card |
| Headshot | `headshot` | 2nd | Player headshot photo |
| *(default)* | `team.thumbnail` | 3rd (fallback) | Team logo |

**Display Logic in Player Cards:**
```
IF player.vanity_card exists:
    Show vanity_card as thumbnail
ELSE IF player.headshot exists:
    Show headshot as thumbnail
ELSE IF player.team.thumbnail exists:
    Show team logo as thumbnail
ELSE:
    No thumbnail
```

## Best Practices

### For Users

#### Choosing Image URLs
✅ **DO:**
- Use reliable image hosting (Discord CDN, Imgur, established hosts)
- Use direct image links (right-click image → "Copy Image Address")
- Test URLs in browser before submitting
- Use permanent URLs, not temporary upload links

❌ **DON'T:**
- Use image hosting page URLs (must be direct image file)
- Use temporary or expiring URLs
- Use images from unreliable hosts
- Use extremely large images (impacts Discord performance)

#### Image Recommendations
**Fancy Cards:**
- Recommended size: 400x600px (or similar 2:3 aspect ratio)
- Format: PNG or JPEG
- File size: < 2MB for best performance
- Style: Custom designs, player stats, artistic renditions

**Headshots:**
- Recommended size: 256x256px (square aspect ratio)
- Format: PNG or JPEG with transparent background
- File size: < 500KB
- Style: Professional headshot, clean background

#### Finding Good Image URLs
1. **Discord CDN** (best option):
   - Upload image to Discord
   - Right-click → Copy Link
   - Paste as image URL

2. **Imgur**:
   - Upload to Imgur
   - Right-click image → Copy Image Address
   - Use direct link (ends with `.png` or `.jpg`)

3. **Other hosts**:
   - Ensure stable, permanent hosting
   - Verify URL accessibility before using

### For Administrators

#### Managing Player Images
- Set consistent style guidelines for your league
- Use standard image dimensions for uniformity
- Maintain backup copies of custom images
- Document image sources for attribution

#### Troubleshooting User Issues
Common problems and solutions:

| Issue | Cause | Solution |
|-------|-------|----------|
| "URL not accessible" | Host down, URL expired | Ask for new URL from stable host |
| "Not a valid image" | URL points to webpage | Get direct image link |
| "Permission denied" | User doesn't own team | Verify team ownership |
| "Player not found" | Typo in name | Use autocomplete feature |

## Error Messages

### Format Errors
```
❌ Invalid URL Format
URL must start with http:// or https://

Requirements:
• Must start with `http://` or `https://`
• Must end with `.jpg`, `.jpeg`, `.png`, `.gif`, or `.webp`
• Maximum 500 characters
```

### Accessibility Errors
```
❌ URL Not Accessible
URL returned status 404

Please check:
• URL is correct and not expired
• Image host is online
• URL points directly to an image file
• URL is publicly accessible
```

### Permission Errors
```
❌ Permission Denied
You don't own a team in the NYY organization

You can only update images for players on teams you own.
```

### Player Not Found
```
❌ Player Not Found
No player found matching 'Mike Trut' in the current season.
```

### Multiple Players Found
```
🔍 Multiple Players Found
Multiple players match 'Mike':
• Mike Trout (OF)
• Mike Zunino (C)

Please use the exact name from autocomplete.
```

## Technical Implementation

### Architecture
```
commands/profile/
├── __init__.py              # Package setup
├── images.py               # Main command implementation
│   ├── validate_url_format()          # Format validation
│   ├── test_url_accessibility()       # Accessibility testing
│   ├── can_edit_player_image()        # Permission checking
│   ├── ImageUpdateConfirmView         # Confirmation UI
│   ├── player_name_autocomplete()     # Autocomplete function
│   └── ImageCommands                  # Command cog
└── README.md               # This file
```

### Dependencies
- `aiohttp` - Async HTTP requests for URL testing
- `discord.py` - Discord bot framework
- `player_service` - Player CRUD operations
- `team_service` - Team queries and ownership
- Standard bot utilities (logging, decorators, embeds)

### Database Fields
**Player Model** (`models/player.py`):
```python
vanity_card: Optional[str] = Field(None, description="Custom vanity card URL")
headshot: Optional[str] = Field(None, description="Player headshot URL")
```

Both fields are optional and store direct image URLs.

### API Integration
**Update Operation:**
```python
# Update player image
update_data = {"vanity_card": "https://example.com/card.png"}
updated_player = await player_service.update_player(player_id, update_data)
```

**Endpoints Used:**
- `GET /api/v3/players?name={name}&season={season}` - Player search
- `PATCH /api/v3/players/{player_id}?vanity_card={url}` - Update player data
- `GET /api/v3/teams?owner_id={user_id}&season={season}` - User's teams

**Important Note:**
The player PATCH endpoint uses **query parameters** instead of JSON body for data updates. The `player_service.update_player()` method automatically handles this by setting `use_query_params=True` when calling the API client.

## Testing

### Test Coverage
**Test File:** `tests/test_commands_profile_images.py`

**Test Categories:**
1. **URL Format Validation** (10 tests)
   - Valid formats (JPG, PNG, WebP, with query params)
   - Invalid protocols (no protocol, FTP)
   - Invalid extensions (PDF, no extension)
   - URL length limits

2. **URL Accessibility** (5 tests)
   - Successful access
   - 404 errors
   - Wrong content-type
   - Timeouts
   - Connection errors

3. **Permission Checking** (7 tests)
   - Admin access to all players
   - User access to owned teams
   - User access to MiL/IL players
   - Denial for other organizations
   - Denial for users without teams
   - Players without team assignment

4. **Integration Tests** (3 tests)
   - Command structure validation
   - Field mapping logic

### Running Tests
```bash
# Run all image management tests
python -m pytest tests/test_commands_profile_images.py -v

# Run specific test class
python -m pytest tests/test_commands_profile_images.py::TestURLValidation -v

# Run with coverage
python -m pytest tests/test_commands_profile_images.py --cov=commands.profile
```

## Future Enhancements

### Planned Features (Post-Launch)
- **Image size validation**: Check image dimensions
- **Image upload support**: Upload images directly instead of URLs
- **Bulk image updates**: Update multiple players at once
- **Image preview history**: See previous images
- **Image moderation**: Admin approval queue for user submissions
- **Default images**: Set default fancy cards per team
- **Image gallery**: View all player images for a team

### Potential Improvements
- **Automatic image optimization**: Resize/compress large images
- **CDN integration**: Auto-upload to Discord CDN for permanence
- **Image templates**: Pre-designed templates users can fill in
- **Batch operations**: Admin tool to set multiple images
- **Image analytics**: Track which images are most viewed

## Troubleshooting

### Common Issues

**Problem:** "URL not accessible" but URL works in browser
- **Cause:** Content-Delivery-Network (CDN) may require browser headers
- **Solution:** Use Discord CDN or Imgur instead

**Problem:** Permission denied even though I own the team
- **Cause:** Season mismatch or ownership data not synced
- **Solution:** Contact admin to verify team ownership data

**Problem:** Image appears broken in Discord
- **Cause:** Discord can't load the image (blocked, wrong format, too large)
- **Solution:** Try different host or smaller file size

**Problem:** Autocomplete doesn't show player
- **Cause:** Player doesn't exist in current season
- **Solution:** Verify player name and season

### Support

For issues or questions:
1. Check this README for solutions
2. Review error messages carefully (they include troubleshooting steps)
3. Contact server administrators
4. Check bot logs for detailed error information

---

**Implementation Details:**
- **Commands:** `commands/profile/images.py`
- **Tests:** `tests/test_commands_profile_images.py`
- **Models:** `models/player.py` (vanity_card, headshot fields)
- **Services:** `services/player_service.py`, `services/team_service.py`

**Related Documentation:**
- **Bot Architecture:** `/discord-app-v2/CLAUDE.md`
- **Command Patterns:** `/discord-app-v2/commands/README.md`
- **Testing Guide:** `/discord-app-v2/tests/README.md`
