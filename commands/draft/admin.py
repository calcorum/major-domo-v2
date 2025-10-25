"""
Draft Admin Commands

Admin-only commands for draft management and configuration.
"""
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import get_config
from services.draft_service import draft_service
from services.draft_pick_service import draft_pick_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from views.draft_views import create_admin_draft_info_embed
from views.embeds import EmbedTemplate


class DraftAdminGroup(app_commands.Group):
    """Draft administration command group."""

    def __init__(self):
        super().__init__(
            name="draft-admin",
            description="Admin commands for draft management"
        )
        self.logger = get_contextual_logger(f'{__name__}.DraftAdminGroup')

    @app_commands.command(name="info", description="View current draft configuration")
    @app_commands.checks.has_permissions(administrator=True)
    @logged_command("/draft-admin info")
    async def draft_admin_info(self, interaction: discord.Interaction):
        """Display current draft configuration and state."""
        await interaction.response.defer()

        # Get draft data
        draft_data = await draft_service.get_draft_data()
        if not draft_data:
            embed = EmbedTemplate.error(
                "Draft Not Found",
                "Could not retrieve draft configuration."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get current pick
        config = get_config()
        current_pick = await draft_pick_service.get_pick(
            config.sba_current_season,
            draft_data.currentpick
        )

        # Create admin info embed
        embed = await create_admin_draft_info_embed(draft_data, current_pick)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="timer", description="Enable or disable draft timer")
    @app_commands.describe(
        enabled="Turn timer on or off",
        minutes="Minutes per pick (optional, default uses current setting)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @logged_command("/draft-admin timer")
    async def draft_admin_timer(
        self,
        interaction: discord.Interaction,
        enabled: bool,
        minutes: Optional[int] = None
    ):
        """Enable or disable the draft timer."""
        await interaction.response.defer()

        # Get draft data
        draft_data = await draft_service.get_draft_data()
        if not draft_data:
            embed = EmbedTemplate.error(
                "Draft Not Found",
                "Could not retrieve draft configuration."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Update timer
        updated = await draft_service.set_timer(draft_data.id, enabled, minutes)

        if not updated:
            embed = EmbedTemplate.error(
                "Update Failed",
                "Failed to update draft timer."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Success message
        status = "enabled" if enabled else "disabled"
        description = f"Draft timer has been **{status}**."

        if enabled and minutes:
            description += f"\n\nPick duration: **{minutes} minutes**"
        elif enabled:
            description += f"\n\nPick duration: **{updated.pick_minutes} minutes**"

        embed = EmbedTemplate.success("Timer Updated", description)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="set-pick", description="Set current pick number")
    @app_commands.describe(
        pick_number="Overall pick number to jump to (1-512)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @logged_command("/draft-admin set-pick")
    async def draft_admin_set_pick(
        self,
        interaction: discord.Interaction,
        pick_number: int
    ):
        """Set the current pick number (admin operation)."""
        await interaction.response.defer()

        config = get_config()

        # Validate pick number
        if pick_number < 1 or pick_number > config.draft_total_picks:
            embed = EmbedTemplate.error(
                "Invalid Pick Number",
                f"Pick number must be between 1 and {config.draft_total_picks}."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get draft data
        draft_data = await draft_service.get_draft_data()
        if not draft_data:
            embed = EmbedTemplate.error(
                "Draft Not Found",
                "Could not retrieve draft configuration."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Verify pick exists
        pick = await draft_pick_service.get_pick(config.sba_current_season, pick_number)
        if not pick:
            embed = EmbedTemplate.error(
                "Pick Not Found",
                f"Pick #{pick_number} does not exist in the database."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Update current pick
        updated = await draft_service.set_current_pick(
            draft_data.id,
            pick_number,
            reset_timer=True
        )

        if not updated:
            embed = EmbedTemplate.error(
                "Update Failed",
                "Failed to update current pick."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Success message
        from utils.draft_helpers import format_pick_display

        description = f"Current pick set to **{format_pick_display(pick_number)}**."
        if pick.owner:
            description += f"\n\n{pick.owner.abbrev} {pick.owner.sname} is now on the clock."

        embed = EmbedTemplate.success("Pick Updated", description)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="channels", description="Configure draft Discord channels")
    @app_commands.describe(
        ping_channel="Channel for 'on the clock' pings",
        result_channel="Channel for draft results"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @logged_command("/draft-admin channels")
    async def draft_admin_channels(
        self,
        interaction: discord.Interaction,
        ping_channel: Optional[discord.TextChannel] = None,
        result_channel: Optional[discord.TextChannel] = None
    ):
        """Configure draft Discord channels."""
        await interaction.response.defer()

        if not ping_channel and not result_channel:
            embed = EmbedTemplate.error(
                "No Channels Provided",
                "Please specify at least one channel to update."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get draft data
        draft_data = await draft_service.get_draft_data()
        if not draft_data:
            embed = EmbedTemplate.error(
                "Draft Not Found",
                "Could not retrieve draft configuration."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Update channels
        updated = await draft_service.update_channels(
            draft_data.id,
            ping_channel_id=ping_channel.id if ping_channel else None,
            result_channel_id=result_channel.id if result_channel else None
        )

        if not updated:
            embed = EmbedTemplate.error(
                "Update Failed",
                "Failed to update draft channels."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Success message
        description = "Draft channels updated:\n\n"
        if ping_channel:
            description += f"**Ping Channel:** {ping_channel.mention}\n"
        if result_channel:
            description += f"**Result Channel:** {result_channel.mention}\n"

        embed = EmbedTemplate.success("Channels Updated", description)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="reset-deadline", description="Reset current pick deadline")
    @app_commands.describe(
        minutes="Minutes to add (uses default if not provided)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @logged_command("/draft-admin reset-deadline")
    async def draft_admin_reset_deadline(
        self,
        interaction: discord.Interaction,
        minutes: Optional[int] = None
    ):
        """Reset the current pick deadline."""
        await interaction.response.defer()

        # Get draft data
        draft_data = await draft_service.get_draft_data()
        if not draft_data:
            embed = EmbedTemplate.error(
                "Draft Not Found",
                "Could not retrieve draft configuration."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if not draft_data.timer:
            embed = EmbedTemplate.warning(
                "Timer Inactive",
                "Draft timer is currently disabled. Enable it with `/draft-admin timer on` first."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Reset deadline
        updated = await draft_service.reset_draft_deadline(draft_data.id, minutes)

        if not updated:
            embed = EmbedTemplate.error(
                "Update Failed",
                "Failed to reset draft deadline."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Success message
        deadline_timestamp = int(updated.pick_deadline.timestamp())
        minutes_used = minutes if minutes else updated.pick_minutes

        description = f"Pick deadline reset: **{minutes_used} minutes** added.\n\n"
        description += f"New deadline: <t:{deadline_timestamp}:F> (<t:{deadline_timestamp}:R>)"

        embed = EmbedTemplate.success("Deadline Reset", description)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function for loading the draft admin commands."""
    bot.tree.add_command(DraftAdminGroup())
