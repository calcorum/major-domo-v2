"""
Custom Command Views for Discord Bot v2.0

Interactive views and modals for the modern custom command system.
"""
from typing import Optional, List, Callable, Awaitable
import discord
from discord.ext import commands

from views.base import BaseView, ConfirmationView, PaginationView
from views.embeds import EmbedTemplate, EmbedColors
from views.modals import BaseModal
from models.custom_command import CustomCommand, CustomCommandSearchResult
from utils.logging import get_contextual_logger
from services.custom_commands_service import custom_commands_service
from exceptions import BotException


class CustomCommandCreateModal(BaseModal):
    """Modal for creating a new custom command."""
    
    def __init__(self, *, timeout: Optional[float] = 300.0):
        super().__init__(title="Create Custom Command", timeout=timeout)
        
        self.command_name = discord.ui.TextInput(
            label="Command Name",
            placeholder="Enter command name (2-32 characters, letters/numbers/dashes only)",
            required=True,
            min_length=2,
            max_length=32
        )
        
        self.command_content = discord.ui.TextInput(
            label="Command Response",
            placeholder="What should the command say when used?",
            style=discord.TextStyle.paragraph,
            required=True,
            min_length=1,
            max_length=2000
        )
        
        self.command_tags = discord.ui.TextInput(
            label="Tags (Optional)",
            placeholder="Comma-separated tags for categorization",
            required=False,
            max_length=200
        )
        
        self.add_item(self.command_name)
        self.add_item(self.command_content)
        self.add_item(self.command_tags)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission."""
        # Parse tags
        tags = []
        if self.command_tags.value:
            tags = [tag.strip() for tag in self.command_tags.value.split(',') if tag.strip()]
        
        # Store results
        self.result = {
            'name': self.command_name.value.strip(),
            'content': self.command_content.value.strip(),
            'tags': tags
        }
        
        self.is_submitted = True
        
        # Create preview embed
        embed = EmbedTemplate.info(
            title="Custom Command Preview",
            description="Here's how your command will look:"
        )
        
        embed.add_field(
            name=f"Command: `/cc {self.result['name']}`",
            value=self.result['content'][:1000] + ('...' if len(self.result['content']) > 1000 else ''),
            inline=False
        )
        
        if tags:
            embed.add_field(
                name="Tags",
                value=', '.join(tags),
                inline=False
            )
        
        embed.set_footer(text="Use the buttons below to confirm or cancel")
        
        # Create confirmation view for the creation
        confirmation_view = CustomCommandCreateConfirmationView(
            self.result,
            user_id=interaction.user.id
        )
        
        await interaction.response.send_message(embed=embed, view=confirmation_view, ephemeral=True)


class CustomCommandCreateConfirmationView(BaseView):
    """View for confirming custom command creation."""
    
    def __init__(self, command_data: dict, *, user_id: int, timeout: float = 180.0):
        super().__init__(timeout=timeout, user_id=user_id)
        self.command_data = command_data
    
    @discord.ui.button(label="Create Command", emoji="✅", style=discord.ButtonStyle.success, row=0)
    async def confirm_create(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm the command creation."""
        
        try:
            # Call the service to actually create the command
            created_command = await custom_commands_service.create_command(
                name=self.command_data['name'],
                content=self.command_data['content'],
                creator_discord_id=interaction.user.id,
                creator_username=interaction.user.name,
                creator_display_name=interaction.user.display_name,
                tags=self.command_data['tags']
            )
            
            embed = EmbedTemplate.success(
                title="Command Created",
                description=f"The command `/cc {self.command_data['name']}` has been created successfully!"
            )
            
        except BotException as e:
            embed = EmbedTemplate.error(
                title="Creation Failed",
                description=f"Failed to create command: {str(e)}"
            )
        except Exception as e:
            embed = EmbedTemplate.error(
                title="Unexpected Error",
                description="An unexpected error occurred while creating the command."
            )
        
        # Disable all buttons
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True  # type: ignore
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()
    
    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.secondary, row=0)
    async def cancel_create(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the command creation."""
        
        embed = EmbedTemplate.info(
            title="Creation Cancelled",
            description="No command was created."
        )
        
        # Disable all buttons
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True  # type: ignore
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


class CustomCommandEditModal(BaseModal):
    """Modal for editing an existing custom command."""
    
    def __init__(self, command: CustomCommand, *, timeout: Optional[float] = 300.0):
        super().__init__(title=f"Edit Command: {command.name}", timeout=timeout)
        self.original_command = command
        
        self.command_content = discord.ui.TextInput(
            label="Command Response",
            placeholder="What should the command say when used?",
            style=discord.TextStyle.paragraph,
            default=command.content,
            required=True,
            min_length=1,
            max_length=2000
        )
        
        self.command_tags = discord.ui.TextInput(
            label="Tags (Optional)",
            placeholder="Comma-separated tags for categorization",
            default=', '.join(command.tags) if command.tags else '',
            required=False,
            max_length=200
        )
        
        self.add_item(self.command_content)
        self.add_item(self.command_tags)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission."""
        # Parse tags
        tags = []
        if self.command_tags.value:
            tags = [tag.strip() for tag in self.command_tags.value.split(',') if tag.strip()]
        
        # Store results
        self.result = {
            'name': self.original_command.name,
            'content': self.command_content.value.strip(),
            'tags': tags
        }
        
        self.is_submitted = True
        
        # Create preview embed showing changes
        embed = EmbedTemplate.info(
            title="Command Edit Preview",
            description=f"Changes to `/cc {self.original_command.name}`:"
        )
        
        # Show content changes
        old_content = self.original_command.content[:500] + ('...' if len(self.original_command.content) > 500 else '')
        new_content = self.result['content'][:500] + ('...' if len(self.result['content']) > 500 else '')
        
        embed.add_field(
            name="Old Response",
            value=old_content,
            inline=False
        )
        
        embed.add_field(
            name="New Response",
            value=new_content,
            inline=False
        )
        
        # Show tag changes
        old_tags = ', '.join(self.original_command.tags) if self.original_command.tags else 'None'
        new_tags = ', '.join(tags) if tags else 'None'
        
        if old_tags != new_tags:
            embed.add_field(name="Old Tags", value=old_tags, inline=True)
            embed.add_field(name="New Tags", value=new_tags, inline=True)
        
        embed.set_footer(text="Use the buttons below to confirm or cancel")
        
        # Create confirmation view for the edit
        confirmation_view = CustomCommandEditConfirmationView(
            self.result,
            self.original_command,
            user_id=interaction.user.id
        )
        
        await interaction.response.send_message(embed=embed, view=confirmation_view, ephemeral=True)


class CustomCommandEditConfirmationView(BaseView):
    """View for confirming custom command edits."""
    
    def __init__(self, edit_data: dict, original_command: CustomCommand, *, user_id: int, timeout: float = 180.0):
        super().__init__(timeout=timeout, user_id=user_id)
        self.edit_data = edit_data
        self.original_command = original_command
    
    @discord.ui.button(label="Confirm Changes", emoji="✅", style=discord.ButtonStyle.success, row=0)
    async def confirm_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm the command edit."""
        
        try:
            # Call the service to actually update the command
            updated_command = await custom_commands_service.update_command(
                name=self.original_command.name,
                new_content=self.edit_data['content'],
                updater_discord_id=interaction.user.id,
                new_tags=self.edit_data['tags']
            )
            
            embed = EmbedTemplate.success(
                title="Command Updated",
                description=f"The command `/cc {self.edit_data['name']}` has been updated successfully!"
            )
            
        except BotException as e:
            embed = EmbedTemplate.error(
                title="Update Failed",
                description=f"Failed to update command: {str(e)}"
            )
        except Exception as e:
            embed = EmbedTemplate.error(
                title="Unexpected Error",
                description="An unexpected error occurred while updating the command."
            )
        
        # Disable all buttons
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True  # type: ignore
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()
    
    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.secondary, row=0)
    async def cancel_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the command edit."""
        
        embed = EmbedTemplate.info(
            title="Edit Cancelled",
            description=f"No changes were made to `/cc {self.original_command.name}`."
        )
        
        # Disable all buttons
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True  # type: ignore
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


class CustomCommandManagementView(BaseView):
    """View for managing a user's custom commands."""
    
    def __init__(
        self,
        commands: List[CustomCommand],
        user_id: int,
        *,
        timeout: float = 300.0
    ):
        super().__init__(timeout=timeout, user_id=user_id)
        self.commands = commands
        self.current_page = 0
        self.commands_per_page = 5
        
        self._update_buttons()
    
    def _update_buttons(self):
        """Update button states based on current page."""
        total_pages = max(1, (len(self.commands) + self.commands_per_page - 1) // self.commands_per_page)
        
        self.previous_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page >= total_pages - 1
        
        # Update page info
        self.page_info.label = f"Page {self.current_page + 1}/{total_pages}"
        
        # Update select options for current page
        self._update_select_options()
    
    def _update_select_options(self):
        """Update select dropdown options with commands from current page."""
        current_commands = self._get_current_commands()
        
        self.command_selector.options = [
            discord.SelectOption(
                label=cmd.name,
                description=cmd.content[:50] + ('...' if len(cmd.content) > 50 else ''),
                emoji="📝"
            )
            for cmd in current_commands
        ]
        
        # Disable select if no commands
        self.command_selector.disabled = len(current_commands) == 0
        
        # Update placeholder based on whether there are commands
        if len(current_commands) == 0:
            self.command_selector.placeholder = "No commands on this page"
        else:
            self.command_selector.placeholder = "Select a command to manage..."
    
    def _get_current_commands(self) -> List[CustomCommand]:
        """Get commands for current page."""
        start_idx = self.current_page * self.commands_per_page
        end_idx = start_idx + self.commands_per_page
        return self.commands[start_idx:end_idx]
    
    def _create_embed(self) -> discord.Embed:
        """Create embed for current page."""
        current_commands = self._get_current_commands()
        
        embed = EmbedTemplate.create_base_embed(
            title="🎮 Your Custom Commands",
            description=f"You have {len(self.commands)} custom command{'s' if len(self.commands) != 1 else ''}",
            color=EmbedColors.PRIMARY
        )
        
        if not current_commands:
            embed.add_field(
                name="No Commands",
                value="You haven't created any custom commands yet!\nUse `/cc-create` to make your first one.",
                inline=False
            )
        else:
            for cmd in current_commands:
                usage_info = f"Used {cmd.use_count} times"
                if cmd.last_used:
                    days_ago = cmd.days_since_last_use
                    if days_ago == 0:
                        usage_info += " (used today)"
                    elif days_ago == 1:
                        usage_info += " (used yesterday)"
                    else:
                        usage_info += f" (last used {days_ago} days ago)"
                
                content_preview = cmd.content[:100] + ('...' if len(cmd.content) > 100 else '')
                
                embed.add_field(
                    name=f"📝 {cmd.name}",
                    value=f"*{content_preview}*\n{usage_info}",
                    inline=False
                )
        
        # Add footer with instructions
        embed.set_footer(text="Use the dropdown to select a command to manage")
        
        return embed
    
    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary, row=0)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page."""
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        
        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True, row=0)
    async def page_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Page info (disabled button)."""
        pass
    
    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary, row=0)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page."""
        total_pages = max(1, (len(self.commands) + self.commands_per_page - 1) // self.commands_per_page)
        self.current_page = min(total_pages - 1, self.current_page + 1)
        self._update_buttons()
        
        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.select(
        placeholder="Select a command to manage...",
        min_values=1,
        max_values=1,
        row=1
    )
    async def command_selector(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle command selection."""
        selected_name = select.values[0]
        selected_command = next((cmd for cmd in self.commands if cmd.name == selected_name), None)
        
        if not selected_command:
            await interaction.response.send_message("❌ Command not found.", ephemeral=True)
            return
        
        # Create command management view
        management_view = SingleCommandManagementView(selected_command, self.user_id or interaction.user.id)
        embed = management_view.create_command_embed()
        
        await interaction.response.send_message(embed=embed, view=management_view, ephemeral=True)
    
    async def on_timeout(self):
        """Handle view timeout."""
        # Clear the select options to show it's expired
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                item.placeholder = "This menu has expired"
                item.disabled = True
            elif hasattr(item, 'disabled'):
                item.disabled = True # type: ignore
    
    def get_embed(self) -> discord.Embed:
        """Get the embed for this view."""
        # Update select options with current page commands
        current_commands = self._get_current_commands()
        
        self.command_selector.options = [
            discord.SelectOption(
                label=cmd.name,
                description=cmd.content[:50] + ('...' if len(cmd.content) > 50 else ''),
                emoji="📝"
            )
            for cmd in current_commands
        ]
        
        # Disable select if no commands
        self.command_selector.disabled = len(current_commands) == 0
        
        return self._create_embed()


class SingleCommandManagementView(BaseView):
    """View for managing a single custom command."""
    
    def __init__(self, command: CustomCommand, user_id: int, *, timeout: float = 180.0):
        super().__init__(timeout=timeout, user_id=user_id)
        self.command = command
    
    def create_command_embed(self) -> discord.Embed:
        """Create detailed embed for the command."""
        embed = EmbedTemplate.create_base_embed(
            title=f"📝 Command: {self.command.name}",
            description="Command details and management options",
            color=EmbedColors.INFO
        )
        
        # Content
        embed.add_field(
            name="Response",
            value=self.command.content,
            inline=False
        )
        
        # Statistics
        stats_text = f"**Uses:** {self.command.use_count}\n"
        stats_text += f"**Created:** <t:{int(self.command.created_at.timestamp())}:R>\n"
        
        if self.command.last_used:
            stats_text += f"**Last Used:** <t:{int(self.command.last_used.timestamp())}:R>\n"
        
        if self.command.updated_at:
            stats_text += f"**Last Updated:** <t:{int(self.command.updated_at.timestamp())}:R>\n"
        
        embed.add_field(
            name="Statistics",
            value=stats_text,
            inline=True
        )
        
        # Tags
        if self.command.tags:
            embed.add_field(
                name="Tags",
                value=', '.join(self.command.tags),
                inline=True
            )
        
        # Popularity score
        score = self.command.popularity_score
        if score > 0:
            embed.add_field(
                name="Popularity Score",
                value=f"{score:.1f}/10",
                inline=True
            )
        
        embed.set_footer(text="Use the buttons below to manage this command")
        
        return embed
    
    @discord.ui.button(label="Edit", emoji="✏️", style=discord.ButtonStyle.primary, row=0)
    async def edit_command(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit the command."""
        modal = CustomCommandEditModal(self.command)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Test", emoji="🧪", style=discord.ButtonStyle.secondary, row=0)
    async def test_command(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Test the command response."""
        embed = EmbedTemplate.create_base_embed(
            title=f"🧪 Test: /cc {self.command.name}",
            description="This is how your command would respond:",
            color=EmbedColors.SUCCESS
        )
        
        # embed.add_field(
        #     name="Response",
        #     value=self.command.content,
        #     inline=False
        # )
        
        embed.set_footer(text="This is just a preview - the command wasn't actually executed")
        
        await interaction.response.send_message(content=self.command.content, embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Delete", emoji="🗑️", style=discord.ButtonStyle.danger, row=0)
    async def delete_command(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete the command with confirmation."""
        embed = EmbedTemplate.warning(
            title="Delete Command",
            description=f"Are you sure you want to delete `/cc {self.command.name}`?"
        )
        
        embed.add_field(
            name="This action cannot be undone",
            value=f"The command has been used **{self.command.use_count}** times.",
            inline=False
        )
        
        # Create confirmation view
        confirmation_view = ConfirmationView(
            user_id=self.user_id or interaction.user.id,
            confirm_label="Delete",
            cancel_label="Keep It"
        )
        
        await interaction.response.send_message(embed=embed, view=confirmation_view, ephemeral=True)
        await confirmation_view.wait()
        
        if confirmation_view.result:
            # User confirmed deletion
            embed = EmbedTemplate.success(
                title="Command Deleted",
                description=f"The command `/cc {self.command.name}` has been deleted."
            )
            await interaction.edit_original_response(embed=embed, view=None)
        else:
            # User cancelled
            embed = EmbedTemplate.info(
                title="Deletion Cancelled",
                description=f"The command `/cc {self.command.name}` was not deleted."
            )
            await interaction.edit_original_response(embed=embed, view=None)


class CustomCommandListView(PaginationView):
    """Paginated view for listing custom commands with search results."""
    
    def __init__(
        self,
        search_result: CustomCommandSearchResult,
        user_id: Optional[int] = None,
        *,
        timeout: float = 300.0
    ):
        # Create embeds from search results
        embeds = self._create_embeds_from_search_result(search_result)
        
        super().__init__(
            pages=embeds,
            user_id=user_id,
            timeout=timeout,
            show_page_numbers=True
        )
        
        self.search_result = search_result
    
    def _create_embeds_from_search_result(self, search_result: CustomCommandSearchResult) -> List[discord.Embed]:
        """Create embeds from search result."""
        if not search_result.commands:
            embed = EmbedTemplate.create_base_embed(
                title="🔍 Custom Commands",
                description="No custom commands found matching your criteria.",
                color=EmbedColors.INFO
            )
            return [embed]
        
        embeds = []
        commands_per_page = 8
        
        for i in range(0, len(search_result.commands), commands_per_page):
            page_commands = search_result.commands[i:i + commands_per_page]
            
            embed = EmbedTemplate.create_base_embed(
                title="🎮 Custom Commands",
                description=f"Found {search_result.total_count} command{'s' if search_result.total_count != 1 else ''}",
                color=EmbedColors.PRIMARY
            )
            
            for cmd in page_commands:
                usage_text = f"Used {cmd.use_count} times"
                if cmd.last_used:
                    usage_text += f" • Last used <t:{int(cmd.last_used.timestamp())}:R>"
                
                content_preview = cmd.content[:80] + ('...' if len(cmd.content) > 80 else '')
                
                embed.add_field(
                    name=f"📝 {cmd.name}",
                    value=f"*{content_preview}*\nBy {cmd.creator.username} • {usage_text}",
                    inline=False
                )
            
            embeds.append(embed)
        
        return embeds


class CustomCommandSearchModal(BaseModal):
    """Modal for advanced custom command search."""
    
    def __init__(self, *, timeout: Optional[float] = 300.0):
        super().__init__(title="Search Custom Commands", timeout=timeout)
        
        self.name_search = discord.ui.TextInput(
            label="Command Name (Optional)",
            placeholder="Search for commands containing this text",
            required=False,
            max_length=100
        )
        
        self.creator_search = discord.ui.TextInput(
            label="Creator Username (Optional)", 
            placeholder="Search for commands by this creator",
            required=False,
            max_length=100
        )
        
        self.min_uses = discord.ui.TextInput(
            label="Minimum Uses (Optional)",
            placeholder="Show only commands used at least this many times",
            required=False,
            max_length=10
        )
        
        self.add_item(self.name_search)
        self.add_item(self.creator_search)
        self.add_item(self.min_uses)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle search form submission."""
        # Parse minimum uses
        min_uses = None
        if self.min_uses.value:
            try:
                min_uses = int(self.min_uses.value)
                if min_uses < 0:
                    min_uses = 0
            except ValueError:
                await interaction.response.send_message(
                    "❌ Minimum uses must be a valid number.",
                    ephemeral=True
                )
                return
        
        # Store search criteria
        self.result = {
            'name_contains': self.name_search.value.strip() if self.name_search.value else None,
            'creator_name': self.creator_search.value.strip() if self.creator_search.value else None,
            'min_uses': min_uses
        }
        
        self.is_submitted = True
        
        # Show confirmation
        embed = EmbedTemplate.create_base_embed(
            title="🔍 Search Submitted",
            description="Searching for custom commands...",
            color=EmbedColors.INFO
        )
        
        criteria = []
        if self.result['name_contains']:
            criteria.append(f"Name contains: '{self.result['name_contains']}'")
        if self.result['creator_name']:
            criteria.append(f"Created by: '{self.result['creator_name']}'")
        if self.result['min_uses'] is not None:
            criteria.append(f"Used at least {self.result['min_uses']} times")
        
        if criteria:
            embed.add_field(
                name="Search Criteria",
                value='\n'.join(criteria),
                inline=False
            )
        else:
            embed.description = "Showing all custom commands..."
        
        await interaction.response.send_message(embed=embed, ephemeral=True)