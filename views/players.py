"""
Player View Components

Interactive Discord UI components for player information display with toggleable statistics.
"""
from typing import Optional, TYPE_CHECKING

import discord
from discord.ext import commands

from utils.logging import get_contextual_logger
from views.base import BaseView
from views.embeds import EmbedTemplate, EmbedColors
from models.team import RosterType

if TYPE_CHECKING:
    from models.player import Player
    from models.batting_stats import BattingStats
    from models.pitching_stats import PitchingStats


class PlayerStatsView(BaseView):
    """
    Interactive view for player information with toggleable batting and pitching statistics.

    Features:
    - Basic player info always visible
    - Batting stats hidden by default, toggled with button
    - Pitching stats hidden by default, toggled with button
    - Buttons only appear if corresponding stats exist
    - User restriction - only command caller can toggle
    - 5 minute timeout with graceful cleanup
    """

    def __init__(
        self,
        player: 'Player',
        season: int,
        batting_stats: Optional['BattingStats'] = None,
        pitching_stats: Optional['PitchingStats'] = None,
        user_id: Optional[int] = None
    ):
        """
        Initialize the player stats view.

        Args:
            player: Player model with basic information
            season: Season for statistics display
            batting_stats: Batting statistics (if available)
            pitching_stats: Pitching statistics (if available)
            user_id: Discord user ID who can interact with this view
        """
        super().__init__(timeout=300.0, user_id=user_id, logger_name=f'{__name__}.PlayerStatsView')

        self.player = player
        self.season = season
        self.batting_stats = batting_stats
        self.pitching_stats = pitching_stats
        self.show_batting = False
        self.show_pitching = False

        # Only show batting button if stats are available
        if not batting_stats:
            self.remove_item(self.toggle_batting_button)
            self.logger.debug("No batting stats available, batting button hidden")

        # Only show pitching button if stats are available
        if not pitching_stats:
            self.remove_item(self.toggle_pitching_button)
            self.logger.debug("No pitching stats available, pitching button hidden")

        self.logger.info("PlayerStatsView initialized",
                        player_id=player.id,
                        player_name=player.name,
                        season=season,
                        has_batting=bool(batting_stats),
                        has_pitching=bool(pitching_stats),
                        user_id=user_id)

    @discord.ui.button(
        label="Show Batting Stats",
        style=discord.ButtonStyle.primary,
        emoji="💥",
        row=0
    )
    async def toggle_batting_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Toggle batting statistics visibility."""
        self.increment_interaction_count()
        self.show_batting = not self.show_batting

        # Update button label
        button.label = "Hide Batting Stats" if self.show_batting else "Show Batting Stats"

        self.logger.info("Batting stats toggled",
                        player_id=self.player.id,
                        show_batting=self.show_batting,
                        user_id=interaction.user.id)

        # Rebuild and update embed
        await self._update_embed(interaction)

    @discord.ui.button(
        label="Show Pitching Stats",
        style=discord.ButtonStyle.primary,
        emoji="⚾",
        row=0
    )
    async def toggle_pitching_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Toggle pitching statistics visibility."""
        self.increment_interaction_count()
        self.show_pitching = not self.show_pitching

        # Update button label
        button.label = "Hide Pitching Stats" if self.show_pitching else "Show Pitching Stats"

        self.logger.info("Pitching stats toggled",
                        player_id=self.player.id,
                        show_pitching=self.show_pitching,
                        user_id=interaction.user.id)

        # Rebuild and update embed
        await self._update_embed(interaction)

    async def _update_embed(self, interaction: discord.Interaction):
        """
        Rebuild the player embed with current visibility settings and update the message.

        Args:
            interaction: Discord interaction from button click
        """
        try:
            # Create embed with current visibility state
            embed = await self._create_player_embed()

            # Update the message with new embed
            await interaction.response.edit_message(embed=embed, view=self)

            self.logger.debug("Embed updated successfully",
                            show_batting=self.show_batting,
                            show_pitching=self.show_pitching)

        except Exception as e:
            self.logger.error("Failed to update embed", error=str(e), exc_info=True)

            # Try to send error message
            try:
                error_embed = EmbedTemplate.error(
                    title="Update Failed",
                    description="Failed to update player statistics. Please try again."
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
            except Exception:
                self.logger.error("Failed to send error message", exc_info=True)

    async def _create_player_embed(self) -> discord.Embed:
        """
        Create player embed with current visibility settings.

        Returns:
            Discord embed with player information and visible stats
        """
        player = self.player
        season = self.season

        # Determine embed color based on team
        embed_color = EmbedColors.PRIMARY
        if hasattr(player, 'team') and player.team and hasattr(player.team, 'color'):
            try:
                # Convert hex color string to int
                embed_color = int(player.team.color, 16)
            except (ValueError, TypeError):
                embed_color = EmbedColors.PRIMARY

        # Create base embed with player name as title
        # Add injury indicator emoji if player is injured
        title = f"🤕 {player.name}" if player.il_return is not None else player.name

        embed = EmbedTemplate.create_base_embed(
            title=title,
            color=embed_color
        )

        # Basic info section (always visible)
        embed.add_field(
            name="Position",
            value=player.primary_position,
            inline=True
        )

        if hasattr(player, 'team') and player.team:
            embed.add_field(
                name="Team",
                value=f"{player.team.abbrev} - {player.team.sname}",
                inline=True
            )

            # Add Major League affiliate if this is a Minor League team
            if player.team.roster_type() == RosterType.MINOR_LEAGUE:
                major_affiliate = player.team.get_major_league_affiliate()
                if major_affiliate:
                    embed.add_field(
                        name="Major Affiliate",
                        value=major_affiliate,
                        inline=True
                    )

        embed.add_field(
            name="sWAR",
            value=f"{player.wara:.1f}",
            inline=True
        )

        embed.add_field(
            name="Player ID",
            value=str(player.id),
            inline=True
        )

        # All positions if multiple
        if len(player.positions) > 1:
            embed.add_field(
                name="Positions",
                value=", ".join(player.positions),
                inline=True
            )

        embed.add_field(
            name="Season",
            value=str(season),
            inline=True
        )

        # Always show injury rating
        embed.add_field(
            name="Injury Rating",
            value=player.injury_rating or "N/A",
            inline=True
        )

        # Show injury return date only if player is currently injured
        if player.il_return:
            embed.add_field(
                name="Injury Return",
                value=player.il_return,
                inline=True
            )

        # Add batting stats if visible and available
        if self.show_batting and self.batting_stats:
            embed.add_field(name='', value='', inline=False)

            self.logger.debug("Adding batting statistics to embed")
            batting_stats = self.batting_stats

            rate_stats = (
                "```\n"
                "╭─────────────╮\n"
                f"│ AVG  {batting_stats.avg:.3f}  │\n"
                f"│ OBP  {batting_stats.obp:.3f}  │\n"
                f"│ SLG  {batting_stats.slg:.3f}  │\n"
                f"│ OPS  {batting_stats.ops:.3f}  │\n"
                f"│ wOBA {batting_stats.woba:.3f}  │\n"
                "╰─────────────╯\n"
                "```"
            )
            embed.add_field(
                name="Rate Stats",
                value=rate_stats,
                inline=True
            )

            count_stats = (
                "```\n"
                "╭───────────╮\n"
                f"│  HR  {batting_stats.homerun:>3}  │\n"
                f"│ RBI  {batting_stats.rbi:>3}  │\n"
                f"│   R  {batting_stats.run:>3}  │\n"
                f"│  AB {batting_stats.ab:>4}  │\n"
                f"│   H {batting_stats.hit:>4}  │\n"
                f"│  BB  {batting_stats.bb:>3}  │\n"
                f"│  SO  {batting_stats.so:>3}  │\n"
                "╰───────────╯\n"
                "```"
            )
            embed.add_field(
                name='Counting Stats',
                value=count_stats,
                inline=True
            )

        # Add pitching stats if visible and available
        if self.show_pitching and self.pitching_stats:
            embed.add_field(name='', value='', inline=False)

            self.logger.debug("Adding pitching statistics to embed")
            pitching_stats = self.pitching_stats
            ip = pitching_stats.innings_pitched

            record_stats = (
                "```\n"
                "╭─────────────╮\n"
                f"│ G-GS {pitching_stats.games:>2}-{pitching_stats.gs:<2}  │\n"
                f"│ W-L  {pitching_stats.win:>2}-{pitching_stats.loss:<2}  │\n"
                f"│ H-SV {pitching_stats.hold:>2}-{pitching_stats.saves:<2}  │\n"
                f"│ ERA  {pitching_stats.era:>5.2f}  │\n"
                f"│ WHIP {pitching_stats.whip:>5.2f}  │\n"
                "╰─────────────╯\n"
                "```"
            )
            embed.add_field(
                name="Record Stats",
                value=record_stats,
                inline=True
            )

            strikeout_stats = (
                "```\n"
                "╭──────────╮\n"
                f"│ IP{ip:>6.1f} │\n"
                f"│ SO  {pitching_stats.so:>3}  │\n"
                f"│ BB  {pitching_stats.bb:>3}  │\n"
                f"│  H  {pitching_stats.hits:>3}  │\n"
                "╰──────────╯\n"
                "```"
            )
            embed.add_field(
                name='Counting Stats',
                value=strikeout_stats,
                inline=True
            )

        # Add a note if no stats are visible
        if not self.show_batting and not self.show_pitching:
            if self.batting_stats or self.pitching_stats:
                embed.add_field(
                    name="📊 Statistics",
                    value="Click the buttons below to show statistics.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📊 Statistics",
                    value="No statistics available for this season.",
                    inline=False
                )

        # Set player card as main image
        if player.image:
            embed.set_image(url=player.image)
            self.logger.debug("Player card image added to embed", image_url=player.image)

        # Set thumbnail with priority: fancycard → headshot → team logo
        thumbnail_url = None
        thumbnail_source = None

        if hasattr(player, 'vanity_card') and player.vanity_card:
            thumbnail_url = player.vanity_card
            thumbnail_source = "fancycard"
        elif hasattr(player, 'headshot') and player.headshot:
            thumbnail_url = player.headshot
            thumbnail_source = "headshot"
        elif hasattr(player, 'team') and player.team and hasattr(player.team, 'thumbnail') and player.team.thumbnail:
            thumbnail_url = player.team.thumbnail
            thumbnail_source = "team logo"

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
            self.logger.debug(f"Thumbnail set from {thumbnail_source}", thumbnail_url=thumbnail_url)

        # Footer with player ID
        footer_text = f"Player ID: {player.id}"
        embed.set_footer(text=footer_text)

        return embed

    async def get_initial_embed(self) -> discord.Embed:
        """
        Get the initial embed with stats hidden.

        Returns:
            Discord embed with player information, stats hidden by default
        """
        # Ensure stats are hidden for initial display
        self.show_batting = False
        self.show_pitching = False

        return await self._create_player_embed()
