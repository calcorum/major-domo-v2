"""
League Schedule Commands

Implements slash commands for displaying game schedules and results.
"""
from typing import Optional
import asyncio

import discord
from discord.ext import commands

from config import get_config
from services.schedule_service import schedule_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from views.embeds import EmbedColors, EmbedTemplate


class ScheduleCommands(commands.Cog):
    """League schedule command handlers."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.ScheduleCommands')
    
    @discord.app_commands.command(
        name="schedule",
        description="Display game schedule"
    )
    @discord.app_commands.describe(
        season="Season to show schedule for (defaults to current season)",
        week="Week number to show (optional)",
        team="Team abbreviation to filter by (optional)"
    )
    @logged_command("/schedule")
    async def schedule(
        self,
        interaction: discord.Interaction,
        season: Optional[int] = None,
        week: Optional[int] = None,
        team: Optional[str] = None
    ):
        """Display game schedule for a week or team."""
        await interaction.response.defer()
        
        search_season = season or get_config().sba_current_season
        
        if team:
            # Show team schedule
            await self._show_team_schedule(interaction, search_season, team, week)
        elif week:
            # Show specific week schedule
            await self._show_week_schedule(interaction, search_season, week)
        else:
            # Show recent/upcoming games
            await self._show_current_schedule(interaction, search_season)
    
    # @discord.app_commands.command(
    #     name="results",
    #     description="Display recent game results"
    # )
    # @discord.app_commands.describe(
    #     season="Season to show results for (defaults to current season)",
    #     week="Specific week to show results for (optional)"
    # )
    # @logged_command("/results")
    # async def results(
    #     self,
    #     interaction: discord.Interaction,
    #     season: Optional[int] = None,
    #     week: Optional[int] = None
    # ):
    #     """Display recent game results."""
    #     await interaction.response.defer()
        
    #     search_season = season or get_config().sba_current_season
        
    #     if week:
    #         # Show specific week results
    #         games = await schedule_service.get_week_schedule(search_season, week)
    #         completed_games = [game for game in games if game.is_completed]
            
    #         if not completed_games:
    #             await interaction.followup.send(
    #                 f"❌ No completed games found for season {search_season}, week {week}.",
    #                 ephemeral=True
    #             )
    #             return
            
    #         embed = await self._create_week_results_embed(completed_games, search_season, week)
    #         await interaction.followup.send(embed=embed)
    #     else:
    #         # Show recent results
    #         recent_games = await schedule_service.get_recent_games(search_season)
            
    #         if not recent_games:
    #             await interaction.followup.send(
    #                 f"❌ No recent games found for season {search_season}.",
    #                 ephemeral=True
    #             )
    #             return
            
    #         embed = await self._create_recent_results_embed(recent_games, search_season)
    #         await interaction.followup.send(embed=embed)
    
    async def _show_week_schedule(self, interaction: discord.Interaction, season: int, week: int):
        """Show schedule for a specific week."""
        self.logger.debug("Fetching week schedule", season=season, week=week)
        
        games = await schedule_service.get_week_schedule(season, week)
        
        if not games:
            await interaction.followup.send(
                f"❌ No games found for season {season}, week {week}.",
                ephemeral=True
            )
            return
        
        embed = await self._create_week_schedule_embed(games, season, week)
        await interaction.followup.send(embed=embed)
    
    async def _show_team_schedule(self, interaction: discord.Interaction, season: int, team: str, week: Optional[int]):
        """Show schedule for a specific team."""
        self.logger.debug("Fetching team schedule", season=season, team=team, week=week)
        
        if week:
            # Show team games for specific week
            week_games = await schedule_service.get_week_schedule(season, week)
            team_games = [
                game for game in week_games 
                if game.away_team.abbrev.upper() == team.upper() or game.home_team.abbrev.upper() == team.upper()
            ]
        else:
            # Show team's recent/upcoming games (limited weeks)
            team_games = await schedule_service.get_team_schedule(season, team, weeks=4)
        
        if not team_games:
            week_text = f" for week {week}" if week else ""
            await interaction.followup.send(
                f"❌ No games found for team '{team}'{week_text} in season {season}.",
                ephemeral=True
            )
            return
        
        embed = await self._create_team_schedule_embed(team_games, season, team, week)
        await interaction.followup.send(embed=embed)
    
    async def _show_current_schedule(self, interaction: discord.Interaction, season: int):
        """Show current schedule overview with recent and upcoming games."""
        self.logger.debug("Fetching current schedule overview", season=season)
        
        # Get both recent and upcoming games
        recent_games, upcoming_games = await asyncio.gather(
            schedule_service.get_recent_games(season, weeks_back=1),
            schedule_service.get_upcoming_games(season, weeks_ahead=1)
        )
        
        if not recent_games and not upcoming_games:
            await interaction.followup.send(
                f"❌ No recent or upcoming games found for season {season}.",
                ephemeral=True
            )
            return
        
        embed = await self._create_current_schedule_embed(recent_games, upcoming_games, season)
        await interaction.followup.send(embed=embed)
    
    async def _create_week_schedule_embed(self, games, season: int, week: int) -> discord.Embed:
        """Create an embed for a week's schedule."""
        embed = EmbedTemplate.create_base_embed(
            title=f"📅 Week {week} Schedule - Season {season}",
            color=EmbedColors.PRIMARY
        )
        
        # Group games by series
        series_games = schedule_service.group_games_by_series(games)
        
        schedule_lines = []
        for (team1, team2), series in series_games.items():
            series_summary = await self._format_series_summary(series)
            schedule_lines.append(f"**{team1} vs {team2}**\n{series_summary}")
        
        if schedule_lines:
            embed.add_field(
                name="Games",
                value="\n\n".join(schedule_lines),
                inline=False
            )
        
        # Add week summary
        completed = len([g for g in games if g.is_completed])
        total = len(games)
        embed.add_field(
            name="Week Progress",
            value=f"{completed}/{total} games completed",
            inline=True
        )
        
        embed.set_footer(text=f"Season {season} • Week {week}")
        return embed
    
    async def _create_team_schedule_embed(self, games, season: int, team: str, week: Optional[int]) -> discord.Embed:
        """Create an embed for a team's schedule."""
        week_text = f" - Week {week}" if week else ""
        embed = EmbedTemplate.create_base_embed(
            title=f"📅 {team.upper()} Schedule{week_text} - Season {season}",
            color=EmbedColors.PRIMARY
        )
        
        # Separate completed and upcoming games
        completed_games = [g for g in games if g.is_completed]
        upcoming_games = [g for g in games if not g.is_completed]
        
        if completed_games:
            recent_lines = []
            for game in completed_games[-5:]:  # Last 5 games
                result = "W" if game.winner and game.winner.abbrev.upper() == team.upper() else "L"
                if game.home_team.abbrev.upper() == team.upper():
                    # Team was home
                    recent_lines.append(f"Week {game.week}: {result} vs {game.away_team.abbrev} ({game.score_display})")
                else:
                    # Team was away  
                    recent_lines.append(f"Week {game.week}: {result} @ {game.home_team.abbrev} ({game.score_display})")
            
            embed.add_field(
                name="Recent Results",
                value="\n".join(recent_lines) if recent_lines else "No recent games",
                inline=False
            )
        
        if upcoming_games:
            upcoming_lines = []
            for game in upcoming_games[:5]:  # Next 5 games
                if game.home_team.abbrev.upper() == team.upper():
                    # Team is home
                    upcoming_lines.append(f"Week {game.week}: vs {game.away_team.abbrev}")
                else:
                    # Team is away
                    upcoming_lines.append(f"Week {game.week}: @ {game.home_team.abbrev}")
            
            embed.add_field(
                name="Upcoming Games",
                value="\n".join(upcoming_lines) if upcoming_lines else "No upcoming games",
                inline=False
            )
        
        embed.set_footer(text=f"Season {season} • {team.upper()}")
        return embed
    
    async def _create_week_results_embed(self, games, season: int, week: int) -> discord.Embed:
        """Create an embed for week results."""
        embed = EmbedTemplate.create_base_embed(
            title=f"🏆 Week {week} Results - Season {season}",
            color=EmbedColors.SUCCESS
        )
        
        # Group by series and show results
        series_games = schedule_service.group_games_by_series(games)
        
        results_lines = []
        for (team1, team2), series in series_games.items():
            # Count wins for each team
            team1_wins = len([g for g in series if g.winner and g.winner.abbrev == team1])
            team2_wins = len([g for g in series if g.winner and g.winner.abbrev == team2])
            
            # Series result
            series_result = f"**{team1} {team1_wins}-{team2_wins} {team2}**"
            
            # Individual games
            game_details = []
            for game in series:
                if game.series_game_display:
                    game_details.append(f"{game.series_game_display}: {game.matchup_display}")
            
            results_lines.append(f"{series_result}\n" + "\n".join(game_details))
        
        if results_lines:
            embed.add_field(
                name="Series Results",
                value="\n\n".join(results_lines),
                inline=False
            )
        
        embed.set_footer(text=f"Season {season} • Week {week} • {len(games)} games completed")
        return embed
    
    async def _create_recent_results_embed(self, games, season: int) -> discord.Embed:
        """Create an embed for recent results."""
        embed = EmbedTemplate.create_base_embed(
            title=f"🏆 Recent Results - Season {season}",
            color=EmbedColors.SUCCESS
        )
        
        # Show most recent games
        recent_lines = []
        for game in games[:10]:  # Show last 10 games
            recent_lines.append(f"Week {game.week}: {game.matchup_display}")
        
        if recent_lines:
            embed.add_field(
                name="Latest Games",
                value="\n".join(recent_lines),
                inline=False
            )
        
        embed.set_footer(text=f"Season {season} • Last {len(games)} completed games")
        return embed
    
    async def _create_current_schedule_embed(self, recent_games, upcoming_games, season: int) -> discord.Embed:
        """Create an embed for current schedule overview."""
        embed = EmbedTemplate.create_base_embed(
            title=f"📅 Current Schedule - Season {season}",
            color=EmbedColors.INFO
        )
        
        if recent_games:
            recent_lines = []
            for game in recent_games[:5]:
                recent_lines.append(f"Week {game.week}: {game.matchup_display}")
            
            embed.add_field(
                name="Recent Results",
                value="\n".join(recent_lines),
                inline=False
            )
        
        if upcoming_games:
            upcoming_lines = []
            for game in upcoming_games[:5]:
                upcoming_lines.append(f"Week {game.week}: {game.matchup_display}")
            
            embed.add_field(
                name="Upcoming Games",
                value="\n".join(upcoming_lines),
                inline=False
            )
        
        embed.set_footer(text=f"Season {season}")
        return embed
    
    async def _format_series_summary(self, series) -> str:
        """Format a series summary."""
        lines = []
        for game in series:
            game_display = f"{game.series_game_display}: {game.matchup_display}" if game.series_game_display else game.matchup_display
            lines.append(game_display)
        
        return "\n".join(lines) if lines else "No games"


async def setup(bot: commands.Bot):
    """Load the schedule commands cog."""
    await bot.add_cog(ScheduleCommands(bot))