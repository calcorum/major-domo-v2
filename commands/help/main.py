"""
Help Commands slash commands for Discord Bot v2.0

Modern implementation for admin-created help topics.
"""
from typing import Optional, List
import discord
from discord import app_commands
from discord.ext import commands

from services.help_commands_service import (
    help_commands_service,
    HelpCommandNotFoundError,
    HelpCommandExistsError
)
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from views.embeds import EmbedTemplate, EmbedColors
from views.help_commands import (
    HelpCommandCreateModal,
    HelpCommandEditModal,
    HelpCommandDeleteConfirmView,
    HelpCommandListView,
    create_help_topic_embed
)
from constants import HELP_EDITOR_ROLE_NAME
from exceptions import BotException


async def help_topic_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    """Autocomplete for help topic names."""
    try:
        # Get topic names matching the current input
        topic_names = await help_commands_service.get_help_names_for_autocomplete(
            partial_name=current,
            limit=25
        )

        return [
            app_commands.Choice(name=name, value=name)
            for name in topic_names
        ]
    except Exception:
        # Return empty list on error to avoid breaking autocomplete
        return []


class HelpCommands(commands.Cog):
    """Help system slash command handlers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.HelpCommands')
        self.logger.info("HelpCommands cog initialized")

    def has_help_edit_permission(self, interaction: discord.Interaction) -> bool:
        """Check if user can edit help commands."""
        # Check if user is admin
        if interaction.user.guild_permissions.administrator:
            return True

        # Check if user has the Help Editor role
        role = discord.utils.get(interaction.guild.roles, name=HELP_EDITOR_ROLE_NAME)
        if role and role in interaction.user.roles:
            return True

        return False

    @app_commands.command(name="help", description="View help topics or list all available help")
    @app_commands.describe(topic="Help topic to view (optional - leave blank to see all topics)")
    @app_commands.autocomplete(topic=help_topic_autocomplete)
    @logged_command("/help")
    async def help_command(self, interaction: discord.Interaction, topic: Optional[str] = None):
        """View a help topic or list all available help topics."""
        await interaction.response.defer()

        try:
            if topic:
                # Get specific help topic
                help_cmd = await help_commands_service.get_help_by_name(topic)

                # Increment view count
                await help_commands_service.increment_view_count(topic)

                # Create and send embed
                embed = create_help_topic_embed(help_cmd)
                await interaction.followup.send(embed=embed)

            else:
                # List all help topics
                all_topics = await help_commands_service.get_all_help_topics()

                if not all_topics:
                    embed = EmbedTemplate.info(
                        title="Help Topics",
                        description="No help topics are currently available.\nAdmins can create topics using `/help-create`."
                    )
                    await interaction.followup.send(embed=embed)
                    return

                # Create list view
                list_view = HelpCommandListView(
                    help_commands=all_topics,
                    user_id=interaction.user.id
                )

                embed = list_view.get_embed()
                await interaction.followup.send(embed=embed, view=list_view)

        except HelpCommandNotFoundError:
            embed = EmbedTemplate.error(
                title="Topic Not Found",
                description=f"No help topic named `{topic}` exists.\nUse `/help` to see available topics."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error("Failed to show help",
                            topic=topic,
                            user_id=interaction.user.id,
                            error=e)
            embed = EmbedTemplate.error(
                title="Error",
                description="An error occurred while loading help. Please try again."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="help-create", description="Create a new help topic (admin/help editor only)")
    @logged_command("/help-create")
    async def help_create(self, interaction: discord.Interaction):
        """Create a new help topic using an interactive modal."""
        # Check permissions
        if not self.has_help_edit_permission(interaction):
            embed = EmbedTemplate.error(
                title="Permission Denied",
                description=f"Only administrators and users with the **{HELP_EDITOR_ROLE_NAME}** role can create help topics."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Show the creation modal
        modal = HelpCommandCreateModal()
        await interaction.response.send_modal(modal)

        # Wait for modal completion
        await modal.wait()

        if not modal.is_submitted:
            return

        try:
            # Create the help topic
            help_cmd = await help_commands_service.create_help(
                name=modal.result['name'],  # type: ignore
                title=modal.result['title'],  # type: ignore
                content=modal.result['content'],  # type: ignore
                creator_discord_id=interaction.user.id,
                category=modal.result.get('category')  # type: ignore
            )

            # Success embed
            embed = EmbedTemplate.success(
                title="Help Topic Created!",
                description=f"The help topic `/help {help_cmd.name}` has been created successfully."
            )

            embed.add_field(
                name="How users can access it",
                value=f"Type `/help {help_cmd.name}` to view this topic.",
                inline=False
            )

            embed.add_field(
                name="Management",
                value=f"Use `/help-edit {help_cmd.name}` to edit or `/help-delete {help_cmd.name}` to delete.",
                inline=False
            )

            # Try to send as followup
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except (discord.NotFound, discord.HTTPException):
                # If followup fails, try editing original
                try:
                    await interaction.edit_original_response(embed=embed)
                except (discord.NotFound, discord.HTTPException):
                    pass  # Silently fail if we can't send the confirmation

        except HelpCommandExistsError:
            embed = EmbedTemplate.error(
                title="Topic Already Exists",
                description=f"A help topic named `{modal.result['name']}` already exists.\nTry a different name."  # type: ignore
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error("Failed to create help topic",
                            topic_name=modal.result.get('name'),  # type: ignore
                            user_id=interaction.user.id,
                            error=e)
            embed = EmbedTemplate.error(
                title="Creation Failed",
                description="An error occurred while creating the help topic. Please try again."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="help-edit", description="Edit an existing help topic (admin/help editor only)")
    @app_commands.describe(topic="Help topic to edit")
    @app_commands.autocomplete(topic=help_topic_autocomplete)
    @logged_command("/help-edit")
    async def help_edit(self, interaction: discord.Interaction, topic: str):
        """Edit an existing help topic."""
        # Check permissions
        if not self.has_help_edit_permission(interaction):
            embed = EmbedTemplate.error(
                title="Permission Denied",
                description=f"Only administrators and users with the **{HELP_EDITOR_ROLE_NAME}** role can edit help topics."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            # Get the help topic
            help_cmd = await help_commands_service.get_help_by_name(topic)

            # Show edit modal
            modal = HelpCommandEditModal(help_cmd)
            await interaction.response.send_modal(modal)

            # Wait for modal completion
            await modal.wait()

            if not modal.is_submitted:
                return

            # Update the help topic
            updated_help = await help_commands_service.update_help(
                name=help_cmd.name,
                new_title=modal.result['title'],  # type: ignore
                new_content=modal.result['content'],  # type: ignore
                updater_discord_id=interaction.user.id,
                new_category=modal.result.get('category')  # type: ignore
            )

            # Success embed
            embed = EmbedTemplate.success(
                title="Help Topic Updated!",
                description=f"The help topic `/help {updated_help.name}` has been updated successfully."
            )

            # Try to send as followup
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except (discord.NotFound, discord.HTTPException):
                # If followup fails, try editing original
                try:
                    await interaction.edit_original_response(embed=embed)
                except (discord.NotFound, discord.HTTPException):
                    pass  # Silently fail if we can't send the confirmation

        except HelpCommandNotFoundError:
            embed = EmbedTemplate.error(
                title="Topic Not Found",
                description=f"No help topic named `{topic}` exists."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error("Failed to edit help topic",
                            topic=topic,
                            user_id=interaction.user.id,
                            error=e)
            embed = EmbedTemplate.error(
                title="Edit Failed",
                description="An error occurred while editing the help topic. Please try again."
            )
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="help-delete", description="Delete a help topic (admin/help editor only)")
    @app_commands.describe(topic="Help topic to delete")
    @app_commands.autocomplete(topic=help_topic_autocomplete)
    @logged_command("/help-delete")
    async def help_delete(self, interaction: discord.Interaction, topic: str):
        """Delete a help topic with confirmation."""
        # Check permissions
        if not self.has_help_edit_permission(interaction):
            embed = EmbedTemplate.error(
                title="Permission Denied",
                description=f"Only administrators and users with the **{HELP_EDITOR_ROLE_NAME}** role can delete help topics."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            # Get the help topic
            help_cmd = await help_commands_service.get_help_by_name(topic)

            # Show deletion confirmation
            embed = EmbedTemplate.warning(
                title="Delete Help Topic",
                description=f"Are you sure you want to delete `/help {help_cmd.name}`?"
            )

            embed.add_field(
                name="Title",
                value=help_cmd.title,
                inline=False
            )

            embed.add_field(
                name="Note",
                value=f"This topic has been viewed **{help_cmd.view_count}** times.\nThis is a soft delete - the topic can be restored later if needed.",
                inline=False
            )

            # Create confirmation view
            confirmation_view = HelpCommandDeleteConfirmView(
                help_cmd,
                user_id=interaction.user.id
            )

            await interaction.response.send_message(embed=embed, view=confirmation_view, ephemeral=True)
            await confirmation_view.wait()

            if confirmation_view.result:
                # User confirmed deletion - actually delete it
                await help_commands_service.delete_help(topic)
                self.logger.info("Help topic deleted",
                                topic=topic,
                                user_id=interaction.user.id)

        except HelpCommandNotFoundError:
            embed = EmbedTemplate.error(
                title="Topic Not Found",
                description=f"No help topic named `{topic}` exists."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error("Failed to delete help topic",
                            topic=topic,
                            user_id=interaction.user.id,
                            error=e)
            embed = EmbedTemplate.error(
                title="Error",
                description="An error occurred while trying to delete the help topic."
            )
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="help-list", description="Browse all help topics")
    @app_commands.describe(
        category="Filter by category (optional)",
        show_deleted="Show deleted topics (admin only, default: false)"
    )
    @logged_command("/help-list")
    async def help_list(
        self,
        interaction: discord.Interaction,
        category: Optional[str] = None,
        show_deleted: bool = False
    ):
        """Browse all help topics with optional category filter."""
        await interaction.response.defer()

        try:
            # Check permissions for show_deleted
            if show_deleted and not self.has_help_edit_permission(interaction):
                embed = EmbedTemplate.error(
                    title="Permission Denied",
                    description="Only administrators and help editors can view deleted topics."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Get help topics
            all_topics = await help_commands_service.get_all_help_topics(
                category=category,
                include_inactive=show_deleted
            )

            if not all_topics:
                embed = EmbedTemplate.info(
                    title="Help Topics",
                    description="No help topics found matching your criteria."
                )

                if category:
                    embed.add_field(
                        name="Tip",
                        value=f"Try viewing all categories by using `/help-list` without filters.",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Get Started",
                        value="Admins can create topics using `/help-create`.",
                        inline=False
                    )

                await interaction.followup.send(embed=embed)
                return

            # Create list view
            list_view = HelpCommandListView(
                help_commands=all_topics,
                user_id=interaction.user.id,
                category_filter=category
            )

            embed = list_view.get_embed()
            await interaction.followup.send(embed=embed, view=list_view)

        except Exception as e:
            self.logger.error("Failed to list help topics",
                            category=category,
                            show_deleted=show_deleted,
                            user_id=interaction.user.id,
                            error=e)
            embed = EmbedTemplate.error(
                title="Error",
                description="An error occurred while loading help topics. Please try again."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
