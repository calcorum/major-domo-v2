"""
Chart display and management commands.

Provides commands for displaying gameplay charts and admin commands
for managing the chart library.
"""
import discord
from discord import app_commands
from discord.ext import commands
from typing import List, Optional

from config import get_config
from utils.decorators import logged_command
from utils.logging import get_contextual_logger, set_discord_context
from services.chart_service import get_chart_service, Chart
from views.embeds import EmbedTemplate, EmbedColors
from exceptions import BotException


# Standalone autocomplete functions

async def chart_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> List[app_commands.Choice[str]]:
    """Autocomplete for chart names."""
    chart_service = get_chart_service()
    chart_keys = chart_service.get_chart_keys()

    # Filter based on current input
    filtered = [
        key for key in chart_keys
        if current.lower() in key.lower()
    ][:25]  # Discord limit

    # Get chart objects for display names
    choices = []
    for key in filtered:
        chart = chart_service.get_chart(key)
        if chart:
            choices.append(
                app_commands.Choice(
                    name=f"{chart.name} ({chart.category})",
                    value=key
                )
            )

    return choices


async def category_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> List[app_commands.Choice[str]]:
    """Autocomplete for category keys."""
    chart_service = get_chart_service()
    categories = chart_service.get_categories()

    # Filter based on current input
    filtered = [
        key for key in categories.keys()
        if current.lower() in key.lower()
    ][:25]  # Discord limit

    return [
        app_commands.Choice(
            name=f"{categories[key]} ({key})",
            value=key
        )
        for key in filtered
    ]


# Helper function for permission checking
def has_manage_permission(interaction: discord.Interaction) -> bool:
    """Check if user has permission to manage charts/categories."""
    # Check if user is admin
    if interaction.user.guild_permissions.administrator:
        return True

    # Check if user has the Help Editor role
    help_editor_role = discord.utils.get(interaction.guild.roles, name=get_config().help_editor_role_name)
    if help_editor_role and help_editor_role in interaction.user.roles:
        return True

    return False


class ChartCommands(commands.Cog):
    """Chart display command handlers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.ChartCommands')
        self.chart_service = get_chart_service()

    @app_commands.command(
        name="charts",
        description="Display a gameplay chart or infographic"
    )
    @app_commands.describe(chart_name="Name of the chart to display")
    @app_commands.autocomplete(chart_name=chart_autocomplete)
    @logged_command("/charts")
    async def charts(
        self,
        interaction: discord.Interaction,
        chart_name: str
    ):
        """Display a gameplay chart or infographic."""
        set_discord_context(
            interaction=interaction,
            command="/charts",
            chart_name=chart_name
        )

        # Get chart
        chart = self.chart_service.get_chart(chart_name)
        if chart is None:
            raise BotException(f"Chart '{chart_name}' not found")

        # Get category display name
        categories = self.chart_service.get_categories()
        category_display = categories.get(chart.category, chart.category)

        # Create embed for first image
        embed = EmbedTemplate.create_base_embed(
            title=f"📊 {chart.name}",
            description=chart.description if chart.description else None,
            color=EmbedColors.PRIMARY
        )
        embed.add_field(name="Category", value=category_display, inline=True)

        if len(chart.urls) > 1:
            embed.add_field(
                name="Images",
                value=f"{len(chart.urls)} images in this chart",
                inline=True
            )

        # Set first image
        if chart.urls:
            embed.set_image(url=chart.urls[0])

        # Send response
        await interaction.response.send_message(embed=embed)

        # Send additional images as followups
        if len(chart.urls) > 1:
            for url in chart.urls[1:]:
                followup_embed = EmbedTemplate.create_base_embed(
                    title=f"📊 {chart.name} (continued)",
                    color=EmbedColors.PRIMARY
                )
                followup_embed.set_image(url=url)
                await interaction.followup.send(embed=followup_embed)

    @app_commands.command(
        name="chart-list",
        description="List all available charts"
    )
    @app_commands.describe(category="Filter by category (optional)")
    @logged_command("/chart-list")
    async def chart_list(
        self,
        interaction: discord.Interaction,
        category: Optional[str] = None
    ):
        """List all available charts."""
        set_discord_context(
            interaction=interaction,
            command="/chart-list",
            category=category
        )

        # Get charts
        if category:
            charts = self.chart_service.get_charts_by_category(category)
            title = f"📊 Charts in '{category}'"
        else:
            charts = self.chart_service.get_all_charts()
            title = "📊 All Available Charts"

        if not charts:
            raise BotException("No charts found")

        # Group by category
        categories = self.chart_service.get_categories()
        charts_by_category = {}
        for chart in charts:
            if chart.category not in charts_by_category:
                charts_by_category[chart.category] = []
            charts_by_category[chart.category].append(chart)

        # Create embed
        embed = EmbedTemplate.create_base_embed(
            title=title,
            description=f"Total: {len(charts)} chart(s)",
            color=EmbedColors.PRIMARY
        )

        # Add fields by category
        for cat_key in sorted(charts_by_category.keys()):
            cat_charts = charts_by_category[cat_key]
            cat_display = categories.get(cat_key, cat_key)

            chart_list = "\n".join([
                f"• `{chart.key}` - {chart.name}"
                for chart in sorted(cat_charts, key=lambda c: c.key)
            ])

            embed.add_field(
                name=f"{cat_display} ({len(cat_charts)})",
                value=chart_list,
                inline=False
            )

        await interaction.response.send_message(embed=embed)


class ChartManageGroup(app_commands.Group):
    """Chart management commands for administrators and help editors."""

    def __init__(self):
        super().__init__(
            name="chart-manage",
            description="Manage charts (admin/help editor only)"
        )
        self.logger = get_contextual_logger(f'{__name__}.ChartManageGroup')
        self.chart_service = get_chart_service()

    @app_commands.command(
        name="add",
        description="Add a new chart to the library"
    )
    @app_commands.describe(
        key="Unique identifier for the chart (e.g., 'rest', 'sac-bunt')",
        name="Display name for the chart",
        category="Category key (use autocomplete)",
        url="Image URL for the chart",
        description="Optional description of the chart"
    )
    @app_commands.autocomplete(category=category_autocomplete)
    @logged_command("/chart-manage add")
    async def add(
        self,
        interaction: discord.Interaction,
        key: str,
        name: str,
        category: str,
        url: str,
        description: Optional[str] = None
    ):
        """Add a new chart to the library."""
        # Check permissions
        if not has_manage_permission(interaction):
            embed = EmbedTemplate.error(
                title="Permission Denied",
                description=f"Only administrators and users with the **{get_config().help_editor_role_name}** role can manage charts."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        set_discord_context(
            interaction=interaction,
            command="/chart-manage add",
            chart_key=key,
            chart_name=name
        )

        # Validate category
        valid_categories = list(self.chart_service.get_categories().keys())
        if category not in valid_categories:
            raise BotException(
                f"Invalid category. Must be one of: {', '.join(valid_categories)}"
            )

        # Add chart (service will handle duplicate key check)
        self.chart_service.add_chart(
            key=key,
            name=name,
            category=category,
            urls=[url],
            description=description or ""
        )

        # Success response
        embed = EmbedTemplate.success(
            title="Chart Added",
            description=f"Successfully added chart '{name}'"
        )
        embed.add_field(name="Key", value=key, inline=True)
        embed.add_field(name="Category", value=category, inline=True)
        embed.set_image(url=url)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="remove",
        description="Remove a chart from the library"
    )
    @app_commands.describe(key="Chart key to remove")
    @app_commands.autocomplete(key=chart_autocomplete)
    @logged_command("/chart-manage remove")
    async def remove(
        self,
        interaction: discord.Interaction,
        key: str
    ):
        """Remove a chart from the library."""
        # Check permissions
        if not has_manage_permission(interaction):
            embed = EmbedTemplate.error(
                title="Permission Denied",
                description=f"Only administrators and users with the **{get_config().help_editor_role_name}** role can manage charts."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        set_discord_context(
            interaction=interaction,
            command="/chart-manage remove",
            chart_key=key
        )

        # Get chart before removing (for confirmation message)
        chart = self.chart_service.get_chart(key)
        if chart is None:
            raise BotException(f"Chart '{key}' not found")

        # Remove chart
        self.chart_service.remove_chart(key)

        # Success response
        embed = EmbedTemplate.success(
            title="Chart Removed",
            description=f"Successfully removed chart '{chart.name}'"
        )
        embed.add_field(name="Key", value=key, inline=True)
        embed.add_field(name="Category", value=chart.category, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="update",
        description="Update a chart's properties"
    )
    @app_commands.describe(
        key="Chart key to update",
        name="New display name (optional)",
        category="New category (optional)",
        url="New image URL (optional)",
        description="New description (optional)"
    )
    @app_commands.autocomplete(
        key=chart_autocomplete,
        category=category_autocomplete
    )
    @logged_command("/chart-manage update")
    async def update(
        self,
        interaction: discord.Interaction,
        key: str,
        name: Optional[str] = None,
        category: Optional[str] = None,
        url: Optional[str] = None,
        description: Optional[str] = None
    ):
        """Update a chart's properties."""
        # Check permissions
        if not has_manage_permission(interaction):
            embed = EmbedTemplate.error(
                title="Permission Denied",
                description=f"Only administrators and users with the **{get_config().help_editor_role_name}** role can manage charts."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        set_discord_context(
            interaction=interaction,
            command="/chart-manage update",
            chart_key=key
        )

        # Validate at least one field to update
        if not any([name, category, url, description]):
            raise BotException("Must provide at least one field to update")

        # Validate category if provided
        if category:
            valid_categories = list(self.chart_service.get_categories().keys())
            if category not in valid_categories:
                raise BotException(
                    f"Invalid category. Must be one of: {', '.join(valid_categories)}"
                )

        # Update chart
        self.chart_service.update_chart(
            key=key,
            name=name,
            category=category,
            urls=[url] if url else None,
            description=description
        )

        # Get updated chart
        chart = self.chart_service.get_chart(key)
        if chart is None:
            raise BotException(f"Chart '{key}' not found after update")

        # Success response
        embed = EmbedTemplate.success(
            title="Chart Updated",
            description=f"Successfully updated chart '{chart.name}'"
        )
        embed.add_field(name="Key", value=key, inline=True)
        embed.add_field(name="Category", value=chart.category, inline=True)

        if url:
            embed.set_image(url=url)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class ChartCategoryGroup(app_commands.Group):
    """Chart category management commands for administrators and help editors."""

    def __init__(self):
        super().__init__(
            name="chart-categories",
            description="Manage chart categories (admin/help editor only)"
        )
        self.logger = get_contextual_logger(f'{__name__}.ChartCategoryGroup')
        self.chart_service = get_chart_service()

    @app_commands.command(
        name="list",
        description="List all chart categories"
    )
    @logged_command("/chart-categories list")
    async def list_categories(
        self,
        interaction: discord.Interaction
    ):
        """List all chart categories."""
        # Check permissions
        if not has_manage_permission(interaction):
            embed = EmbedTemplate.error(
                title="Permission Denied",
                description=f"Only administrators and users with the **{get_config().help_editor_role_name}** role can manage categories."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        set_discord_context(
            interaction=interaction,
            command="/chart-categories list"
        )

        categories = self.chart_service.get_categories()

        if not categories:
            embed = EmbedTemplate.info(
                title="📊 Chart Categories",
                description="No categories defined. Use `/chart-categories add` to create one."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Create embed
        embed = EmbedTemplate.create_base_embed(
            title="📊 Chart Categories",
            description=f"Total: {len(categories)} category(ies)",
            color=EmbedColors.PRIMARY
        )

        # List all categories
        category_list = "\n".join([
            f"• `{key}` - {display_name}"
            for key, display_name in sorted(categories.items())
        ])

        embed.add_field(
            name="Categories",
            value=category_list,
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="add",
        description="Add a new chart category"
    )
    @app_commands.describe(
        key="Category key (e.g., 'gameplay', 'stats')",
        display_name="Display name (e.g., 'Gameplay Charts', 'Statistics')"
    )
    @logged_command("/chart-categories add")
    async def add_category(
        self,
        interaction: discord.Interaction,
        key: str,
        display_name: str
    ):
        """Add a new chart category."""
        # Check permissions
        if not has_manage_permission(interaction):
            embed = EmbedTemplate.error(
                title="Permission Denied",
                description=f"Only administrators and users with the **{get_config().help_editor_role_name}** role can manage categories."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        set_discord_context(
            interaction=interaction,
            command="/chart-categories add",
            category_key=key
        )

        # Add category (service will handle duplicate check)
        self.chart_service.add_category(key=key, display_name=display_name)

        # Success response
        embed = EmbedTemplate.success(
            title="Category Added",
            description=f"Successfully added category '{display_name}'"
        )
        embed.add_field(name="Key", value=key, inline=True)
        embed.add_field(name="Display Name", value=display_name, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="remove",
        description="Remove a chart category"
    )
    @app_commands.describe(key="Category key to remove")
    @app_commands.autocomplete(key=category_autocomplete)
    @logged_command("/chart-categories remove")
    async def remove_category(
        self,
        interaction: discord.Interaction,
        key: str
    ):
        """Remove a chart category."""
        # Check permissions
        if not has_manage_permission(interaction):
            embed = EmbedTemplate.error(
                title="Permission Denied",
                description=f"Only administrators and users with the **{get_config().help_editor_role_name}** role can manage categories."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        set_discord_context(
            interaction=interaction,
            command="/chart-categories remove",
            category_key=key
        )

        # Get category before removing (for confirmation message)
        categories = self.chart_service.get_categories()
        if key not in categories:
            raise BotException(f"Category '{key}' not found")

        category_display = categories[key]

        # Remove category (service will validate no charts use it)
        self.chart_service.remove_category(key)

        # Success response
        embed = EmbedTemplate.success(
            title="Category Removed",
            description=f"Successfully removed category '{category_display}'"
        )
        embed.add_field(name="Key", value=key, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="rename",
        description="Rename a chart category"
    )
    @app_commands.describe(
        key="Category key to rename",
        new_display_name="New display name"
    )
    @app_commands.autocomplete(key=category_autocomplete)
    @logged_command("/chart-categories rename")
    async def rename_category(
        self,
        interaction: discord.Interaction,
        key: str,
        new_display_name: str
    ):
        """Rename a chart category."""
        # Check permissions
        if not has_manage_permission(interaction):
            embed = EmbedTemplate.error(
                title="Permission Denied",
                description=f"Only administrators and users with the **{get_config().help_editor_role_name}** role can manage categories."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        set_discord_context(
            interaction=interaction,
            command="/chart-categories rename",
            category_key=key
        )

        # Get old name for confirmation
        categories = self.chart_service.get_categories()
        if key not in categories:
            raise BotException(f"Category '{key}' not found")

        old_display_name = categories[key]

        # Update category
        self.chart_service.update_category(key=key, display_name=new_display_name)

        # Success response
        embed = EmbedTemplate.success(
            title="Category Renamed",
            description=f"Successfully renamed category from '{old_display_name}' to '{new_display_name}'"
        )
        embed.add_field(name="Key", value=key, inline=True)
        embed.add_field(name="Old Name", value=old_display_name, inline=True)
        embed.add_field(name="New Name", value=new_display_name, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup function for chart commands."""
    await bot.add_cog(ChartCommands(bot))
    bot.tree.add_command(ChartManageGroup())
    bot.tree.add_command(ChartCategoryGroup())
