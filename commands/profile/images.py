"""
Player Image Management Commands

Allows users to update player fancy card and headshot images for players
on teams they own. Admins can update any player's images.
"""
from typing import Optional, List, Tuple
import asyncio
import aiohttp

import discord
from discord import app_commands
from discord.ext import commands

from config import get_config
from services.player_service import player_service
from services.team_service import team_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from views.embeds import EmbedColors, EmbedTemplate
from views.base import BaseView
from models.player import Player


# URL Validation Functions

def validate_url_format(url: str) -> Tuple[bool, str]:
    """
    Validate URL format for image links.

    Args:
        url: URL to validate

    Returns:
        Tuple of (is_valid, error_message)
        If valid, error_message is empty string
    """
    # Length check
    if len(url) > 500:
        return False, "URL too long (max 500 characters)"

    # Protocol check
    if not url.startswith(('http://', 'https://')):
        return False, "URL must start with http:// or https://"

    # Image extension check
    valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
    url_lower = url.lower()

    # Check if URL ends with valid extension (ignore query params)
    base_url = url_lower.split('?')[0]  # Remove query parameters
    if not any(base_url.endswith(ext) for ext in valid_extensions):
        return False, f"URL must end with a valid image extension: {', '.join(valid_extensions)}"

    return True, ""


async def check_url_accessibility(url: str) -> Tuple[bool, str]:
    """
    Check if URL is accessible and returns image content.

    Args:
        url: URL to test

    Returns:
        Tuple of (is_accessible, error_message)
        If accessible, error_message is empty string
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status != 200:
                    return False, f"URL returned status {response.status}"

                # Check content-type header
                content_type = response.headers.get('content-type', '').lower()
                if content_type and not content_type.startswith('image/'):
                    return False, f"URL does not return an image (content-type: {content_type})"

                return True, ""

    except aiohttp.ClientError as e:
        return False, f"Could not access URL: {str(e)}"
    except asyncio.TimeoutError:
        return False, "URL request timed out after 5 seconds"
    except Exception as e:
        return False, f"Error testing URL: {str(e)}"


# Permission Checking

async def can_edit_player_image(
    interaction: discord.Interaction,
    player: Player,
    season: int,
    logger
) -> Tuple[bool, str]:
    """
    Check if user can edit player's image.

    Args:
        interaction: Discord interaction object
        player: Player to check permissions for
        season: Season to check
        logger: Logger for debug output

    Returns:
        Tuple of (has_permission, error_message)
        If has permission, error_message is empty string
    """
    # Admins can edit anyone
    if interaction.user.guild_permissions.administrator:
        logger.debug("User is admin, granting permission", user_id=interaction.user.id)
        return True, ""

    # Check if player has a team
    if not player.team:
        return False, "Cannot determine player's team ownership"

    # Get user's teams (all roster types)
    user_teams = await team_service.get_teams_by_owner(interaction.user.id, season)

    if not user_teams:
        return False, "You don't own any teams in the current season"

    # Check if any of user's teams are in same organization as player's team
    for user_team in user_teams:
        if user_team.is_same_organization(player.team):
            logger.debug(
                "User owns organization, granting permission",
                user_id=interaction.user.id,
                user_team=user_team.abbrev,
                player_team=player.team.abbrev
            )
            return True, ""

    # User doesn't own this organization
    player_org = player.team._get_base_abbrev()
    return False, f"You don't own a team in the {player_org} organization"


# Confirmation View

class ImageUpdateConfirmView(BaseView):
    """Confirmation view showing image preview before updating."""

    def __init__(self, player: Player, image_url: str, image_type: str, user_id: int):
        super().__init__(timeout=180.0, user_id=user_id)
        self.player = player
        self.image_url = image_url
        self.image_type = image_type
        self.confirmed = False

    @discord.ui.button(label="Confirm Update", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm the image update."""
        self.confirmed = True

        # Disable all buttons
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True  # type: ignore

        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the image update."""
        self.confirmed = False

        # Disable all buttons
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True  # type: ignore

        await interaction.response.edit_message(view=self)
        self.stop()


# Autocomplete

async def player_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    """Autocomplete for player names, prioritizing user's team players."""
    if len(current) < 2:
        return []

    try:
        # Use the shared autocomplete utility with team prioritization
        from utils.autocomplete import player_autocomplete
        return await player_autocomplete(interaction, current)
    except Exception:
        # Return empty list on error to avoid breaking autocomplete
        return []


# Main Command Cog

class ImageCommands(commands.Cog):
    """Player image management command handlers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.ImageCommands')
        self.logger.info("ImageCommands cog initialized")

    @app_commands.command(
        name="set-image",
        description="Update a player's fancy card or headshot image"
    )
    @app_commands.describe(
        image_type="Type of image to update",
        player_name="Player name (use autocomplete)",
        image_url="Direct URL to the image file"
    )
    @app_commands.choices(image_type=[
        app_commands.Choice(name="Fancy Card", value="fancy-card"),
        app_commands.Choice(name="Headshot", value="headshot")
    ])
    @app_commands.autocomplete(player_name=player_name_autocomplete)
    @logged_command("/set-image")
    async def set_image(
        self,
        interaction: discord.Interaction,
        image_type: app_commands.Choice[str],
        player_name: str,
        image_url: str
    ):
        """Update a player's image (fancy card or headshot)."""
        # Defer response for potentially slow operations
        await interaction.response.defer(ephemeral=True)

        # Get the image type value
        img_type = image_type.value
        field_name = "vanity_card" if img_type == "fancy-card" else "headshot"
        display_name = "Fancy Card" if img_type == "fancy-card" else "Headshot"

        self.logger.info(
            "Image update requested",
            user_id=interaction.user.id,
            player_name=player_name,
            image_type=img_type
        )

        # Step 1: Validate URL format
        is_valid_format, format_error = validate_url_format(image_url)
        if not is_valid_format:
            self.logger.warning("Invalid URL format", url=image_url, error=format_error)
            embed = EmbedTemplate.error(
                title="Invalid URL Format",
                description=f"❌ {format_error}\n\n"
                           f"**Requirements:**\n"
                           f"• Must start with `http://` or `https://`\n"
                           f"• Must end with `.jpg`, `.jpeg`, `.png`, `.gif`, or `.webp`\n"
                           f"• Maximum 500 characters"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Step 2: Test URL accessibility
        self.logger.debug("Testing URL accessibility", url=image_url)
        is_accessible, access_error = await check_url_accessibility(image_url)
        if not is_accessible:
            self.logger.warning("URL not accessible", url=image_url, error=access_error)
            embed = EmbedTemplate.error(
                title="URL Not Accessible",
                description=f"❌ {access_error}\n\n"
                           f"**Please check:**\n"
                           f"• URL is correct and not expired\n"
                           f"• Image host is online\n"
                           f"• URL points directly to an image file\n"
                           f"• URL is publicly accessible"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Step 3: Find player
        self.logger.debug("Searching for player", player_name=player_name)
        players = await player_service.get_players_by_name(player_name, get_config().sba_season)

        if not players:
            self.logger.warning("Player not found", player_name=player_name)
            embed = EmbedTemplate.error(
                title="Player Not Found",
                description=f"❌ No player found matching `{player_name}` in the current season."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Handle multiple matches - try exact match
        player = None
        if len(players) == 1:
            player = players[0]
        else:
            # Try exact match
            for p in players:
                if p.name.lower() == player_name.lower():
                    player = p
                    break

            if player is None:
                # Multiple candidates, ask user to be more specific
                player_list = "\n".join([f"• {p.name} ({p.primary_position})" for p in players[:10]])
                embed = EmbedTemplate.info(
                    title="Multiple Players Found",
                    description=f"🔍 Multiple players match `{player_name}`:\n\n{player_list}\n\n"
                               f"Please use the exact name from autocomplete."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        self.logger.info("Player found", player_id=player.id, player_name=player.name)

        # Step 4: Check permissions
        has_permission, permission_error = await can_edit_player_image(
            interaction, player, get_config().sba_season, self.logger
        )

        if not has_permission:
            self.logger.warning(
                "Permission denied",
                user_id=interaction.user.id,
                player_id=player.id,
                error=permission_error
            )
            embed = EmbedTemplate.error(
                title="Permission Denied",
                description=f"❌ {permission_error}\n\n"
                           f"You can only update images for players on teams you own."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Step 5: Show preview with confirmation
        self.logger.debug("Creating preview embed")
        preview_embed = EmbedTemplate.create_base_embed(
            title=f"🖼️ Update {display_name} for {player.name}",
            description=f"Preview the new {display_name.lower()} below. Click **Confirm Update** to save this change.",
            color=EmbedColors.INFO
        )

        # Add current image info
        current_image = getattr(player, field_name, None)
        if current_image:
            preview_embed.add_field(
                name="Current Image",
                value="Will be replaced",
                inline=True
            )
        else:
            preview_embed.add_field(
                name="Current Image",
                value="None set",
                inline=True
            )

        # Add player info
        preview_embed.add_field(
            name="Player",
            value=f"{player.name} ({player.primary_position})",
            inline=True
        )

        if hasattr(player, 'team') and player.team:
            preview_embed.add_field(
                name="Team",
                value=player.team.abbrev,
                inline=True
            )

        # Set the new image as thumbnail for preview
        preview_embed.set_thumbnail(url=image_url)

        preview_embed.set_footer(text="This preview shows how the image will appear. Confirm to save.")

        # Create confirmation view
        confirm_view = ImageUpdateConfirmView(
            player=player,
            image_url=image_url,
            image_type=img_type,
            user_id=interaction.user.id
        )

        await interaction.followup.send(embed=preview_embed, view=confirm_view, ephemeral=True)

        # Wait for confirmation
        await confirm_view.wait()

        if not confirm_view.confirmed:
            self.logger.info("Image update cancelled by user", player_id=player.id)
            cancelled_embed = EmbedTemplate.info(
                title="Update Cancelled",
                description=f"No changes were made to {player.name}'s {display_name.lower()}."
            )
            await interaction.edit_original_response(embed=cancelled_embed, view=None)
            return

        # Step 6: Update database
        self.logger.info(
            "Updating player image",
            player_id=player.id,
            field=field_name,
            url_length=len(image_url)
        )

        update_data = {field_name: image_url}
        updated_player = await player_service.update_player(player.id, update_data)

        if updated_player is None:
            self.logger.error("Failed to update player", player_id=player.id)
            error_embed = EmbedTemplate.error(
                title="Update Failed",
                description="❌ An error occurred while updating the player's image. Please try again."
            )
            await interaction.edit_original_response(embed=error_embed, view=None)
            return

        # Step 7: Send success message
        self.logger.info(
            "Player image updated successfully",
            player_id=player.id,
            field=field_name,
            user_id=interaction.user.id
        )

        success_embed = EmbedTemplate.success(
            title="Image Updated Successfully!",
            description=f"**{display_name}** for **{player.name}** has been updated."
        )

        success_embed.add_field(
            name="Player",
            value=f"{player.name} ({player.primary_position})",
            inline=True
        )

        if hasattr(player, 'team') and player.team:
            success_embed.add_field(
                name="Team",
                value=player.team.abbrev,
                inline=True
            )

        success_embed.add_field(
            name="Image Type",
            value=display_name,
            inline=True
        )

        # Show the new image
        success_embed.set_thumbnail(url=image_url)

        success_embed.set_footer(text=f"Updated by {interaction.user.display_name}")

        await interaction.edit_original_response(embed=success_embed, view=None)


async def setup(bot: commands.Bot):
    """Load the image management commands cog."""
    await bot.add_cog(ImageCommands(bot))
