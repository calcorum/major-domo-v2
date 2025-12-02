"""
Flexible command permission system.

This module provides decorators for controlling command access across different
servers and user types:
- @global_command: Available in all servers
- @league_only: Only available in the league server
- @requires_team: User must have a team (works with global commands)
"""
import logging
from functools import wraps
from typing import Optional, Callable

import discord
from discord.ext import commands

from config import get_config

logger = logging.getLogger(__name__)


class PermissionError(Exception):
    """Raised when a user doesn't have permission to use a command."""
    pass


async def get_user_team(user_id: int) -> Optional[dict]:
    """
    Check if a user has a team in the league.

    This function is cached because TeamService.get_team_by_owner() is already
    cached with a 30-minute TTL. The cached service method avoids repeated
    API calls when the same user runs multiple commands.

    Args:
        user_id: Discord user ID

    Returns:
        Team data dict if user has a team, None if user has no team

    Raises:
        Exception: If there's an error communicating with the API (network, timeout, etc.)
                   Allows caller to distinguish between "no team" vs "error checking"

    Note:
        The underlying service method uses @cached_single_item decorator,
        so this function benefits from automatic caching without additional
        implementation.
    """
    # Import here to avoid circular imports
    from services.team_service import team_service

    # Get team by owner (Discord user ID)
    # This call is automatically cached by TeamService
    config = get_config()
    team = await team_service.get_team_by_owner(
        owner_id=user_id,
        season=config.sba_season
    )

    if team:
        logger.debug(f"User {user_id} has team: {team.lname}")
        return {
            'id': team.id,
            'name': team.lname,
            'abbrev': team.abbrev,
            'season': team.season
        }

    logger.debug(f"User {user_id} does not have a team")
    return None


def is_league_server(guild_id: int) -> bool:
    """Check if a guild is the league server."""
    config = get_config()
    return guild_id == config.guild_id


def league_only():
    """
    Decorator to restrict a command to the league server only.

    Usage:
        @discord.app_commands.command(name="team")
        @league_only()
        async def team_command(self, interaction: discord.Interaction):
            # Only executes in league server
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            # Check if in a guild
            if not interaction.guild:
                await interaction.response.send_message(
                    "❌ This command can only be used in a server.",
                    ephemeral=True
                )
                return

            # Check if in league server
            if not is_league_server(interaction.guild.id):
                await interaction.response.send_message(
                    "❌ This command is only available in the SBa league server.",
                    ephemeral=True
                )
                return

            return await func(self, interaction, *args, **kwargs)

        return wrapper
    return decorator


def requires_team():
    """
    Decorator to require a user to have a team in the league.
    Can be used on global commands to restrict to league participants.

    Usage:
        @discord.app_commands.command(name="mymoves")
        @requires_team()
        async def mymoves_command(self, interaction: discord.Interaction):
            # Only executes if user has a team
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            try:
                # Check if user has a team
                team = await get_user_team(interaction.user.id)

                if team is None:
                    await interaction.response.send_message(
                        "❌ This command requires you to have a team in the SBa league. Contact an admin if you believe this is an error.",
                        ephemeral=True
                    )
                    return

                # Store team info in interaction for command to use
                # This allows commands to access the team without another lookup
                interaction.extras['user_team'] = team

                return await func(self, interaction, *args, **kwargs)

            except Exception as e:
                # Log the error for debugging
                logger.error(f"Error checking team ownership for user {interaction.user.id}: {e}", exc_info=True)

                # Provide helpful error message to user
                await interaction.response.send_message(
                    "❌ Unable to verify team ownership due to a temporary error. Please try again in a moment. "
                    "If this persists, contact an admin.",
                    ephemeral=True
                )
                return

        return wrapper
    return decorator


def global_command():
    """
    Decorator to explicitly mark a command as globally available.
    This is mainly for documentation purposes - commands are global by default.

    Usage:
        @discord.app_commands.command(name="roll")
        @global_command()
        async def roll_command(self, interaction: discord.Interaction):
            # Available in all servers
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            return await func(self, interaction, *args, **kwargs)

        return wrapper
    return decorator


def admin_only():
    """
    Decorator to restrict a command to server administrators.
    Works in any server, but requires admin permissions.

    Usage:
        @discord.app_commands.command(name="sync")
        @admin_only()
        async def sync_command(self, interaction: discord.Interaction):
            # Only executes for admins
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            # Check if user is guild admin
            if not interaction.guild:
                await interaction.response.send_message(
                    "❌ This command can only be used in a server.",
                    ephemeral=True
                )
                return

            # Check if user has admin permissions
            if not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message(
                    "❌ Unable to verify permissions.",
                    ephemeral=True
                )
                return

            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ This command requires administrator permissions.",
                    ephemeral=True
                )
                return

            return await func(self, interaction, *args, **kwargs)

        return wrapper
    return decorator


# Decorator can be combined for complex permissions
def league_admin_only():
    """
    Decorator requiring both league server AND admin permissions.

    Works with BOTH slash commands (Interaction) and prefix commands (Context).

    Usage (slash):
        @discord.app_commands.command(name="force-sync")
        @league_admin_only()
        async def force_sync(self, interaction: discord.Interaction):
            # Only league server admins can use this

    Usage (prefix):
        @commands.command(name="admin-sync")
        @league_admin_only()
        async def admin_sync_prefix(self, ctx: commands.Context):
            # Only league server admins can use this
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx_or_interaction, *args, **kwargs):
            # Detect if this is a Context (prefix) or Interaction (slash)
            is_prefix = isinstance(ctx_or_interaction, commands.Context)

            if is_prefix:
                ctx = ctx_or_interaction
                guild = ctx.guild
                author = ctx.author

                async def send_error(msg: str):
                    await ctx.send(msg)
            else:
                interaction = ctx_or_interaction
                guild = interaction.guild
                author = interaction.user

                async def send_error(msg: str):
                    await interaction.response.send_message(msg, ephemeral=True)

            # Check guild
            if not guild:
                await send_error("❌ This command can only be used in a server.")
                return

            # Check if league server
            if not is_league_server(guild.id):
                await send_error("❌ This command is only available in the SBa league server.")
                return

            # Check admin permissions
            if not isinstance(author, discord.Member):
                await send_error("❌ Unable to verify permissions.")
                return

            if not author.guild_permissions.administrator:
                await send_error("❌ This command requires administrator permissions.")
                return

            return await func(self, ctx_or_interaction, *args, **kwargs)

        return wrapper
    return decorator
