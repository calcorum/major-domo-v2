"""
Help Command Views for Discord Bot v2.0

Interactive views and modals for the custom help system.
"""
from typing import Optional, List
import discord

from views.base import BaseView, ConfirmationView, PaginationView
from views.embeds import EmbedTemplate, EmbedColors
from views.modals import BaseModal
from models.help_command import HelpCommand, HelpCommandSearchResult
from utils.logging import get_contextual_logger
from exceptions import BotException


class HelpCommandCreateModal(BaseModal):
    """Modal for creating a new help topic."""

    def __init__(self, *, timeout: Optional[float] = 300.0):
        super().__init__(title="Create Help Topic", timeout=timeout)

        self.topic_name = discord.ui.TextInput(
            label="Topic Name",
            placeholder="e.g., trading-rules (2-32 chars, letters/numbers/dashes)",
            required=True,
            min_length=2,
            max_length=32
        )

        self.topic_title = discord.ui.TextInput(
            label="Display Title",
            placeholder="e.g., Trading Rules & Guidelines",
            required=True,
            min_length=1,
            max_length=200
        )

        self.topic_category = discord.ui.TextInput(
            label="Category (Optional)",
            placeholder="e.g., rules, guides, resources, info, faq",
            required=False,
            max_length=50
        )

        self.topic_content = discord.ui.TextInput(
            label="Content",
            placeholder="Help content (markdown supported, max 4000 chars)",
            style=discord.TextStyle.paragraph,
            required=True,
            min_length=1,
            max_length=4000
        )

        self.add_item(self.topic_name)
        self.add_item(self.topic_title)
        self.add_item(self.topic_category)
        self.add_item(self.topic_content)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission."""
        import re

        # Validate topic name format
        name = self.topic_name.value.strip().lower()
        if not re.match(r'^[a-z0-9_-]+$', name):
            embed = EmbedTemplate.error(
                title="Invalid Topic Name",
                description=(
                    f"Topic name `{self.topic_name.value}` contains invalid characters.\n\n"
                    "**Allowed:** lowercase letters, numbers, dashes, and underscores only.\n"
                    "**Examples:** `trading-rules`, `how_to_draft`, `faq1`\n\n"
                    "Please try again with a valid name."
                )
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Validate category format if provided
        category = self.topic_category.value.strip().lower() if self.topic_category.value else None
        if category and not re.match(r'^[a-z0-9_-]+$', category):
            embed = EmbedTemplate.error(
                title="Invalid Category",
                description=(
                    f"Category `{self.topic_category.value}` contains invalid characters.\n\n"
                    "**Allowed:** lowercase letters, numbers, dashes, and underscores only.\n"
                    "**Examples:** `rules`, `guides`, `faq`\n\n"
                    "Please try again with a valid category."
                )
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Store results
        self.result = {
            'name': name,
            'title': self.topic_title.value.strip(),
            'content': self.topic_content.value.strip(),
            'category': category
        }

        self.is_submitted = True

        # Create preview embed
        embed = EmbedTemplate.info(
            title="Help Topic Preview",
            description="Here's how your help topic will look:"
        )

        embed.add_field(
            name="Name",
            value=f"`/help {self.result['name']}`",
            inline=True
        )

        embed.add_field(
            name="Category",
            value=self.result['category'] or "None",
            inline=True
        )

        embed.add_field(
            name="Title",
            value=self.result['title'],
            inline=False
        )

        # Show content preview (truncated if too long)
        content_preview = self.result['content'][:500] + ('...' if len(self.result['content']) > 500 else '')
        embed.add_field(
            name="Content",
            value=content_preview,
            inline=False
        )

        embed.set_footer(text="Creating this help topic will make it available to all server members")

        await interaction.response.send_message(embed=embed, ephemeral=True)


class HelpCommandEditModal(BaseModal):
    """Modal for editing an existing help topic."""

    def __init__(self, help_command: HelpCommand, *, timeout: Optional[float] = 300.0):
        super().__init__(title=f"Edit: {help_command.name}", timeout=timeout)
        self.original_help = help_command

        self.topic_title = discord.ui.TextInput(
            label="Display Title",
            placeholder="e.g., Trading Rules & Guidelines",
            default=help_command.title,
            required=True,
            min_length=1,
            max_length=200
        )

        self.topic_category = discord.ui.TextInput(
            label="Category (Optional)",
            placeholder="e.g., rules, guides, resources, info, faq",
            default=help_command.category or '',
            required=False,
            max_length=50
        )

        self.topic_content = discord.ui.TextInput(
            label="Content",
            placeholder="Help content (markdown supported, max 4000 chars)",
            style=discord.TextStyle.paragraph,
            default=help_command.content,
            required=True,
            min_length=1,
            max_length=4000
        )

        self.add_item(self.topic_title)
        self.add_item(self.topic_category)
        self.add_item(self.topic_content)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission."""
        # Store results
        self.result = {
            'name': self.original_help.name,
            'title': self.topic_title.value.strip(),
            'content': self.topic_content.value.strip(),
            'category': self.topic_category.value.strip() if self.topic_category.value else None
        }

        self.is_submitted = True

        # Create preview embed showing changes
        embed = EmbedTemplate.info(
            title="Help Topic Edit Preview",
            description=f"Changes to `/help {self.original_help.name}`:"
        )

        # Show title changes if different
        if self.original_help.title != self.result['title']:
            embed.add_field(name="Old Title", value=self.original_help.title, inline=True)
            embed.add_field(name="New Title", value=self.result['title'], inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)  # Spacer

        # Show category changes
        old_cat = self.original_help.category or "None"
        new_cat = self.result['category'] or "None"
        if old_cat != new_cat:
            embed.add_field(name="Old Category", value=old_cat, inline=True)
            embed.add_field(name="New Category", value=new_cat, inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)  # Spacer

        # Show content preview (always show since it's the main field)
        old_content = self.original_help.content[:300] + ('...' if len(self.original_help.content) > 300 else '')
        new_content = self.result['content'][:300] + ('...' if len(self.result['content']) > 300 else '')

        embed.add_field(
            name="Old Content",
            value=old_content,
            inline=False
        )

        embed.add_field(
            name="New Content",
            value=new_content,
            inline=False
        )

        embed.set_footer(text="Changes will be visible to all server members")

        await interaction.response.send_message(embed=embed, ephemeral=True)


class HelpCommandDeleteConfirmView(BaseView):
    """Confirmation view for deleting a help topic."""

    def __init__(self, help_command: HelpCommand, *, user_id: int, timeout: float = 180.0):
        super().__init__(timeout=timeout, user_id=user_id)
        self.help_command = help_command
        self.result = None

    @discord.ui.button(label="Delete Topic", emoji="🗑️", style=discord.ButtonStyle.danger, row=0)
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm the topic deletion."""
        self.result = True

        embed = EmbedTemplate.success(
            title="Help Topic Deleted",
            description=f"The help topic `/help {self.help_command.name}` has been deleted (soft delete)."
        )

        embed.add_field(
            name="Note",
            value="This topic can be restored later if needed using admin commands.",
            inline=False
        )

        # Disable all buttons
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True  # type: ignore

        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.secondary, row=0)
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the topic deletion."""
        self.result = False

        embed = EmbedTemplate.info(
            title="Deletion Cancelled",
            description=f"The help topic `/help {self.help_command.name}` was not deleted."
        )

        # Disable all buttons
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True  # type: ignore

        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


class HelpCommandListView(BaseView):
    """Paginated view for browsing help topics."""

    def __init__(
        self,
        help_commands: List[HelpCommand],
        user_id: Optional[int] = None,
        category_filter: Optional[str] = None,
        *,
        timeout: float = 300.0
    ):
        super().__init__(timeout=timeout, user_id=user_id)
        self.help_commands = help_commands
        self.category_filter = category_filter
        self.current_page = 0
        self.topics_per_page = 10

        self._update_buttons()

    def _update_buttons(self):
        """Update button states based on current page."""
        total_pages = max(1, (len(self.help_commands) + self.topics_per_page - 1) // self.topics_per_page)

        self.previous_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page >= total_pages - 1

        # Update page info
        self.page_info.label = f"Page {self.current_page + 1}/{total_pages}"

    def _get_current_topics(self) -> List[HelpCommand]:
        """Get help topics for current page."""
        start_idx = self.current_page * self.topics_per_page
        end_idx = start_idx + self.topics_per_page
        return self.help_commands[start_idx:end_idx]

    def _create_embed(self) -> discord.Embed:
        """Create embed for current page."""
        current_topics = self._get_current_topics()

        title = "📚 Help Topics"
        if self.category_filter:
            title += f" - {self.category_filter.title()}"

        description = f"Found {len(self.help_commands)} help topic{'s' if len(self.help_commands) != 1 else ''}"

        embed = EmbedTemplate.create_base_embed(
            title=title,
            description=description,
            color=EmbedColors.INFO
        )

        if not current_topics:
            embed.add_field(
                name="No Topics",
                value="No help topics found. Admins can create topics using `/help-create`.",
                inline=False
            )
        else:
            # Group by category for better organization
            by_category = {}
            for topic in current_topics:
                cat = topic.category or "Uncategorized"
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(topic)

            for category, topics in sorted(by_category.items()):
                topic_list = []
                for topic in topics:
                    views_text = f" • {topic.view_count} views" if topic.view_count > 0 else ""
                    topic_list.append(f"• `/help {topic.name}` - {topic.title}{views_text}")

                embed.add_field(
                    name=f"📂 {category}",
                    value='\n'.join(topic_list),
                    inline=False
                )

        embed.set_footer(text="Use /help <topic-name> to view a specific topic")

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
        total_pages = max(1, (len(self.help_commands) + self.topics_per_page - 1) // self.topics_per_page)
        self.current_page = min(total_pages - 1, self.current_page + 1)
        self._update_buttons()

        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        """Handle view timeout."""
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True  # type: ignore

    def get_embed(self) -> discord.Embed:
        """Get the embed for this view."""
        return self._create_embed()


def create_help_topic_embed(help_command: HelpCommand) -> discord.Embed:
    """
    Create a formatted embed for displaying a help topic.

    Args:
        help_command: The help command to display

    Returns:
        Formatted discord.Embed
    """
    embed = EmbedTemplate.create_base_embed(
        title=help_command.title,
        description=help_command.content,
        color=EmbedColors.INFO
    )

    # Add metadata footer
    footer_text = f"Topic: {help_command.name}"
    if help_command.category:
        footer_text += f" • Category: {help_command.category}"
    if help_command.view_count > 0:
        footer_text += f" • Viewed {help_command.view_count} times"

    embed.set_footer(text=footer_text)

    # Add timestamps if available
    if help_command.updated_at:
        embed.timestamp = help_command.updated_at
    else:
        embed.timestamp = help_command.created_at

    return embed
