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
from services.draft_sheet_service import get_draft_sheet_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.permissions import league_admin_only
from views.draft_views import create_admin_draft_info_embed
from views.embeds import EmbedTemplate


class DraftAdminGroup(app_commands.Group):
    """Draft administration command group."""

    def __init__(self, bot: commands.Bot):
        super().__init__(
            name="draft-admin",
            description="Admin commands for draft management"
        )
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.DraftAdminGroup')

    def _ensure_monitor_running(self) -> str:
        """
        Ensure the draft monitor task is running.

        Returns:
            Status message about the monitor state
        """
        from tasks.draft_monitor import setup_draft_monitor

        if not hasattr(self.bot, 'draft_monitor') or self.bot.draft_monitor is None:
            self.bot.draft_monitor = setup_draft_monitor(self.bot)
            self.logger.info("Draft monitor task started")
            return "\n\n🤖 **Draft monitor started** - auto-draft and warnings active"
        elif not self.bot.draft_monitor.monitor_loop.is_running():
            # Task exists but was stopped/cancelled - create a new one
            self.bot.draft_monitor = setup_draft_monitor(self.bot)
            self.logger.info("Draft monitor task recreated")
            return "\n\n🤖 **Draft monitor restarted** - auto-draft and warnings active"
        else:
            return "\n\n🤖 Draft monitor already running"

    @app_commands.command(name="info", description="View current draft configuration")
    @league_admin_only()
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
            config.sba_season,
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
    @league_admin_only()
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

        # Start draft monitor task if timer is enabled
        monitor_status = ""
        if enabled:
            monitor_status = self._ensure_monitor_running()

        # Success message
        status = "enabled" if enabled else "disabled"
        description = f"Draft timer has been **{status}**."

        if enabled:
            # Show pick duration
            pick_mins = minutes if minutes else updated.pick_minutes
            description += f"\n\n**Pick duration:** {pick_mins} minutes"

            # Show current pick number
            description += f"\n**Current Pick:** #{updated.currentpick}"

            # Show deadline
            if updated.pick_deadline:
                deadline_timestamp = int(updated.pick_deadline.timestamp())
                description += f"\n**Deadline:** <t:{deadline_timestamp}:T> (<t:{deadline_timestamp}:R>)"

        description += monitor_status

        embed = EmbedTemplate.success("Timer Updated", description)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="set-pick", description="Set current pick number")
    @app_commands.describe(
        pick_number="Overall pick number to jump to (1-512)"
    )
    @league_admin_only()
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
        pick = await draft_pick_service.get_pick(config.sba_season, pick_number)
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

        # Add timer status and ensure monitor is running if timer is active
        if updated.timer and updated.pick_deadline:
            deadline_timestamp = int(updated.pick_deadline.timestamp())
            description += f"\n\n⏱️ **Timer Active** - Deadline <t:{deadline_timestamp}:R>"
            # Ensure monitor is running
            monitor_status = self._ensure_monitor_running()
            description += monitor_status
        else:
            description += "\n\n⏸️ **Timer Inactive**"

        embed = EmbedTemplate.success("Pick Updated", description)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="channels", description="Configure draft Discord channels")
    @app_commands.describe(
        ping_channel="Channel for 'on the clock' pings",
        result_channel="Channel for draft results"
    )
    @league_admin_only()
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
    @league_admin_only()
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

    @app_commands.command(name="resync-sheet", description="Resync all picks to Google Sheet")
    @league_admin_only()
    @logged_command("/draft-admin resync-sheet")
    async def draft_admin_resync_sheet(self, interaction: discord.Interaction):
        """
        Resync all draft picks from database to Google Sheet.

        Used for recovery if sheet gets corrupted, auth fails, or picks were
        missed during the draft. Clears existing data and repopulates from database.
        """
        await interaction.response.defer()

        config = get_config()

        # Check if sheet integration is enabled
        if not config.draft_sheet_enabled:
            embed = EmbedTemplate.warning(
                "Sheet Disabled",
                "Draft sheet integration is currently disabled."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Check if sheet is configured for current season
        sheet_url = config.get_draft_sheet_url(config.sba_season)
        if not sheet_url:
            embed = EmbedTemplate.error(
                "No Sheet Configured",
                f"No draft sheet is configured for season {config.sba_season}."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get all picks with player data for current season
        all_picks = await draft_pick_service.get_picks_with_players(config.sba_season)

        if not all_picks:
            embed = EmbedTemplate.warning(
                "No Picks Found",
                "No draft picks found for the current season."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Filter to only picks that have been made (have a player)
        completed_picks = [p for p in all_picks if p.player is not None]

        if not completed_picks:
            embed = EmbedTemplate.warning(
                "No Completed Picks",
                "No draft picks have been made yet."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Prepare pick data for batch write
        pick_data = []
        for pick in completed_picks:
            orig_abbrev = pick.origowner.abbrev if pick.origowner else (pick.owner.abbrev if pick.owner else "???")
            owner_abbrev = pick.owner.abbrev if pick.owner else "???"
            player_name = pick.player.name if pick.player else "Unknown"
            swar = pick.player.wara if pick.player else 0.0

            pick_data.append((
                pick.overall,
                orig_abbrev,
                owner_abbrev,
                player_name,
                swar
            ))

        # Get draft sheet service
        draft_sheet_service = get_draft_sheet_service()

        # Clear existing sheet data first
        cleared = await draft_sheet_service.clear_picks_range(
            config.sba_season,
            start_overall=1,
            end_overall=config.draft_total_picks
        )

        if not cleared:
            embed = EmbedTemplate.warning(
                "Clear Failed",
                "Failed to clear existing sheet data. Attempting to write picks anyway..."
            )
            # Don't return - try to write anyway

        # Write all picks in batch
        success_count, failure_count = await draft_sheet_service.write_picks_batch(
            config.sba_season,
            pick_data
        )

        # Build result message
        total_picks = len(pick_data)
        if failure_count == 0:
            description = (
                f"Successfully synced **{success_count}** picks to the draft sheet.\n\n"
                f"[View Draft Sheet]({sheet_url})"
            )
            embed = EmbedTemplate.success("Resync Complete", description)
        elif success_count > 0:
            description = (
                f"Synced **{success_count}** picks ({failure_count} failed).\n\n"
                f"[View Draft Sheet]({sheet_url})"
            )
            embed = EmbedTemplate.warning("Partial Resync", description)
        else:
            description = (
                f"Failed to sync any picks. Check logs for details.\n\n"
                f"[View Draft Sheet]({sheet_url})"
            )
            embed = EmbedTemplate.error("Resync Failed", description)

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function for loading the draft admin commands."""
    bot.tree.add_command(DraftAdminGroup(bot))
