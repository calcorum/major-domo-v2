"""
Custom Commands slash commands for Discord Bot v2.0

Modern implementation with interactive views and excellent UX.
"""
from typing import Optional, List
import discord
from discord import app_commands
from discord.ext import commands

from services.custom_commands_service import (
    custom_commands_service,
    CustomCommandNotFoundError,
    CustomCommandExistsError,
    CustomCommandPermissionError
)
from models.custom_command import CustomCommandSearchFilters
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from views.embeds import EmbedTemplate, EmbedColors
from views.custom_commands import (
    CustomCommandCreateModal,
    CustomCommandEditModal,
    CustomCommandManagementView,
    CustomCommandListView,
    CustomCommandSearchModal,
    SingleCommandManagementView
)
from exceptions import BotException


class CustomCommandsCommands(commands.Cog):
    """Custom commands slash command handlers."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.CustomCommandsCommands')
        self.logger.info("CustomCommandsCommands cog initialized")
    
    @app_commands.command(name="cc", description="Execute a custom command")
    @app_commands.describe(name="Name of the custom command to execute")
    @logged_command("/cc")
    async def execute_custom_command(self, interaction: discord.Interaction, name: str):
        """Execute a custom command."""
        await interaction.response.defer()
        
        try:
            # Execute the command and get response
            command, response_content = await custom_commands_service.execute_command(name)
            
        except CustomCommandNotFoundError:
            embed = EmbedTemplate.error(
                title="Command Not Found",
                description=f"No custom command named `{name}` exists.\nUse `/cc-list` to see available commands."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
            
        # # Create embed with the response
        # embed = EmbedTemplate.create_base_embed(
        #     title=f"🎮 {command.name}",
        #     description=response_content,
        #     color=EmbedColors.PRIMARY
        # )
        
        # # Add creator info in footer
        # embed.set_footer(
        #     text=f"Created by {command.creator.username} • Used {command.use_count} times"
        # )
        
        await interaction.followup.send(content=response_content)
    
    @execute_custom_command.autocomplete('name')
    async def execute_custom_command_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        """Provide autocomplete for custom command names."""
        try:
            # Get command names matching the current input
            command_names = await custom_commands_service.get_command_names_for_autocomplete(
                partial_name=current,
                limit=25
            )
            
            return [
                app_commands.Choice(name=name, value=name)
                for name in command_names
            ]
        except Exception:
            # Return empty list on error
            return []
    
    @app_commands.command(name="cc-create", description="Create a new custom command")
    @logged_command("/cc-create")
    async def create_custom_command(self, interaction: discord.Interaction):
        """Create a new custom command using an interactive modal."""
        # Show the creation modal
        modal = CustomCommandCreateModal()
        await interaction.response.send_modal(modal)
        
        # Wait for modal completion
        await modal.wait()
        
        if not modal.is_submitted:
            return
        
        try:
            # Create the command
            command = await custom_commands_service.create_command(
                name=modal.result['name'], # type: ignore
                content=modal.result['content'], # pyright: ignore[reportOptionalSubscript]
                creator_discord_id=interaction.user.id,
                creator_username=interaction.user.name,
                creator_display_name=interaction.user.display_name,
                tags=modal.result.get('tags')
            )
            
            # Success embed
            embed = EmbedTemplate.success(
                title="✅ Custom Command Created!",
                description=f"Your command `/cc {command.name}` has been created successfully."
            )
            
            embed.add_field(
                name="How to use it",
                value=f"Type `/cc {command.name}` to execute your command.",
                inline=False
            )
            
            embed.add_field(
                name="Management",
                value="Use `/cc-mine` to view and manage all your commands.",
                inline=False
            )
            
            # Try to get the original interaction for editing
            try:
                # Get the interaction that triggered the modal
                original_response = await interaction.original_response()
                await interaction.edit_original_response(embed=embed, view=None)
            except (discord.NotFound, discord.HTTPException):
                # If we can't edit the original, send a followup
                await interaction.followup.send(embed=embed, ephemeral=True)
        
        except CustomCommandExistsError:
            embed = EmbedTemplate.error(
                title="Command Already Exists",
                description=f"A command named `{modal.result['name']}` already exists.\nTry a different name." # pyright: ignore[reportOptionalSubscript]
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            self.logger.error("Failed to create custom command",
                            command_name=modal.result.get('name'), # pyright: ignore[reportOptionalMemberAccess]
                            user_id=interaction.user.id,
                            error=e)
            embed = EmbedTemplate.error(
                title="Creation Failed",
                description="An error occurred while creating your command. Please try again."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="cc-edit", description="Edit one of your custom commands")
    @app_commands.describe(name="Name of the command to edit")
    @logged_command("/cc-edit")
    async def edit_custom_command(self, interaction: discord.Interaction, name: str):
        """Edit an existing custom command."""
        try:
            # Get the command
            command = await custom_commands_service.get_command_by_name(name)
            
            # Check if user owns the command
            if command.creator.discord_id != interaction.user.id: # type: ignore  / get_command returns or raises
                embed = EmbedTemplate.error(
                    title="Permission Denied",
                    description="You can only edit commands that you created."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Show edit modal
            modal = CustomCommandEditModal(command)
            await interaction.response.send_modal(modal)
            
            # Wait for modal completion
            await modal.wait()
            
            if not modal.is_submitted:
                return
            
            # Update the command
            updated_command = await custom_commands_service.update_command(
                name=command.name,
                new_content=modal.result['content'],
                updater_discord_id=interaction.user.id,
                new_tags=modal.result.get('tags')
            )
            
            # Success embed
            embed = EmbedTemplate.success(
                title="✅ Command Updated!",
                description=f"Your command `/cc {updated_command.name}` has been updated successfully."
            )
            
            # Try to edit the original response
            try:
                await interaction.edit_original_response(embed=embed, view=None)
            except (discord.NotFound, discord.HTTPException):
                await interaction.followup.send(embed=embed, ephemeral=True)
        
        except CustomCommandNotFoundError:
            embed = EmbedTemplate.error(
                title="Command Not Found",
                description=f"No custom command named `{name}` exists."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        except Exception as e:
            self.logger.error("Failed to edit custom command",
                            command_name=name,
                            user_id=interaction.user.id,
                            error=e)
            embed = EmbedTemplate.error(
                title="Edit Failed",
                description="An error occurred while editing your command. Please try again."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @edit_custom_command.autocomplete('name')
    async def edit_custom_command_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for commands owned by the user."""
        try:
            # Get user's commands
            search_result = await custom_commands_service.get_commands_by_creator(
                creator_discord_id=interaction.user.id,
                page=1,
                page_size=25
            )
            
            # Filter by current input
            matching_commands = [
                cmd for cmd in search_result.commands
                if current.lower() in cmd.name.lower()
            ]
            
            return [
                app_commands.Choice(name=cmd.name, value=cmd.name)
                for cmd in matching_commands[:25]
            ]
        except Exception:
            return []
    
    @app_commands.command(name="cc-delete", description="Delete one of your custom commands")
    @app_commands.describe(name="Name of the command to delete")
    @logged_command("/cc-delete")
    async def delete_custom_command(self, interaction: discord.Interaction, name: str):
        """Delete a custom command with confirmation."""
        try:
            # Get the command
            command = await custom_commands_service.get_command_by_name(name)
            
            # Check if user owns the command
            if command.creator.discord_id != interaction.user.id:
                embed = EmbedTemplate.error(
                    title="Permission Denied",
                    description="You can only delete commands that you created."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Show command management view for deletion
            management_view = SingleCommandManagementView(command, interaction.user.id)
            embed = management_view.create_command_embed()
            
            # Override the embed title to emphasize deletion
            embed.title = f"🗑️ Delete Command: {command.name}"
            embed.color = EmbedColors.WARNING
            embed.description = "⚠️ Are you sure you want to delete this command?"
            
            await interaction.response.send_message(embed=embed, view=management_view, ephemeral=True)
        
        except CustomCommandNotFoundError:
            embed = EmbedTemplate.error(
                title="Command Not Found",
                description=f"No custom command named `{name}` exists."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        except Exception as e:
            self.logger.error("Failed to show delete interface for custom command",
                            command_name=name,
                            user_id=interaction.user.id,
                            error=e)
            embed = EmbedTemplate.error(
                title="Error",
                description="An error occurred while loading the command. Please try again."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @delete_custom_command.autocomplete('name')
    async def delete_custom_command_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for commands owned by the user."""
        # NOTE: Originally was: return await self.edit_custom_command_autocomplete(interaction, current)
        # But Pylance complained about "Expected 1 positional argument" so duplicated logic instead
        try:
            # Get user's commands
            search_result = await custom_commands_service.get_commands_by_creator(
                creator_discord_id=interaction.user.id,
                page=1,
                page_size=25
            )
            
            # Filter by current input
            matching_commands = [
                cmd for cmd in search_result.commands
                if current.lower() in cmd.name.lower()
            ]
            
            return [
                app_commands.Choice(name=cmd.name, value=cmd.name)
                for cmd in matching_commands[:25]
            ]
        except Exception:
            return []
    
    @app_commands.command(name="cc-mine", description="View and manage your custom commands")
    @logged_command("/cc-mine")
    async def my_custom_commands(self, interaction: discord.Interaction):
        """Show user's custom commands with management interface."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get user's commands
            search_result = await custom_commands_service.get_commands_by_creator(
                creator_discord_id=interaction.user.id,
                page=1,
                page_size=100  # Get all commands for management
            )
            
            if not search_result.commands:
                embed = EmbedTemplate.info(
                    title="📝 Your Custom Commands",
                    description="You haven't created any custom commands yet!"
                )
                
                embed.add_field(
                    name="Get Started",
                    value="Use `/cc-create` to create your first custom command.",
                    inline=False
                )
                
                embed.add_field(
                    name="Explore",
                    value="Use `/cc-list` to see what commands others have created.",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed)
                return
            
            # Create management view
            management_view = CustomCommandManagementView(
                commands=search_result.commands,
                user_id=interaction.user.id
            )
            
            embed = management_view.get_embed()
            await interaction.followup.send(embed=embed, view=management_view)
        
        except Exception as e:
            self.logger.error("Failed to load user's custom commands",
                            user_id=interaction.user.id,
                            error=e)
            embed = EmbedTemplate.error(
                title="Load Failed",
                description="An error occurred while loading your commands. Please try again."
            )
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="cc-list", description="Browse all custom commands")
    @app_commands.describe(
        creator="Filter by creator username",
        search="Search in command names",
        popular="Show only popular commands (10+ uses)"
    )
    @logged_command("/cc-list")
    async def list_custom_commands(
        self,
        interaction: discord.Interaction,
        creator: Optional[str] = None,
        search: Optional[str] = None,
        popular: bool = False
    ):
        """Browse custom commands with filtering options."""
        await interaction.response.defer()
        
        try:
            # Build search filters
            filters = CustomCommandSearchFilters(
                name_contains=search,
                creator_name=creator,
                min_uses=10 if popular else None,
                sort_by='popularity' if popular else 'name',
                sort_desc=popular,
                page=1,
                page_size=50
            )
            
            # Search for commands
            search_result = await custom_commands_service.search_commands(filters)
            
            # Create list view
            list_view = CustomCommandListView(
                search_result=search_result,
                user_id=interaction.user.id
            )
            
            embed = list_view.get_current_embed()
            
            # Add search info to embed
            search_info = []
            if creator:
                search_info.append(f"Creator: {creator}")
            if search:
                search_info.append(f"Name contains: {search}")
            if popular:
                search_info.append("Popular commands only")
            
            if search_info:
                embed.add_field(
                    name="🔍 Filters Applied",
                    value=" • ".join(search_info),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, view=list_view)
        
        except Exception as e:
            self.logger.error("Failed to list custom commands",
                            user_id=interaction.user.id,
                            error=e)
            embed = EmbedTemplate.error(
                title="Search Failed",
                description="An error occurred while searching for commands. Please try again."
            )
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="cc-search", description="Advanced search for custom commands")
    @logged_command("/cc-search")
    async def search_custom_commands(self, interaction: discord.Interaction):
        """Advanced search for custom commands using a modal."""
        # Show search modal
        modal = CustomCommandSearchModal()
        await interaction.response.send_modal(modal)
        
        # Wait for modal completion
        await modal.wait()
        
        if not modal.is_submitted:
            return
        
        try:
            # Build search filters from modal results
            filters = CustomCommandSearchFilters(
                name_contains=modal.result.get('name_contains'),
                creator_name=modal.result.get('creator_name'),
                min_uses=modal.result.get('min_uses'),
                sort_by='popularity',
                sort_desc=True,
                page=1,
                page_size=50
            )
            
            # Search for commands
            search_result = await custom_commands_service.search_commands(filters)
            
            # Create list view
            list_view = CustomCommandListView(
                search_result=search_result,
                user_id=interaction.user.id
            )
            
            embed = list_view.get_current_embed()
            
            # Try to edit the original response
            try:
                await interaction.edit_original_response(embed=embed, view=list_view)
            except (discord.NotFound, discord.HTTPException):
                await interaction.followup.send(embed=embed, view=list_view)
        
        except Exception as e:
            self.logger.error("Failed to search custom commands",
                            user_id=interaction.user.id,
                            error=e)
            embed = EmbedTemplate.error(
                title="Search Failed",
                description="An error occurred while searching. Please try again."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="cc-info", description="Get detailed information about a custom command")
    @app_commands.describe(name="Name of the command to get info about")
    @logged_command("/cc-info")
    async def info_custom_command(self, interaction: discord.Interaction, name: str):
        """Get detailed information about a custom command."""
        await interaction.response.defer()
        
        try:
            # Get the command
            command = await custom_commands_service.get_command_by_name(name)
            
            # Create detailed info embed
            embed = EmbedTemplate.create_base_embed(
                title=f"📊 Command Info: {command.name}",
                description="Detailed information about this custom command",
                color=EmbedColors.INFO
            )
            
            # Basic info
            embed.add_field(
                name="Response",
                value=command.content[:500] + ('...' if len(command.content) > 500 else ''),
                inline=False
            )
            
            # Creator info
            creator_text = f"**Username:** {command.creator.username}\n"
            if command.creator.display_name:
                creator_text += f"**Display Name:** {command.creator.display_name}\n"
            creator_text += f"**Total Commands:** {command.creator.active_commands}"
            
            embed.add_field(
                name="👤 Creator",
                value=creator_text,
                inline=True
            )
            
            # Usage statistics
            stats_text = f"**Total Uses:** {command.use_count}\n"
            stats_text += f"**Popularity Score:** {command.popularity_score:.1f}/10\n"
            stats_text += f"**Created:** <t:{int(command.created_at.timestamp())}:R>\n"
            
            if command.last_used:
                stats_text += f"**Last Used:** <t:{int(command.last_used.timestamp())}:R>\n"
            else:
                stats_text += "**Last Used:** Never\n"
            
            if command.updated_at:
                stats_text += f"**Last Updated:** <t:{int(command.updated_at.timestamp())}:R>"
            
            embed.add_field(
                name="📈 Statistics",
                value=stats_text,
                inline=True
            )
            
            # Tags
            if command.tags:
                embed.add_field(
                    name="🏷️ Tags",
                    value=', '.join(command.tags),
                    inline=False
                )
            
            # Usage instructions
            embed.add_field(
                name="💡 How to Use",
                value=f"Type `/cc {command.name}` to execute this command",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
        
        except CustomCommandNotFoundError:
            embed = EmbedTemplate.error(
                title="Command Not Found",
                description=f"No custom command named `{name}` exists.\nUse `/cc-list` to see available commands."
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            self.logger.error("Failed to get custom command info",
                            command_name=name,
                            user_id=interaction.user.id,
                            error=e)
            embed = EmbedTemplate.error(
                title="Info Failed",
                description="An error occurred while getting command information."
            )
            await interaction.followup.send(embed=embed)
    
    @info_custom_command.autocomplete('name')
    async def info_custom_command_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for all command names."""
        # NOTE: Originally was: return await self.execute_custom_command_autocomplete(interaction, current)
        # But Pylance complained about "Expected 1 positional argument" so duplicated logic instead
        try:
            # Get command names matching the current input
            command_names = await custom_commands_service.get_command_names_for_autocomplete(
                partial_name=current,
                limit=25
            )
            
            return [
                app_commands.Choice(name=name, value=name)
                for name in command_names
            ]
        except Exception:
            # Return empty list on error
            return []