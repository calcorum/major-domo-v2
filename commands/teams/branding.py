"""
Team Branding Management Commands

Allows team owners to update their team's visual branding including colors and logos
for major league teams, minor league affiliates, and dice roll displays.
"""
import asyncio
import aiohttp
from typing import Optional, Tuple, Dict, List

import discord
from discord.ext import commands
from discord import app_commands

from config import get_config
from services import team_service
from models.team import Team
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.permissions import league_only
from views.embeds import EmbedTemplate, EmbedColors
from views.confirmations import ConfirmationView


# ============================================================================
# Validation Functions
# ============================================================================

def validate_hex_color(color: str) -> Tuple[bool, str, str]:
    """
    Validate hex color format.

    Args:
        color: Hex color string (with or without # prefix)

    Returns:
        Tuple of (is_valid, normalized_color, error_message)
        - is_valid: True if validation passed
        - normalized_color: Uppercase hex without # prefix
        - error_message: Empty if valid, error description if invalid
    """
    if not color:
        return True, "", ""

    # Strip # and whitespace
    color = color.strip().lstrip('#')

    # Check length
    if len(color) != 6:
        return False, "", "Color must be 6 characters (e.g., FF5733 or #FF5733)"

    # Check characters are valid hex
    if not all(c in '0123456789ABCDEFabcdef' for c in color):
        return False, "", "Color must contain only hex digits (0-9, A-F)"

    return True, color.upper(), ""


async def validate_image_url(url: str) -> Tuple[bool, str]:
    """
    Validate image URL format and accessibility.

    Args:
        url: Image URL to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if validation passed
        - error_message: Empty if valid, error description if invalid
    """
    if not url:
        return True, ""

    # Format validation
    if not url.startswith(('http://', 'https://')):
        return False, "URL must start with http:// or https://"

    valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
    # Check extension (handle query parameters)
    url_path = url.split('?')[0]  # Strip query params
    if not any(url_path.lower().endswith(ext) for ext in valid_extensions):
        return False, f"URL must end with {', '.join(valid_extensions)}"

    # Accessibility test
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    return False, f"URL returned status {resp.status} (not accessible)"

                content_type = resp.headers.get('Content-Type', '')
                if not content_type.startswith('image/'):
                    return False, "URL does not point to an image"

        return True, ""
    except asyncio.TimeoutError:
        return False, "URL request timed out (5 seconds)"
    except Exception as e:
        return False, f"Unable to access URL: {str(e)}"


# ============================================================================
# Branding Modal
# ============================================================================

class BrandingModal(discord.ui.Modal, title="Team Branding"):
    """Modal form for collecting team branding updates."""

    def __init__(
        self,
        cog,  # BrandingCommands instance
        ml_team: Team,
        mil_team: Optional[Team]
    ):
        """
        Initialize branding modal with current team values.

        Args:
            cog: BrandingCommands cog instance (for access to service and logger)
            ml_team: Major league team to update
            mil_team: Minor league team (optional)
        """
        super().__init__()
        self.cog = cog
        self.ml_team = ml_team
        self.mil_team = mil_team

        # Set placeholders to show current values
        current_ml_color = ml_team.color or "Not set"
        current_dice_color = ml_team.dice_color or "Not set"
        current_mil_color = mil_team.color if mil_team else "No MiL team"

        self.major_color.placeholder = f"Current: {current_ml_color}"
        self.dice_color.placeholder = f"Current: {current_dice_color}"
        self.minor_color.placeholder = f"Current: {current_mil_color}"

    major_color = discord.ui.TextInput(
        label="Major League Team Color",
        placeholder="FF5733 or #FF5733",
        max_length=7,
        required=False,
        style=discord.TextStyle.short
    )

    major_logo = discord.ui.TextInput(
        label="Major League Logo URL",
        placeholder="https://... (leave blank to keep current)",
        max_length=500,
        required=False,
        style=discord.TextStyle.short
    )

    minor_color = discord.ui.TextInput(
        label="Minor League Team Color",
        placeholder="33C3FF or #33C3FF",
        max_length=7,
        required=False,
        style=discord.TextStyle.short
    )

    minor_logo = discord.ui.TextInput(
        label="Minor League Logo URL",
        placeholder="https://... (leave blank to keep current)",
        max_length=500,
        required=False,
        style=discord.TextStyle.short
    )

    dice_color = discord.ui.TextInput(
        label="Dice Roll Color",
        placeholder="A6CE39 or #A6CE39",
        max_length=7,
        required=False,
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission and validation."""
        await interaction.response.defer()

        # Collect modal data
        modal_data = {
            'major_color': self.major_color.value.strip(),
            'major_logo': self.major_logo.value.strip(),
            'minor_color': self.minor_color.value.strip(),
            'minor_logo': self.minor_logo.value.strip(),
            'dice_color': self.dice_color.value.strip(),
        }

        # Check if any fields were filled
        if not any(modal_data.values()):
            embed = EmbedTemplate.info(
                "No Changes",
                "No branding changes were specified. All fields were left blank."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Validate and process
        await self.cog._process_branding_update(
            interaction,
            self.ml_team,
            self.mil_team,
            modal_data
        )


# ============================================================================
# Branding Commands Cog
# ============================================================================

class BrandingCommands(commands.Cog):
    """Team branding management command handlers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.BrandingCommands')
        self.logger.info("BrandingCommands cog initialized")

    @app_commands.command(name="branding", description="Update your team's colors and logos")
    @league_only()
    @logged_command("/branding")
    async def team_branding(self, interaction: discord.Interaction):
        """
        Update team branding including colors and logos.

        Team owners can update:
        - Major league team color and logo
        - Minor league team color and logo
        - Dice roll color
        """
        # Get current season
        config = get_config()
        season = config.sba_season

        # Verify user owns a team (must do this BEFORE responding to interaction)
        ml_team = await team_service.get_team_by_owner(interaction.user.id, season)

        if not ml_team:
            self.logger.info("User does not own a team", user_id=interaction.user.id)
            embed = EmbedTemplate.error(
                "Not a Team Owner",
                "You don't own a team in the current season."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Get minor league affiliate (if exists)
        mil_team = None
        try:
            mil_team = await ml_team.minor_league_affiliate()
            self.logger.info("Found minor league affiliate", mil_team_id=mil_team.id)
        except ValueError:
            # No MiL affiliate - this is OK
            self.logger.info("No minor league affiliate found for team", team_id=ml_team.id)

        # Show branding modal as immediate response
        modal = BrandingModal(
            cog=self,
            ml_team=ml_team,
            mil_team=mil_team
        )

        # Send modal as the interaction response
        await interaction.response.send_modal(modal)

    async def _process_branding_update(
        self,
        interaction: discord.Interaction,
        ml_team: Team,
        mil_team: Optional[Team],
        modal_data: Dict[str, str]
    ):
        """
        Process and validate branding update from modal.

        Args:
            interaction: Discord interaction
            ml_team: Major league team to update
            mil_team: Minor league team (optional)
            modal_data: Dictionary of modal field values
        """
        # Validate all inputs
        updates, errors = await self._validate_all_inputs(modal_data)

        # Show validation errors
        if errors:
            error_text = "\n".join(errors)
            embed = EmbedTemplate.error(
                "Validation Errors",
                f"{error_text}\n\n💡 **Tip:** Leave fields blank to keep current values"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Check if there are any actual updates
        if not updates['major'] and not updates['minor']:
            embed = EmbedTemplate.info(
                "No Changes",
                "No valid branding changes were specified."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Create preview embeds
        embeds = await self._create_preview_embeds(ml_team, mil_team, updates)

        # Show confirmation dialog
        confirmation_view = ConfirmationView(
            responders=[interaction.user],
            timeout=60.0,
            confirm_label="Apply Changes",
            cancel_label="Cancel"
        )

        confirmation_message = await interaction.followup.send(
            content="🎨 **Branding Preview** - Review and confirm changes:",
            embeds=embeds,
            view=confirmation_view,
            wait=True
        )

        await confirmation_view.wait()

        if not confirmation_view.confirmed:
            embed = EmbedTemplate.info(
                "Cancelled",
                "Branding changes were not applied."
            )
            await confirmation_message.edit(content=None, embeds=[embed], view=None)
            return

        # Apply updates
        await self._apply_branding_updates(interaction, ml_team, mil_team, updates, confirmation_message)

    async def _validate_all_inputs(
        self,
        modal_data: Dict[str, str]
    ) -> Tuple[Dict[str, Dict[str, str]], List[str]]:
        """
        Validate all modal inputs.

        Args:
            modal_data: Dictionary of modal field values

        Returns:
            Tuple of (updates_dict, error_list)
            - updates_dict: {'major': {...}, 'minor': {...}}
            - error_list: List of error messages
        """
        updates = {
            'major': {},
            'minor': {},
        }
        errors = []

        # Validate major league color
        if modal_data['major_color']:
            valid, normalized, error = validate_hex_color(modal_data['major_color'])
            if not valid:
                errors.append(f"**Major Team Color:** {error}")
            else:
                updates['major']['color'] = normalized

        # Validate dice color
        if modal_data['dice_color']:
            valid, normalized, error = validate_hex_color(modal_data['dice_color'])
            if not valid:
                errors.append(f"**Dice Roll Color:** {error}")
            else:
                updates['major']['dice_color'] = normalized

        # Validate minor league color
        if modal_data['minor_color']:
            valid, normalized, error = validate_hex_color(modal_data['minor_color'])
            if not valid:
                errors.append(f"**Minor Team Color:** {error}")
            else:
                updates['minor']['color'] = normalized

        # Collect URLs for concurrent validation
        url_validations = []

        if modal_data['major_logo']:
            url_validations.append(('major_logo', 'Major Team Logo', modal_data['major_logo']))

        if modal_data['minor_logo']:
            url_validations.append(('minor_logo', 'Minor Team Logo', modal_data['minor_logo']))

        # Validate all URLs concurrently
        if url_validations:
            tasks = [validate_image_url(url) for _, _, url in url_validations]
            results = await asyncio.gather(*tasks)

            for (field, label, url), (valid, error) in zip(url_validations, results):
                if not valid:
                    errors.append(f"**{label}:** {error}")
                else:
                    # Add to appropriate updates dict
                    if field == 'major_logo':
                        updates['major']['thumbnail'] = url
                    elif field == 'minor_logo':
                        updates['minor']['thumbnail'] = url

        return updates, errors

    async def _create_preview_embeds(
        self,
        ml_team: Team,
        mil_team: Optional[Team],
        updates: Dict[str, Dict[str, str]]
    ) -> List[discord.Embed]:
        """
        Create preview embeds showing branding changes.

        Args:
            ml_team: Major league team
            mil_team: Minor league team (optional)
            updates: Updates dictionary from validation

        Returns:
            List of 1-3 embeds showing previews
        """
        embeds = []

        # Major league preview
        if updates['major']:
            # Determine preview color (use new color if provided, else current)
            if 'color' in updates['major']:
                preview_color = int(updates['major']['color'], 16)
            elif ml_team.color:
                preview_color = int(ml_team.color, 16)
            else:
                preview_color = EmbedColors.PRIMARY

            # Determine preview logo
            preview_logo = updates['major'].get('thumbnail', ml_team.thumbnail)

            embed = EmbedTemplate.create_base_embed(
                title=f"{ml_team.lname} - Preview",
                description="Major League Team Branding",
                color=preview_color
            )

            if preview_logo:
                embed.set_thumbnail(url=preview_logo)

            # Add fields showing what's changing
            changes = []
            if 'color' in updates['major']:
                changes.append(f"**Team Color:** #{updates['major']['color']}")
            if 'thumbnail' in updates['major']:
                changes.append(f"**Team Logo:** Updated ✓")
            if 'dice_color' in updates['major']:
                changes.append(f"**Dice Color:** #{updates['major']['dice_color']}")

            if changes:
                embed.add_field(
                    name="Changes",
                    value="\n".join(changes),
                    inline=False
                )

            embeds.append(embed)

        # Minor league preview (if applicable)
        if mil_team and updates['minor']:
            # Determine preview color
            if 'color' in updates['minor']:
                preview_color = int(updates['minor']['color'], 16)
            elif mil_team.color:
                preview_color = int(mil_team.color, 16)
            else:
                preview_color = EmbedColors.PRIMARY

            # Determine preview logo
            preview_logo = updates['minor'].get('thumbnail', mil_team.thumbnail)

            embed = EmbedTemplate.create_base_embed(
                title=f"{mil_team.lname} - Preview",
                description="Minor League Team Branding",
                color=preview_color
            )

            if preview_logo:
                embed.set_thumbnail(url=preview_logo)

            # Add fields showing what's changing
            changes = []
            if 'color' in updates['minor']:
                changes.append(f"**Team Color:** #{updates['minor']['color']}")
            if 'thumbnail' in updates['minor']:
                changes.append(f"**Team Logo:** Updated ✓")

            if changes:
                embed.add_field(
                    name="Changes",
                    value="\n".join(changes),
                    inline=False
                )

            embeds.append(embed)

        # Dice color preview (if updated and different from team color)
        if 'dice_color' in updates.get('major', {}):
            dice_color_int = int(updates['major']['dice_color'], 16)

            dice_embed = EmbedTemplate.create_base_embed(
                title=f"{ml_team.lname} - Dice Color Preview",
                description="This color will be used for dice rolls in gameplay",
                color=dice_color_int
            )

            dice_embed.add_field(
                name="Dice Color",
                value=f"#{updates['major']['dice_color']}",
                inline=False
            )

            embeds.append(dice_embed)

        return embeds

    async def _apply_branding_updates(
        self,
        interaction: discord.Interaction,
        ml_team: Team,
        mil_team: Optional[Team],
        updates: Dict[str, Dict[str, str]],
        confirmation_message
    ):
        """
        Apply branding updates to database and Discord.

        Args:
            interaction: Discord interaction
            ml_team: Major league team to update
            mil_team: Minor league team (optional)
            updates: Updates dictionary from validation
            confirmation_message: The message to update with results
        """
        role_updated = False
        role_error = None

        # Update major league team
        if updates['major']:
            self.logger.info("Updating major league team", team_id=ml_team.id, updates=updates['major'])
            updated_ml = await team_service.update_team(ml_team.id, updates['major'])

            if not updated_ml:
                self.logger.error("Failed to update major league team", team_id=ml_team.id)
                embed = EmbedTemplate.error(
                    "Update Failed",
                    "Failed to update major league team branding. Please try again."
                )
                await confirmation_message.edit(content=None, embeds=[embed], view=None)
                return

            # Update Discord role color (non-blocking)
            if 'color' in updates['major']:
                role_updated, role_error = await self._update_discord_role_color(
                    interaction,
                    ml_team,
                    updates['major']['color']
                )

        # Update minor league team (if applicable)
        if mil_team and updates['minor']:
            self.logger.info("Updating minor league team", team_id=mil_team.id, updates=updates['minor'])
            await team_service.update_team(mil_team.id, updates['minor'])

        # Create success message
        success_message = self._format_success_message(updates, role_updated, role_error)

        embed = EmbedTemplate.success(
            "Branding Updated",
            success_message
        )

        await confirmation_message.edit(content=None, embeds=[embed], view=None)

    async def _update_discord_role_color(
        self,
        interaction: discord.Interaction,
        team: Team,
        hex_color: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Update Discord role color for team (non-blocking).

        Args:
            interaction: Discord interaction
            team: Team whose role to update
            hex_color: New hex color (without # prefix)

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Find role by team long name
            role = discord.utils.get(
                interaction.guild.roles,
                name=team.lname
            )

            if not role:
                self.logger.warning("Discord role not found", team_name=team.lname)
                return False, "Discord role not found"

            # Convert hex to int
            color_int = int(hex_color, 16)

            # Update role
            await role.edit(colour=color_int)

            self.logger.info("Discord role color updated", team_name=team.lname, color=hex_color)
            return True, None

        except discord.Forbidden:
            self.logger.warning("Missing permissions to edit role", team_name=team.lname)
            return False, "Missing permissions to edit role"
        except Exception as e:
            self.logger.warning(f"Failed to update Discord role color: {e}", team_name=team.lname)
            return False, str(e)

    def _format_success_message(
        self,
        updates: Dict[str, Dict[str, str]],
        role_updated: bool,
        role_error: Optional[str]
    ) -> str:
        """
        Format success message showing all applied changes.

        Args:
            updates: Updates dictionary
            role_updated: Whether Discord role was updated
            role_error: Error message if role update failed

        Returns:
            Formatted success message string
        """
        lines = []

        # Major league updates
        if updates['major']:
            lines.append("**Major League:**")
            if 'color' in updates['major']:
                lines.append(f"• Color: #{updates['major']['color']} ✅")
            if 'thumbnail' in updates['major']:
                lines.append(f"• Logo: Updated ✅")
            if 'dice_color' in updates['major']:
                lines.append(f"• Dice Color: #{updates['major']['dice_color']} ✅")

            # Discord role status
            if 'color' in updates['major']:
                if role_updated:
                    lines.append(f"• Discord role: Updated ✅")
                else:
                    lines.append(f"• Discord role: Failed ({role_error}) ⚠️")

        # Minor league updates
        if updates['minor']:
            lines.append("\n**Minor League:**")
            if 'color' in updates['minor']:
                lines.append(f"• Color: #{updates['minor']['color']} ✅")
            if 'thumbnail' in updates['minor']:
                lines.append(f"• Logo: Updated ✅")

        # Warning about role update failure
        if role_error:
            lines.append("\n⚠️ **Note:** Discord role color update failed, but database was updated successfully.")

        return "\n".join(lines)


async def setup(bot: commands.Bot):
    """Load the branding commands cog."""
    await bot.add_cog(BrandingCommands(bot))
