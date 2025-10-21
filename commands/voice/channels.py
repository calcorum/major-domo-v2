"""
Voice Channel Commands

Implements slash commands for creating and managing voice channels for gameplay.
"""
import logging
import random
from typing import Optional

import discord
from discord.ext import commands

from config import get_config
from services.team_service import team_service
from services.schedule_service import ScheduleService
from services.league_service import league_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from views.embeds import EmbedTemplate
from models.team import RosterType

logger = logging.getLogger(f'{__name__}.VoiceChannelCommands')

# Random codenames for public channels
CODENAMES = [
    "Phoenix", "Thunder", "Lightning", "Storm", "Blaze", "Frost", "Shadow", "Nova",
    "Viper", "Falcon", "Wolf", "Eagle", "Tiger", "Shark", "Bear", "Dragon",
    "Alpha", "Beta", "Gamma", "Delta", "Echo", "Foxtrot", "Golf", "Hotel",
    "Crimson", "Azure", "Emerald", "Golden", "Silver", "Bronze", "Platinum", "Diamond"
]


def random_codename() -> str:
    """Generate a random codename for public channels."""
    return random.choice(CODENAMES)


class VoiceChannelCommands(commands.Cog):
    """Voice channel management commands for gameplay."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.VoiceChannelCommands')
        self.schedule_service = ScheduleService()

    # Modern slash command group
    voice_group = discord.app_commands.Group(
        name="voice-channel",
        description="Create voice channels for gameplay"
    )

    async def _get_user_team(self, user_id: int, season: Optional[int] = None):
        """
        Get the user's current team.

        Args:
            user_id: Discord user ID
            season: Season to check (defaults to current)

        Returns:
            Team object or None if not found
        """
        season = season or get_config().sba_current_season
        teams = await team_service.get_teams_by_owner(user_id, season)
        return teams[0] if teams else None

    async def _get_user_major_league_team(self, user_id: int, season: Optional[int] = None):
        """
        Get the user's Major League team for schedule/game purposes.

        Args:
            user_id: Discord user ID
            season: Season to check (defaults to current)

        Returns:
            Major League Team object or None if not found
        """
        season = season or get_config().sba_current_season
        teams = await team_service.get_teams_by_owner(user_id, season)

        # Filter to only Major League teams (3-character abbreviations)
        major_league_teams = [team for team in teams if team.roster_type() == RosterType.MAJOR_LEAGUE]

        return major_league_teams[0] if major_league_teams else None

    async def _create_tracked_channel(
        self,
        interaction: discord.Interaction,
        channel_name: str,
        channel_type: str,
        overwrites: dict
    ) -> discord.VoiceChannel:
        """
        Create a voice channel and add it to tracking.

        Args:
            interaction: Discord interaction
            channel_name: Name for the voice channel
            channel_type: Type of channel ('public' or 'private')
            overwrites: Permission overwrites for the channel

        Returns:
            Created Discord voice channel
        """
        guild = interaction.guild
        voice_category = discord.utils.get(guild.categories, name="Voice Channels")

        # Create the voice channel
        channel = await guild.create_voice_channel(
            name=channel_name,
            overwrites=overwrites,
            category=voice_category
        )

        # Add to cleanup service tracking
        if hasattr(self.bot, 'voice_cleanup_service'):
            cleanup_service = self.bot.voice_cleanup_service  # type: ignore[attr-defined]
            cleanup_service.tracker.add_channel(channel, channel_type, interaction.user.id)
        else:
            self.logger.warning("Voice cleanup service not available, channel won't be tracked")

        return channel

    @voice_group.command(name="public", description="Create a public voice channel")
    @logged_command("/voice-channel public")
    async def create_public_channel(self, interaction: discord.Interaction):
        """Create a public voice channel for gameplay."""
        await interaction.response.defer()

        # Verify user has a Major League team
        user_team = await self._get_user_major_league_team(interaction.user.id)
        if not user_team:
            embed = EmbedTemplate.error(
                title="No Major League Team Found",
                description="❌ You must own a Major League team to create voice channels.\n\n"
                           "Contact a league administrator if you believe this is an error."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Create channel with public permissions
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(speak=True, connect=True)
        }

        channel_name = f"Gameplay {random_codename()}"

        try:
            channel = await self._create_tracked_channel(
                interaction, channel_name, "public", overwrites
            )

            # Get actual cleanup time from service
            cleanup_minutes = getattr(self.bot, 'voice_cleanup_service', None)
            cleanup_time = cleanup_minutes.empty_threshold if cleanup_minutes else 15

            embed = EmbedTemplate.success(
                title="Voice Channel Created",
                description=f"✅ Created public voice channel {channel.mention}\n\n"
                           f"**Channel:** {channel.name}\n"
                           f"**Type:** Public (everyone can speak)\n"
                           f"**Auto-cleanup:** {cleanup_time} minutes after becoming empty"
            )

            await interaction.followup.send(embed=embed)

        except discord.Forbidden:
            embed = EmbedTemplate.error(
                title="Permission Error",
                description="❌ I don't have permission to create voice channels.\n\n"
                           "Please contact a server administrator."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error(f"Error creating public voice channel: {e}")
            embed = EmbedTemplate.error(
                title="Creation Failed",
                description="❌ An error occurred while creating the voice channel.\n\n"
                           "Please try again or contact support."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @voice_group.command(name="private", description="Create a private team vs team voice channel")
    @logged_command("/voice-channel private")
    async def create_private_channel(self, interaction: discord.Interaction):
        """Create a private voice channel for team matchup."""
        await interaction.response.defer()

        # Verify user has a Major League team
        user_team = await self._get_user_major_league_team(interaction.user.id)
        if not user_team:
            embed = EmbedTemplate.error(
                title="No Major League Team Found",
                description="❌ You must own a Major League team to create private voice channels.\n\n"
                           "Private channels are for scheduled games between Major League teams.\n"
                           "Contact a league administrator if you believe this is an error."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get current league info
        try:
            current_info = await league_service.get_current_state()
            if current_info is None:
                embed = EmbedTemplate.error(
                    title="League Info Error",
                    description="❌ Unable to retrieve current league information.\n\n"
                               "Please try again later."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            current_season = current_info.season
            current_week = current_info.week
        except Exception as e:
            self.logger.error(f"Error getting current league info: {e}")
            embed = EmbedTemplate.error(
                title="League Info Error",
                description="❌ Unable to retrieve current league information.\n\n"
                           "Please try again later."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Find opponent from current week's schedule
        try:
            # Get all games for the current week
            week_games = await self.schedule_service.get_week_schedule(current_season, current_week)

            # Filter for games involving this team that haven't been completed
            team_abbrev_upper = user_team.abbrev.upper()
            current_week_games = [
                g for g in week_games
                if (g.away_team.abbrev.upper() == team_abbrev_upper or
                    g.home_team.abbrev.upper() == team_abbrev_upper)
                and not g.is_completed
            ]

            if not current_week_games:
                embed = EmbedTemplate.warning(
                    title="No Games Found",
                    description=f"❌ No upcoming games found for {user_team.abbrev} in week {current_week}.\n\n"
                               f"You may be between series or all games for this week are complete."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            game = current_week_games[0]  # Use first upcoming game
            opponent_team = game.away_team if game.home_team.id == user_team.id else game.home_team

        except Exception as e:
            self.logger.error(f"Error getting team schedule: {e}")
            embed = EmbedTemplate.error(
                title="Schedule Error",
                description="❌ Unable to retrieve your team's schedule.\n\n"
                           "Please try again later."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Setup permissions for team roles
        user_team_role = discord.utils.get(interaction.guild.roles, name=user_team.lname)
        opponent_team_role = discord.utils.get(interaction.guild.roles, name=opponent_team.lname)

        # Start with default permissions (everyone can connect but not speak)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(speak=False, connect=True)
        }

        # Add speaking permissions for team roles
        team_roles_found = []
        if user_team_role:
            overwrites[user_team_role] = discord.PermissionOverwrite(speak=True, connect=True)
            team_roles_found.append(user_team.lname)

        if opponent_team_role:
            overwrites[opponent_team_role] = discord.PermissionOverwrite(speak=True, connect=True)
            team_roles_found.append(opponent_team.lname)

        # Create private channel with team names
        away_name = game.away_team.sname
        home_name = game.home_team.sname
        channel_name = f"{away_name} vs {home_name}"

        try:
            channel = await self._create_tracked_channel(
                interaction, channel_name, "private", overwrites
            )

            # Get actual cleanup time from service
            cleanup_minutes = getattr(self.bot, 'voice_cleanup_service', None)
            cleanup_time = cleanup_minutes.empty_threshold if cleanup_minutes else 15

            embed = EmbedTemplate.success(
                title="Private Voice Channel Created",
                description=f"✅ Created private voice channel {channel.mention}\n\n"
                           f"**Matchup:** {away_name} vs {home_name}\n"
                           f"**Type:** Private (team members only can speak)\n"
                           f"**Auto-cleanup:** {cleanup_time} minutes after becoming empty"
            )

            embed.add_field(
                name="Speaking Permissions",
                value=f"🎤 **{user_team.abbrev}** - {user_team.lname}\n"
                      f"🎤 **{opponent_team.abbrev}** - {opponent_team.lname}\n"
                      f"👂 Everyone else can listen",
                inline=False
            )

            if len(team_roles_found) < 2:
                missing_roles = []
                if not user_team_role:
                    missing_roles.append(user_team.lname)
                if not opponent_team_role:
                    missing_roles.append(opponent_team.lname)

                embed.add_field(
                    name="⚠️ Missing Roles",
                    value=f"Could not find Discord roles for: {', '.join(missing_roles)}\n"
                          f"These teams may not have speaking permissions.",
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        except discord.Forbidden:
            embed = EmbedTemplate.error(
                title="Permission Error",
                description="❌ I don't have permission to create voice channels.\n\n"
                           "Please contact a server administrator."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error(f"Error creating private voice channel: {e}")
            embed = EmbedTemplate.error(
                title="Creation Failed",
                description="❌ An error occurred while creating the voice channel.\n\n"
                           "Please try again or contact support."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    # Deprecated prefix commands with migration messages
    @commands.command(name="vc", aliases=["voice", "gameplay"])
    async def deprecated_public_voice(self, ctx: commands.Context):
        """Deprecated command - redirect to new slash command."""
        embed = EmbedTemplate.info(
            title="Command Deprecated",
            description=(
                "The `!vc` command has been deprecated.\n\n"
                "**Please use:** `/voice-channel public` for your voice channel needs.\n\n"
                "The new slash commands provide better functionality and organization!"
            )
        )
        embed.set_footer(text="💡 Tip: Type /voice-channel and see the available options!")
        await ctx.send(embed=embed)

    @commands.command(name="private")
    async def deprecated_private_voice(self, ctx: commands.Context):
        """Deprecated command - redirect to new slash command."""
        embed = EmbedTemplate.info(
            title="Command Deprecated",
            description=(
                "The `!private` command has been deprecated.\n\n"
                "**Please use:** `/voice-channel private` for your private team channel needs.\n\n"
                "The new slash commands provide better functionality and organization!"
            )
        )
        embed.set_footer(text="💡 Tip: Type /voice-channel and see the available options!")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """Load the voice channel commands cog."""
    await bot.add_cog(VoiceChannelCommands(bot))