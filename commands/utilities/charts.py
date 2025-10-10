"""
Chart display and management commands.

Provides commands for displaying gameplay charts and admin commands
for managing the chart library.
"""
import discord
from discord import app_commands
from discord.ext import commands
from typing import List, Optional

from utils.decorators import logged_command
from utils.logging import get_contextual_logger, set_discord_context
from services.chart_service import get_chart_service, Chart
from views.embeds import EmbedTemplate, EmbedColors
from exceptions import BotException


class ChartCommands(commands.Cog):
    """Chart display command handlers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.ChartCommands')
        self.chart_service = get_chart_service()

    async def chart_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for chart names."""
        chart_keys = self.chart_service.get_chart_keys()

        # Filter based on current input
        filtered = [
            key for key in chart_keys
            if current.lower() in key.lower()
        ][:25]  # Discord limit

        # Get chart objects for display names
        choices = []
        for key in filtered:
            chart = self.chart_service.get_chart(key)
            if chart:
                choices.append(
                    app_commands.Choice(
                        name=f"{chart.name} ({chart.category})",
                        value=key
                    )
                )

        return choices

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


class ChartAdminCommands(commands.Cog):
    """Chart management command handlers for administrators."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.ChartAdminCommands')
        self.chart_service = get_chart_service()

    @app_commands.command(
        name="chart-add",
        description="[Admin] Add a new chart to the library"
    )
    @app_commands.describe(
        key="Unique identifier for the chart (e.g., 'rest', 'sac-bunt')",
        name="Display name for the chart",
        category="Category (gameplay, defense, reference, stats)",
        url="Image URL for the chart",
        description="Optional description of the chart"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @logged_command("/chart-add")
    async def chart_add(
        self,
        interaction: discord.Interaction,
        key: str,
        name: str,
        category: str,
        url: str,
        description: Optional[str] = None
    ):
        """Add a new chart to the library."""
        set_discord_context(
            interaction=interaction,
            command="/chart-add",
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
            title="✅ Chart Added",
            description=f"Successfully added chart '{name}'"
        )
        embed.add_field(name="Key", value=key, inline=True)
        embed.add_field(name="Category", value=category, inline=True)
        embed.set_image(url=url)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="chart-remove",
        description="[Admin] Remove a chart from the library"
    )
    @app_commands.describe(key="Chart key to remove")
    @app_commands.checks.has_permissions(administrator=True)
    @logged_command("/chart-remove")
    async def chart_remove(
        self,
        interaction: discord.Interaction,
        key: str
    ):
        """Remove a chart from the library."""
        set_discord_context(
            interaction=interaction,
            command="/chart-remove",
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
            title="✅ Chart Removed",
            description=f"Successfully removed chart '{chart.name}'"
        )
        embed.add_field(name="Key", value=key, inline=True)
        embed.add_field(name="Category", value=chart.category, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="chart-list",
        description="[Admin] List all available charts"
    )
    @app_commands.describe(category="Filter by category (optional)")
    @app_commands.checks.has_permissions(administrator=True)
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

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="chart-update",
        description="[Admin] Update a chart's properties"
    )
    @app_commands.describe(
        key="Chart key to update",
        name="New display name (optional)",
        category="New category (optional)",
        url="New image URL (optional)",
        description="New description (optional)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @logged_command("/chart-update")
    async def chart_update(
        self,
        interaction: discord.Interaction,
        key: str,
        name: Optional[str] = None,
        category: Optional[str] = None,
        url: Optional[str] = None,
        description: Optional[str] = None
    ):
        """Update a chart's properties."""
        set_discord_context(
            interaction=interaction,
            command="/chart-update",
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
            title="✅ Chart Updated",
            description=f"Successfully updated chart '{chart.name}'"
        )
        embed.add_field(name="Key", value=key, inline=True)
        embed.add_field(name="Category", value=chart.category, inline=True)

        if url:
            embed.set_image(url=url)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup function for chart commands."""
    await bot.add_cog(ChartCommands(bot))
    await bot.add_cog(ChartAdminCommands(bot))
