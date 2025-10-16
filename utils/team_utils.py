"""
Team Utilities

Common team-related helper functions used across commands.
"""
from typing import Optional
import discord

from models.team import Team
from services.team_service import team_service


async def get_user_major_league_team(
    user_id: int,
    season: int = get_config().sba_current_season
) -> Optional[Team]:
    """
    Get the major league team owned by a Discord user.

    This is a very common pattern used across many commands, so it's
    extracted into a utility function for consistency and reusability.

    Args:
        user_id: Discord user ID
        season: Season to check (defaults to current season)

    Returns:
        Team object if user owns a major league team, None otherwise
    """
    try:
        major_league_teams = await team_service.get_teams_by_owner(
            user_id,
            season,
            roster_type="ml"
        )

        if major_league_teams:
            return major_league_teams[0]  # Return first ML team

        return None

    except Exception:
        # Silently fail and return None - let calling code handle the error
        return None


async def validate_user_has_team(
    interaction: discord.Interaction,
    season: int = get_config().sba_current_season
) -> Optional[Team]:
    """
    Validate that a user has a major league team and send error message if not.

    This combines team lookup with standard error messaging for consistency.

    Args:
        interaction: Discord interaction object
        season: Season to check (defaults to current season)

    Returns:
        Team object if user has a team, None if not (error message already sent)
    """
    user_team = await get_user_major_league_team(interaction.user.id, season)

    if not user_team:
        await interaction.followup.send(
            "❌ You don't appear to own a major league team in the current season.",
            ephemeral=True
        )
        return None

    return user_team


async def get_team_by_abbrev_with_validation(
    team_abbrev: str,
    interaction: discord.Interaction,
    season: int = get_config().sba_current_season
) -> Optional[Team]:
    """
    Get a team by abbreviation with standard error messaging.

    Args:
        team_abbrev: Team abbreviation to look up
        interaction: Discord interaction object for error messaging
        season: Season to check (defaults to current season)

    Returns:
        Team object if found, None if not (error message already sent)
    """
from config import get_config
    try:
        team = await team_service.get_team_by_abbrev(team_abbrev, season)

        if not team:
            await interaction.followup.send(
                f"❌ Team '{team_abbrev}' not found.",
                ephemeral=True
            )
            return None

        return team

    except Exception:
        await interaction.followup.send(
            f"❌ Error looking up team '{team_abbrev}'. Please try again.",
            ephemeral=True
        )
        return None