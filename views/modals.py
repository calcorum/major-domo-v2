"""
Modal Components for Discord Bot v2.0

Interactive forms and input dialogs for collecting user data.
"""
from typing import Optional, Callable, Awaitable, Dict, Any, List
import re

import discord
from discord.ext import commands

from .embeds import EmbedTemplate, EmbedColors
from utils.logging import get_contextual_logger


class BaseModal(discord.ui.Modal):
    """Base modal class with consistent error handling and validation."""
    
    def __init__(
        self,
        *,
        title: str,
        timeout: Optional[float] = 300.0,
        custom_id: Optional[str] = None
    ):
        kwargs = {"title": title, "timeout": timeout}
        if custom_id is not None:
            kwargs["custom_id"] = custom_id
        super().__init__(**kwargs)
        self.logger = get_contextual_logger(f'{__name__}.{self.__class__.__name__}')
        self.result: Optional[Dict[str, Any]] = None
        self.is_submitted = False
    
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle modal errors."""
        self.logger.error("Modal error occurred",
                         error=error,
                         modal_title=self.title,
                         user_id=interaction.user.id)
        
        try:
            embed = EmbedTemplate.error(
                title="Form Error",
                description="An error occurred while processing your form. Please try again."
            )
            
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error("Failed to send error message", error=e)
    
    def validate_input(self, field_name: str, value: str, validators: Optional[List[Callable[[str], bool]]] = None) -> tuple[bool, str]:
        """Validate input field with optional custom validators."""
        if not value.strip():
            return False, f"{field_name} cannot be empty."
        
        if validators:
            for validator in validators:
                try:
                    if not validator(value):
                        return False, f"Invalid {field_name} format."
                except Exception:
                    return False, f"Validation error for {field_name}."
        
        return True, ""


class PlayerSearchModal(BaseModal):
    """Modal for collecting detailed player search criteria."""
    
    def __init__(self, *, timeout: Optional[float] = 300.0):
        super().__init__(title="Player Search", timeout=timeout)
        
        self.player_name = discord.ui.TextInput(
            label="Player Name",
            placeholder="Enter player name (required)",
            required=True,
            max_length=100
        )
        
        self.position = discord.ui.TextInput(
            label="Position",
            placeholder="e.g., SS, OF, P (optional)",
            required=False,
            max_length=10
        )
        
        self.team = discord.ui.TextInput(
            label="Team",
            placeholder="Team abbreviation (optional)",
            required=False,
            max_length=5
        )
        
        self.season = discord.ui.TextInput(
            label="Season",
            placeholder="Season number (optional)",
            required=False,
            max_length=4
        )
        
        self.add_item(self.player_name)
        self.add_item(self.position)
        self.add_item(self.team)
        self.add_item(self.season)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission."""
        # Validate season if provided
        season_value = None
        if self.season.value:
            try:
                season_value = int(self.season.value)
                if season_value < 1 or season_value > 50:  # Reasonable bounds
                    raise ValueError("Season out of range")
            except ValueError:
                embed = EmbedTemplate.error(
                    title="Invalid Season",
                    description="Season must be a valid number between 1 and 50."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        # Store results
        self.result = {
            'name': self.player_name.value.strip(),
            'position': self.position.value.strip() if self.position.value else None,
            'team': self.team.value.strip().upper() if self.team.value else None,
            'season': season_value
        }
        
        self.is_submitted = True
        
        # Acknowledge submission
        embed = EmbedTemplate.info(
            title="Search Submitted",
            description=f"Searching for player: **{self.result['name']}**"
        )
        
        if self.result['position']:
            embed.add_field(name="Position", value=self.result['position'], inline=True)
        if self.result['team']:
            embed.add_field(name="Team", value=self.result['team'], inline=True)
        if self.result['season']:
            embed.add_field(name="Season", value=str(self.result['season']), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TeamSearchModal(BaseModal):
    """Modal for collecting team search criteria."""
    
    def __init__(self, *, timeout: Optional[float] = 300.0):
        super().__init__(title="Team Search", timeout=timeout)
        
        self.team_input = discord.ui.TextInput(
            label="Team Name or Abbreviation",
            placeholder="Enter team name or abbreviation",
            required=True,
            max_length=50
        )
        
        self.season = discord.ui.TextInput(
            label="Season",
            placeholder="Season number (optional)",
            required=False,
            max_length=4
        )
        
        self.add_item(self.team_input)
        self.add_item(self.season)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission."""
        # Validate season if provided
        season_value = None
        if self.season.value:
            try:
                season_value = int(self.season.value)
                if season_value < 1 or season_value > 50:
                    raise ValueError("Season out of range")
            except ValueError:
                embed = EmbedTemplate.error(
                    title="Invalid Season",
                    description="Season must be a valid number between 1 and 50."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        # Store results
        self.result = {
            'team': self.team_input.value.strip(),
            'season': season_value
        }
        
        self.is_submitted = True
        
        # Acknowledge submission
        embed = EmbedTemplate.info(
            title="Search Submitted",
            description=f"Searching for team: **{self.result['team']}**"
        )
        
        if self.result['season']:
            embed.add_field(name="Season", value=str(self.result['season']), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class FeedbackModal(BaseModal):
    """Modal for collecting user feedback."""
    
    def __init__(
        self, 
        *, 
        timeout: Optional[float] = 600.0,
        submit_callback: Optional[Callable[[Dict[str, Any]], Awaitable[bool]]] = None
    ):
        super().__init__(title="Submit Feedback", timeout=timeout)
        self.submit_callback = submit_callback
        
        self.feedback_type = discord.ui.TextInput(
            label="Feedback Type",
            placeholder="e.g., Bug Report, Feature Request, General",
            required=True,
            max_length=50
        )
        
        self.subject = discord.ui.TextInput(
            label="Subject",
            placeholder="Brief description of your feedback",
            required=True,
            max_length=100
        )
        
        self.description = discord.ui.TextInput(
            label="Description",
            placeholder="Detailed description of your feedback",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000
        )
        
        self.contact = discord.ui.TextInput(
            label="Contact Info (Optional)",
            placeholder="How to reach you for follow-up",
            required=False,
            max_length=100
        )
        
        self.add_item(self.feedback_type)
        self.add_item(self.subject)
        self.add_item(self.description)
        self.add_item(self.contact)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle feedback submission."""
        # Store results
        self.result = {
            'type': self.feedback_type.value.strip(),
            'subject': self.subject.value.strip(),
            'description': self.description.value.strip(),
            'contact': self.contact.value.strip() if self.contact.value else None,
            'user_id': interaction.user.id,
            'username': str(interaction.user),
            'submitted_at': discord.utils.utcnow()
        }
        
        self.is_submitted = True
        
        # Process feedback
        if self.submit_callback:
            try:
                success = await self.submit_callback(self.result)
                
                if success:
                    embed = EmbedTemplate.success(
                        title="Feedback Submitted",
                        description="Thank you for your feedback! We'll review it shortly."
                    )
                else:
                    embed = EmbedTemplate.error(
                        title="Submission Failed",
                        description="Failed to submit feedback. Please try again later."
                    )
            except Exception as e:
                self.logger.error("Feedback submission error", error=e)
                embed = EmbedTemplate.error(
                    title="Submission Error",
                    description="An error occurred while submitting feedback."
                )
        else:
            embed = EmbedTemplate.success(
                title="Feedback Received",
                description="Your feedback has been recorded."
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ConfigurationModal(BaseModal):
    """Modal for configuration settings with validation."""
    
    def __init__(
        self,
        current_config: Dict[str, Any],
        *,
        timeout: Optional[float] = 300.0,
        save_callback: Optional[Callable[[Dict[str, Any]], Awaitable[bool]]] = None
    ):
        super().__init__(title="Configuration Settings", timeout=timeout)
        self.current_config = current_config
        self.save_callback = save_callback
        
        # Add configuration fields (customize based on needs)
        self.setting1 = discord.ui.TextInput(
            label="Setting 1",
            placeholder="Enter value for setting 1",
            default=str(current_config.get('setting1', '')),
            required=False,
            max_length=100
        )
        
        self.setting2 = discord.ui.TextInput(
            label="Setting 2",
            placeholder="Enter value for setting 2",
            default=str(current_config.get('setting2', '')),
            required=False,
            max_length=100
        )
        
        self.add_item(self.setting1)
        self.add_item(self.setting2)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle configuration submission."""
        # Validate and store new configuration
        new_config = self.current_config.copy()
        
        if self.setting1.value:
            new_config['setting1'] = self.setting1.value.strip()
        
        if self.setting2.value:
            new_config['setting2'] = self.setting2.value.strip()
        
        self.result = new_config
        self.is_submitted = True
        
        # Save configuration
        if self.save_callback:
            try:
                success = await self.save_callback(new_config)
                
                if success:
                    embed = EmbedTemplate.success(
                        title="Configuration Saved",
                        description="Your configuration has been updated successfully."
                    )
                else:
                    embed = EmbedTemplate.error(
                        title="Save Failed",
                        description="Failed to save configuration. Please try again."
                    )
            except Exception as e:
                self.logger.error("Configuration save error", error=e)
                embed = EmbedTemplate.error(
                    title="Save Error",
                    description="An error occurred while saving configuration."
                )
        else:
            embed = EmbedTemplate.success(
                title="Configuration Updated",
                description="Configuration has been updated."
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CustomInputModal(BaseModal):
    """Flexible modal for custom input collection."""
    
    def __init__(
        self,
        title: str,
        fields: List[Dict[str, Any]],
        *,
        timeout: Optional[float] = 300.0,
        submit_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
    ):
        super().__init__(title=title, timeout=timeout)
        self.submit_callback = submit_callback
        self.fields_config = fields
        
        # Add text inputs based on field configuration
        for field in fields[:5]:  # Discord limit of 5 text inputs
            text_input = discord.ui.TextInput(
                label=field.get('label', 'Field'),
                placeholder=field.get('placeholder', ''),
                default=field.get('default', ''),
                required=field.get('required', False),
                max_length=field.get('max_length', 4000),
                style=getattr(discord.TextStyle, field.get('style', 'short'))
            )
            
            self.add_item(text_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle custom form submission."""
        # Collect all input values
        results = {}
        
        for i, item in enumerate(self.children):
            if isinstance(item, discord.ui.TextInput):
                field_config = self.fields_config[i] if i < len(self.fields_config) else {}
                field_key = field_config.get('key', f'field_{i}')
                
                # Apply validation if specified
                validators = field_config.get('validators', [])
                if validators:
                    is_valid, error_msg = self.validate_input(
                        field_config.get('label', 'Field'),
                        item.value,
                        validators
                    )
                    
                    if not is_valid:
                        embed = EmbedTemplate.error(
                            title="Validation Error",
                            description=error_msg
                        )
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                        return
                
                results[field_key] = item.value.strip() if item.value else None
        
        self.result = results
        self.is_submitted = True
        
        # Execute callback if provided
        if self.submit_callback:
            await self.submit_callback(results)
        else:
            embed = EmbedTemplate.success(
                title="Form Submitted",
                description="Your form has been submitted successfully."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


# Validation helper functions
def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_numeric(value: str) -> bool:
    """Validate numeric input."""
    try:
        float(value)
        return True
    except ValueError:
        return False


def validate_integer(value: str) -> bool:
    """Validate integer input."""
    try:
        int(value)
        return True
    except ValueError:
        return False


def validate_team_abbreviation(abbrev: str) -> bool:
    """Validate team abbreviation format."""
    return len(abbrev) >= 2 and len(abbrev) <= 5 and abbrev.isalpha()


def validate_season(season: str) -> bool:
    """Validate season number."""
    try:
        season_num = int(season)
        return 1 <= season_num <= 50
    except ValueError:
        return False