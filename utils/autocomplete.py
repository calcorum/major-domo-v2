"""
Autocomplete Utilities

Shared autocomplete functions for Discord slash commands.
"""
from typing import List, Optional
import discord
from discord import app_commands

from config import get_config
from services.player_service import player_service
from services.team_service import team_service
from utils.team_utils import get_user_major_league_team


async def player_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> List[app_commands.Choice[str]]:
    """
    Autocomplete for player names with team context prioritization.

    Prioritizes players from the user's team first, then shows other players.

    Args:
        interaction: Discord interaction object
        current: Current input from user

    Returns:
        List of player name choices (user's team players first)
    """
    if len(current) < 2:
        return []

    try:
        # Get user's team for prioritization
        user_team = await get_user_major_league_team(interaction.user.id)

        # Search for players using the search endpoint
        players = await player_service.search_players(current, limit=50, season=get_config().sba_current_season)

        # Separate players by team (user's team vs others)
        user_team_players = []
        other_players = []

        for player in players:
            # Check if player belongs to user's team (any roster section)
            is_users_player = False
            if user_team and hasattr(player, 'team') and player.team:
                # Check if player is from user's major league team or has same base team
                if (player.team.id == user_team.id or
                    (hasattr(player, 'team_id') and player.team_id == user_team.id)):
                    is_users_player = True

            if is_users_player:
                user_team_players.append(player)
            else:
                other_players.append(player)

        # Format choices with team context
        choices = []

        # Add user's team players first (prioritized)
        for player in user_team_players[:15]:  # Limit user team players
            team_info = f"{player.primary_position}"
            if hasattr(player, 'team') and player.team:
                team_info += f" - {player.team.abbrev}"

            choice_name = f"{player.name} ({team_info})"
            choices.append(app_commands.Choice(name=choice_name, value=player.name))

        # Add other players (remaining slots)
        remaining_slots = 25 - len(choices)
        for player in other_players[:remaining_slots]:
            team_info = f"{player.primary_position}"
            if hasattr(player, 'team') and player.team:
                team_info += f" - {player.team.abbrev}"

            choice_name = f"{player.name} ({team_info})"
            choices.append(app_commands.Choice(name=choice_name, value=player.name))

        return choices

    except Exception:
        # Silently fail on autocomplete errors to avoid disrupting user experience
        return []


async def team_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> List[app_commands.Choice[str]]:
    """
    Autocomplete for team abbreviations.

    Args:
        interaction: Discord interaction object
        current: Current input from user

    Returns:
        List of team abbreviation choices
    """
    if len(current) < 1:
        return []

    try:
        # Get all teams for current season
        teams = await team_service.get_teams_by_season(get_config().sba_current_season)

        # Filter teams by current input and limit to 25
        matching_teams = [
            team for team in teams
            if current.lower() in team.abbrev.lower() or current.lower() in team.sname.lower()
        ][:25]

        choices = []
        for team in matching_teams:
            choice_name = f"{team.abbrev} - {team.sname}"
            choices.append(app_commands.Choice(name=choice_name, value=team.abbrev))

        return choices

    except Exception:
        # Silently fail on autocomplete errors
        return []


async def major_league_team_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> List[app_commands.Choice[str]]:
    """
    Autocomplete for Major League team abbreviations only.

    Used for trade commands where only ML team owners should be able to initiate trades.

    Args:
        interaction: Discord interaction object
        current: Current input from user

    Returns:
        List of Major League team abbreviation choices
    """
    if len(current) < 1:
        return []

    try:
        # Get all teams for current season
        all_teams = await team_service.get_teams_by_season(get_config().sba_current_season)

        # Filter to only Major League teams using the model's helper method
        from models.team import RosterType
        ml_teams = [
            team for team in all_teams
            if team.roster_type() == RosterType.MAJOR_LEAGUE
        ]

        # Filter teams by current input and limit to 25
        matching_teams = [
            team for team in ml_teams
            if current.lower() in team.abbrev.lower() or current.lower() in team.sname.lower()
        ][:25]

        choices = []
        for team in matching_teams:
            choice_name = f"{team.abbrev} - {team.sname}"
            choices.append(app_commands.Choice(name=choice_name, value=team.abbrev))

        return choices

    except Exception:
        # Silently fail on autocomplete errors
        return []