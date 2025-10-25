"""
Draft Status Commands

Display current draft state and information.
"""
import discord
from discord.ext import commands

from config import get_config
from services.draft_service import draft_service
from services.draft_pick_service import draft_pick_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from views.draft_views import create_draft_status_embed, create_on_the_clock_embed
from views.embeds import EmbedTemplate


class DraftStatusCommands(commands.Cog):
    """Draft status display command handlers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.DraftStatusCommands')

    @discord.app_commands.command(
        name="draft-status",
        description="View current draft state and timer information"
    )
    @logged_command("/draft-status")
    async def draft_status(self, interaction: discord.Interaction):
        """Display current draft state."""
        await interaction.response.defer()

        config = get_config()

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
        current_pick = await draft_pick_service.get_pick(
            config.sba_current_season,
            draft_data.currentpick
        )

        if not current_pick:
            embed = EmbedTemplate.error(
                "Pick Not Found",
                f"Could not retrieve pick #{draft_data.currentpick}."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Check pick lock status
        draft_picks_cog = self.bot.get_cog('DraftPicksCog')
        lock_status = "🔓 No pick in progress"

        if draft_picks_cog and draft_picks_cog.pick_lock.locked():
            if draft_picks_cog.lock_acquired_by:
                user = self.bot.get_user(draft_picks_cog.lock_acquired_by)
                user_name = user.name if user else f"User {draft_picks_cog.lock_acquired_by}"
                lock_status = f"🔒 Pick in progress by {user_name}"
            else:
                lock_status = "🔒 Pick in progress (system)"

        # Create status embed
        embed = await create_draft_status_embed(draft_data, current_pick, lock_status)
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(
        name="draft-on-clock",
        description="View detailed 'on the clock' information"
    )
    @logged_command("/draft-on-clock")
    async def draft_on_clock(self, interaction: discord.Interaction):
        """Display detailed 'on the clock' information with recent and upcoming picks."""
        await interaction.response.defer()

        config = get_config()

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
        current_pick = await draft_pick_service.get_pick(
            config.sba_current_season,
            draft_data.currentpick
        )

        if not current_pick or not current_pick.owner:
            embed = EmbedTemplate.error(
                "Pick Not Found",
                f"Could not retrieve pick #{draft_data.currentpick}."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get recent picks
        recent_picks = await draft_pick_service.get_recent_picks(
            config.sba_current_season,
            draft_data.currentpick,
            limit=5
        )

        # Get upcoming picks
        upcoming_picks = await draft_pick_service.get_upcoming_picks(
            config.sba_current_season,
            draft_data.currentpick,
            limit=5
        )

        # Get team roster sWAR (optional)
        from services.team_service import team_service
        team_roster_swar = None

        roster = await team_service.get_team_roster(current_pick.owner.id, 'current')
        if roster and roster.get('active'):
            team_roster_swar = roster['active'].get('WARa')

        # Create on the clock embed
        embed = await create_on_the_clock_embed(
            current_pick,
            draft_data,
            recent_picks,
            upcoming_picks,
            team_roster_swar
        )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    """Load the draft status commands cog."""
    await bot.add_cog(DraftStatusCommands(bot))
