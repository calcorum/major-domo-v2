"""
Weather command for Discord Bot v2.0

Provides ballpark weather checks with dice rolls for gameplay.
"""
import random
from typing import Optional, Tuple

import discord
from discord.ext import commands

from services import team_service, league_service, schedule_service
from models.team import Team
from models.current import Current
from models.game import Game
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.team_utils import get_user_major_league_team
from views.embeds import EmbedTemplate, EmbedColors


class WeatherCommands(commands.Cog):
    """Weather command handlers."""

    # Division weeks where time of day logic differs
    DIVISION_WEEKS = [1, 3, 6, 14, 16, 18]

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.WeatherCommands')
        self.logger.info("WeatherCommands cog initialized")

    @discord.app_commands.command(name="weather", description="Roll ballpark weather for a team")
    @discord.app_commands.describe(
        team_abbrev="Team abbreviation (optional - defaults to channel or your team)"
    )
    @logged_command("/weather")
    async def weather(self, interaction: discord.Interaction, team_abbrev: Optional[str] = None):
        """Display weather check for a team's ballpark."""
        await interaction.response.defer()

        # Get current league state
        current = await league_service.get_current_state()
        if current is None:
            embed = EmbedTemplate.error(
                title="League State Unavailable",
                description="Could not retrieve current league state. Please try again later."
            )
            await interaction.followup.send(embed=embed)
            return

        # Resolve team using 3-tier resolution
        team = await self._resolve_team(interaction, team_abbrev, current.season)

        if team is None:
            embed = EmbedTemplate.error(
                title="Team Not Found",
                description=(
                    f"Could not find a team for you. Try:\n"
                    f"• Provide a team abbreviation: `/weather NYY`\n"
                    f"• Use this command in a team channel\n"
                    f"• Make sure you own a team"
                )
            )
            await interaction.followup.send(embed=embed)
            return

        # Get games for this team in current week
        week_schedule = await schedule_service.get_week_schedule(current.season, current.week)
        team_games = [
            game for game in week_schedule
            if game.away_team.abbrev.upper() == team.abbrev.upper()
            or game.home_team.abbrev.upper() == team.abbrev.upper()
        ]

        # Calculate season, time of day, and roll weather
        season_display = self._get_season_display(current.week)
        time_of_day = self._get_time_of_day(team_games, current.week)
        weather_roll = self._roll_weather()

        # Create and send embed
        embed = self._create_weather_embed(
            team=team,
            current=current,
            season_display=season_display,
            time_of_day=time_of_day,
            weather_roll=weather_roll,
            games_played=sum(1 for g in team_games if g.is_completed),
            total_games=len(team_games),
            username=interaction.user.name
        )

        await interaction.followup.send(embed=embed)

    async def _resolve_team(
        self,
        interaction: discord.Interaction,
        team_abbrev: Optional[str],
        season: int
    ) -> Optional[Team]:
        """
        Resolve team using 3-tier priority:
        1. Explicit team_abbrev parameter
        2. Channel name parsing (format: <abbrev>-<park name>)
        3. User's owned team

        Args:
            interaction: Discord interaction
            team_abbrev: Explicit team abbreviation from user
            season: Current season number

        Returns:
            Team object or None if not found
        """
        # Priority 1: Explicit parameter
        if team_abbrev:
            team = await team_service.get_team_by_abbrev(team_abbrev.upper(), season)
            if team:
                self.logger.info("Team resolved via explicit parameter", team_abbrev=team_abbrev)
                return team

        # Priority 2: Channel name parsing
        if isinstance(interaction.channel, discord.TextChannel):
            channel_name = interaction.channel.name
            # Parse channel name: "NYY-Yankee Stadium" -> "NYY"
            channel_abbrev = channel_name.split('-')[0].upper()
            team = await team_service.get_team_by_abbrev(channel_abbrev, season)
            if team:
                self.logger.info("Team resolved via channel name", channel_name=channel_name, abbrev=channel_abbrev)
                return team

        # Priority 3: User's owned Major League team
        team = await get_user_major_league_team(interaction.user.id, season)
        if team:
            self.logger.info("Team resolved via user ownership", user_id=interaction.user.id)
        else:
            self.logger.info("Team could not be resolved", user_id=interaction.user.id)

        return team

    def _get_season_display(self, week: int) -> str:
        """
        Get season display with emoji based on week.

        Args:
            week: Current week number

        Returns:
            Season string with emoji
        """
        if week <= 5:
            return "🌼 Spring"
        elif week <= 14:
            return "🏖️ Summer"
        else:
            return "🍂 Fall"

    def _get_time_of_day(self, games: list[Game], week: int) -> str:
        """
        Calculate time of day based on games played.

        Logic:
        - Division weeks: [1, 3, 6, 14, 16, 18]
        - 0/2 games played OR (1 game in div week): Night 🌙
        - 1/3 games played: Day 🌞
        - 4+ games played: "Spidey Time" (special case)
        - No games scheduled: Show pattern for all 4 games

        Args:
            games: List of games for this team this week
            week: Current week number

        Returns:
            Time of day string with emoji
        """
        night_str = "🌙 Night"
        day_str = "🌞 Day"
        is_div_week = week in self.DIVISION_WEEKS

        if not games:
            # No games scheduled - show the pattern
            if is_div_week:
                return f"{night_str} / {night_str} / {night_str} / {day_str}"
            else:
                return f"{night_str} / {day_str} / {night_str} / {day_str}"

        # Count completed games
        played_games = sum(1 for g in games if g.is_completed)

        if played_games in [0, 2] or (played_games == 1 and is_div_week):
            return night_str
        elif played_games in [1, 3]:
            return day_str
        else:
            # 4+ games - special case (shouldn't happen normally)
            # Try to get custom emoji, fallback to text
            penni = self.bot.get_emoji(1338227310201016370)
            if penni:
                return f"{penni} Spidey Time"
            else:
                return "🕸️ Spidey Time"

    def _roll_weather(self) -> int:
        """
        Roll a d20 for weather.

        Returns:
            Random integer between 1 and 20
        """
        return random.randint(1, 20)

    def _create_weather_embed(
        self,
        team: Team,
        current: Current,
        season_display: str,
        time_of_day: str,
        weather_roll: int,
        games_played: int,
        total_games: int,
        username: str
    ) -> discord.Embed:
        """
        Create the weather check embed.

        Args:
            team: Team object
            current: Current league state
            season_display: Season string with emoji
            time_of_day: Time of day string with emoji
            weather_roll: The d20 roll result
            games_played: Number of completed games
            total_games: Total games scheduled
            username: User who requested the weather

        Returns:
            Formatted Discord embed
        """
        # Create base embed with team colors
        color = int(team.color, 16) if team.color else EmbedColors.PRIMARY
        embed = EmbedTemplate.create_base_embed(
            title="🌤️ Weather Check",
            color=color
        )

        # Add season, time of day, and week info as inline fields
        embed.add_field(name="Season", value=season_display, inline=True)
        embed.add_field(name="Time of Day", value=time_of_day, inline=True)
        embed.add_field(
            name="Week",
            value=f"{current.week} | Games Played: {games_played}/{total_games}",
            inline=True
        )

        # Add weather roll in markdown code block
        roll_text = f"```md\n# {weather_roll}\nDetails: [1d20 ({weather_roll})]\n```"
        embed.add_field(name=f"Weather roll for {username}", value=roll_text, inline=False)

        # Set stadium image at bottom
        if team.stadium:
            embed.set_image(url=team.stadium)

        return embed


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(WeatherCommands(bot))
