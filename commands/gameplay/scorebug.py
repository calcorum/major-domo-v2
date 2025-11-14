"""
Scorebug Commands

Implements commands for publishing and displaying live game scorebugs from Google Sheets scorecards.
"""
import discord
from discord.ext import commands
from discord import app_commands

from services.scorebug_service import ScorebugData, ScorebugService
from services.team_service import team_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.permissions import league_only
from utils.scorebug_helpers import create_scorebug_embed
from views.embeds import EmbedTemplate, EmbedColors
from exceptions import SheetsException
from .scorecard_tracker import ScorecardTracker


class ScorebugCommands(commands.Cog):
    """Scorebug command handlers for live game tracking."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.ScorebugCommands')
        self.scorebug_service = ScorebugService()
        self.scorecard_tracker = ScorecardTracker()
        self.logger.info("ScorebugCommands cog initialized")

    @app_commands.command(
        name="publish-scorecard",
        description="Publish a Google Sheets scorecard to this channel for live tracking"
    )
    @app_commands.describe(
        url="Full URL to the Google Sheets scorecard or just the sheet key"
    )
    @league_only()
    @logged_command("/publish-scorecard")
    async def publish_scorecard(
        self,
        interaction: discord.Interaction,
        url: str
    ):
        """
        Link a Google Sheets scorecard to the current channel for live scorebug tracking.

        The scorecard will be monitored for live score updates which will be displayed
        in the live scores channel and optionally in associated voice channels.
        """
        await interaction.response.defer()

        try:
            # Validate access to the scorecard
            await interaction.edit_original_response(
                content="📋 Accessing scorecard..."
            )

            # Try to open the scorecard to validate it
            scorecard = await self.scorebug_service.open_scorecard(url)

            # Verify it has a Scorebug tab
            try:
                scorebug_data = await self.scorebug_service.read_scorebug_data(url, full_length=False)
            except SheetsException:
                embed = EmbedTemplate.error(
                    title="Invalid Scorecard",
                    description=(
                        "This doesn't appear to be a valid scorecard.\n\n"
                        "Make sure the sheet has a 'Scorebug' tab and is properly set up."
                    )
                )
                await interaction.edit_original_response(content=None, embed=embed)
                return

            # Get team data for display
            away_team = None
            home_team = None
            if scorebug_data.away_team_id:
                away_team = await team_service.get_team(scorebug_data.away_team_id)
            if scorebug_data.home_team_id:
                home_team = await team_service.get_team(scorebug_data.home_team_id)

            # Format scorecard link
            away_abbrev = away_team.abbrev if away_team else "AWAY"
            home_abbrev = home_team.abbrev if home_team else "HOME"
            scorecard_link = f"[{away_abbrev} @ {home_abbrev}]({url})"

            # Store the scorecard in the tracker
            self.scorecard_tracker.publish_scorecard(
                text_channel_id=interaction.channel_id, # type: ignore
                sheet_url=url,
                publisher_id=interaction.user.id
            )

            # Create success embed
            embed = EmbedTemplate.success(
                title="Scorecard Published",
                description=(
                    f"Your scorecard has been published to {interaction.channel.mention}\n\n" # type: ignore
                    f"**Sheet:** {scorecard.title}\n"
                    f"**Status:** Live tracking enabled\n"
                    f"**Scorecard:** {scorecard_link}\n\n"
                    f"Anyone can now run `/scorebug` in this channel to see the current score.\n"
                    f"The scorebug will also update in the live scores channel every 3 minutes."
                )
            )

            embed.add_field(
                name="Commands",
                value=(
                    "`/scorebug` - Display full scorebug with details\n"
                    "`/scorebug full_length:False` - Display compact scorebug"
                ),
                inline=False
            )

            await interaction.edit_original_response(content=None, embed=embed)

        except SheetsException as e:
            embed = EmbedTemplate.error(
                title="Cannot Access Scorecard",
                description=(
                    f"❌ {str(e)}\n\n"
                    f"**Common issues:**\n"
                    f"• Sheet is not publicly accessible\n"
                    f"• Invalid sheet URL or key\n"
                    f"• Sheet doesn't exist\n\n"
                    f"Make sure your sheet is shared with 'Anyone with the link can view'."
                )
            )
            await interaction.edit_original_response(content=None, embed=embed)

        except Exception as e:
            self.logger.error(f"Error publishing scorecard: {e}", exc_info=True)
            embed = EmbedTemplate.error(
                title="Publication Failed",
                description=(
                    "❌ An unexpected error occurred while publishing the scorecard.\n\n"
                    "Please try again or contact support if the issue persists."
                )
            )
            await interaction.edit_original_response(content=None, embed=embed)

    @app_commands.command(
        name="scorebug",
        description="Display the scorebug for the game in this channel"
    )
    @app_commands.describe(
        full_length="Include full game details (defaults to True)"
    )
    @league_only()
    @logged_command("/scorebug")
    async def scorebug(
        self,
        interaction: discord.Interaction,
        full_length: bool = True
    ):
        """
        Display the current scorebug from the scorecard published in this channel.
        """
        await interaction.response.defer(ephemeral=True)

        # Check if a scorecard is published in this channel
        sheet_url = self.scorecard_tracker.get_scorecard(interaction.channel_id) # type: ignore

        if not sheet_url:
            embed = EmbedTemplate.error(
                title="No Scorecard Published",
                description=(
                    "❌ No scorecard has been published in this channel.\n\n"
                    "Use `/publish-scorecard <url>` to publish a scorecard first."
                )
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            # Read scorebug data
            await interaction.edit_original_response(
                content="📊 Reading scorebug..."
            )

            scorebug_data = await self.scorebug_service.read_scorebug_data(
                sheet_url,
                full_length=full_length
            )

            # Get team data
            away_team = None
            home_team = None
            if scorebug_data.away_team_id:
                away_team = await team_service.get_team(scorebug_data.away_team_id)
            if scorebug_data.home_team_id:
                home_team = await team_service.get_team(scorebug_data.home_team_id)

            # Create scorebug embed using shared utility
            embed = create_scorebug_embed(
                scorebug_data,
                away_team,
                home_team,
                full_length
            )

            await interaction.edit_original_response(content=None, embed=embed)

            # Update timestamp in tracker
            self.scorecard_tracker.update_timestamp(interaction.channel_id) # type: ignore

        except SheetsException as e:
            embed = EmbedTemplate.error(
                title="Cannot Read Scorebug",
                description=(
                    f"❌ {str(e)}\n\n"
                    f"The scorecard may have been deleted or the sheet structure changed."
                )
            )
            await interaction.edit_original_response(content=None, embed=embed)

        except Exception as e:
            self.logger.error(f"Error displaying scorebug: {e}", exc_info=True)
            embed = EmbedTemplate.error(
                title="Display Failed",
                description=(
                    "❌ An error occurred while reading the scorebug.\n\n"
                    "Please try again or republish the scorecard."
                )
            )
            await interaction.edit_original_response(content=None, embed=embed)


async def setup(bot: commands.Bot):
    """Load the scorebug commands cog."""
    await bot.add_cog(ScorebugCommands(bot))
