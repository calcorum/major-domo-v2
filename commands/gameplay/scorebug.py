"""
Scorebug Commands

Implements commands for publishing and displaying live game scorebugs from Google Sheets scorecards.
"""
import discord
from discord.ext import commands
from discord import app_commands

from services.scorebug_service import ScorebugService
from services.team_service import team_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
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
    @logged_command("/scorebug")
    async def scorebug(
        self,
        interaction: discord.Interaction,
        full_length: bool = True
    ):
        """
        Display the current scorebug from the scorecard published in this channel.
        """
        await interaction.response.defer()

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

            # Create scorebug embed
            embed = await self._create_scorebug_embed(
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

    async def _create_scorebug_embed(
        self,
        scorebug_data,
        away_team,
        home_team,
        full_length: bool
    ) -> discord.Embed:
        """
        Create a rich embed from scorebug data.

        Args:
            scorebug_data: ScorebugData object
            away_team: Away team object (optional)
            home_team: Home team object (optional)
            full_length: Include full details

        Returns:
            Discord embed with scorebug information
        """
        # Determine winning team for embed color
        if scorebug_data.away_score > scorebug_data.home_score and away_team:
            embed_color = away_team.get_color_int()
            thumbnail_url = away_team.thumbnail if away_team.thumbnail else None
        elif scorebug_data.home_score > scorebug_data.away_score and home_team:
            embed_color = home_team.get_color_int()
            thumbnail_url = home_team.thumbnail if home_team.thumbnail else None
        else:
            embed_color = EmbedColors.INFO
            thumbnail_url = None

        # Create embed with header as title
        embed = discord.Embed(
            title=scorebug_data.header,
            color=embed_color
        )

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        # Add score information
        away_abbrev = away_team.abbrev if away_team else "AWAY"
        home_abbrev = home_team.abbrev if home_team else "HOME"

        score_text = (
            f"```\n"
            f"{away_abbrev:<6} {scorebug_data.away_score:>3}\n"
            f"{home_abbrev:<6} {scorebug_data.home_score:>3}\n"
            f"```"
        )

        embed.add_field(
            name="Score",
            value=score_text,
            inline=True
        )

        # Add game state
        if not scorebug_data.is_final:
            embed.add_field(
                name="Status",
                value=f"**{scorebug_data.which_half}**",
                inline=True
            )

        # Add runners on base if present
        if scorebug_data.runners and any(scorebug_data.runners):
            runners_text = self._format_runners(scorebug_data.runners)
            if runners_text:
                embed.add_field(
                    name="Runners",
                    value=runners_text,
                    inline=False
                )

        # Add matchups if full length
        if full_length and scorebug_data.matchups and any(scorebug_data.matchups):
            matchups_text = self._format_matchups(scorebug_data.matchups)
            if matchups_text:
                embed.add_field(
                    name="Matchups",
                    value=matchups_text,
                    inline=False
                )

        # Add summary if full length
        if full_length and scorebug_data.summary and any(scorebug_data.summary):
            summary_text = self._format_summary(scorebug_data.summary)
            if summary_text:
                embed.add_field(
                    name="Summary",
                    value=summary_text,
                    inline=False
                )

        return embed

    def _format_runners(self, runners) -> str:
        """Format runners on base for display."""
        # runners is a list of [runner_name, runner_position] pairs
        runner_lines = []
        for runner_data in runners:
            if runner_data and len(runner_data) >= 2 and runner_data[0]:
                runner_lines.append(f"**{runner_data[1]}:** {runner_data[0]}")

        return "\n".join(runner_lines) if runner_lines else ""

    def _format_matchups(self, matchups) -> str:
        """Format current matchups for display."""
        # matchups is a list of [batter, pitcher] pairs
        matchup_lines = []
        for matchup_data in matchups:
            if matchup_data and len(matchup_data) >= 2 and matchup_data[0]:
                matchup_lines.append(f"{matchup_data[0]} vs {matchup_data[1]}")

        return "\n".join(matchup_lines) if matchup_lines else ""

    def _format_summary(self, summary) -> str:
        """Format game summary for display."""
        # summary is a list of summary line pairs
        summary_lines = []
        for summary_data in summary:
            if summary_data and len(summary_data) >= 1 and summary_data[0]:
                # Join both columns if present
                line = " - ".join([str(x) for x in summary_data if x])
                summary_lines.append(line)

        return "\n".join(summary_lines) if summary_lines else ""


async def setup(bot: commands.Bot):
    """Load the scorebug commands cog."""
    await bot.add_cog(ScorebugCommands(bot))
