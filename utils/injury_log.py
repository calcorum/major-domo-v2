"""
Injury Log Posting Utility

Provides functions for posting injury information to Discord channels:
- #injury-log: Two embeds showing current injuries by team and by return week
- #sba-network-news: Individual injury announcements
"""
from typing import Optional, Dict, List, Any
from collections import defaultdict

import discord

from config import get_config
from models.player import Player
from models.team import Team
from services.injury_service import injury_service
from services.team_service import team_service
from views.embeds import EmbedTemplate, EmbedColors
from utils.logging import get_contextual_logger

logger = get_contextual_logger(f'{__name__}')


async def get_major_league_team_name(team_data: dict, season: int) -> str:
    """
    Get the Major League team name from player's team data.

    Args:
        team_data: Team dictionary from API response
        season: Current season number

    Returns:
        Major League team short name (sname)
    """
    if not team_data:
        return "Unknown"

    abbrev = team_data.get('abbrev', '')

    # If abbreviation is 3 chars or less, it's already ML
    if len(abbrev) <= 3:
        return team_data.get('sname', abbrev)

    # Extract base abbreviation for MiL/IL teams
    abbrev_lower = abbrev.lower()
    if abbrev_lower.endswith('mil'):
        base_abbrev = abbrev[:-3]
    elif abbrev_lower.endswith('il'):
        base_abbrev = abbrev[:-2]
    else:
        return team_data.get('sname', abbrev)

    # Look up the ML team
    try:
        ml_team = await team_service.get_team_by_abbrev(base_abbrev, season)
        if ml_team:
            return ml_team.sname
    except Exception as e:
        logger.warning(f"Could not get ML team for {abbrev}: {e}")

    return team_data.get('sname', abbrev)


async def update_injury_log_channel(
    bot: discord.Client,
    season: int
) -> bool:
    """
    Update the #injury-log channel with current injuries.

    Creates two embeds:
    1. Current injuries grouped by Major League team
    2. Current injuries grouped by return week

    Args:
        bot: Discord bot instance
        season: Current season number

    Returns:
        True if successful, False otherwise
    """
    try:
        config = get_config()
        guild = bot.get_guild(config.guild_id)

        if not guild:
            logger.warning(f"Could not find guild {config.guild_id}")
            return False

        channel = discord.utils.get(guild.text_channels, name='injury-log')
        if not channel:
            logger.warning("Could not find #injury-log channel")
            return False

        # Get all active injuries
        injuries_raw = await injury_service.get_all_active_injuries_raw(season)

        if not injuries_raw:
            logger.info("No active injuries found for injury log update")
            # Still update the channel with "no injuries" message
            await _clear_and_post_no_injuries(channel, season)
            return True

        # Group injuries by team and by week
        injuries_by_team: Dict[str, List[dict]] = defaultdict(list)
        injuries_by_week: Dict[int, List[dict]] = defaultdict(list)

        for injury in injuries_raw:
            player = injury.get('player', {})
            team_data = player.get('team', {})

            # Get ML team name for grouping
            ml_team_name = await get_major_league_team_name(team_data, season)

            injuries_by_team[ml_team_name].append({
                'name': player.get('name', 'Unknown'),
                'il_return': player.get('il_return', 'TBD'),
                'end_week': injury.get('end_week', 0)
            })

            end_week = injury.get('end_week', 0)
            injuries_by_week[end_week].append({
                'name': player.get('name', 'Unknown'),
                'il_return': player.get('il_return', 'TBD')
            })

        # Create team embed
        team_embed = EmbedTemplate.create_base_embed(
            title="🏥 Current Injuries by Team",
            description="Player Name (Return Date)",
            color=EmbedColors.WARNING,
            timestamp=True
        )
        team_embed.set_thumbnail(url=config.sba_logo_url)

        # Sort teams alphabetically and add fields
        for team_name in sorted(injuries_by_team.keys()):
            players = injuries_by_team[team_name]
            team_string = '\n'.join(
                f"{p['name']} ({p['il_return']})"
                for p in players
            )

            # Discord field value limit is 1024 chars
            if len(team_string) > 1024:
                team_string = team_string[:1020] + "..."

            team_embed.add_field(
                name=f"{team_name} ({len(players)})",
                value=team_string,
                inline=True
            )

        team_embed.set_footer(
            text=f"SBa Season {season} • {len(injuries_raw)} active injuries",
            icon_url=config.sba_logo_url
        )

        # Create week embed
        week_embed = EmbedTemplate.create_base_embed(
            title="📅 Current Injuries by Return Week",
            description="Player Name (Return Date)",
            color=EmbedColors.INFO,
            timestamp=True
        )
        week_embed.set_thumbnail(url=config.sba_logo_url)

        # Sort weeks numerically and add fields
        for week_num in sorted(injuries_by_week.keys()):
            players = injuries_by_week[week_num]
            week_string = '\n'.join(
                f"{p['name']} ({p['il_return']})"
                for p in players
            )

            # Discord field value limit is 1024 chars
            if len(week_string) > 1024:
                week_string = week_string[:1020] + "..."

            week_embed.add_field(
                name=f"Week {week_num} ({len(players)})",
                value=week_string,
                inline=True
            )

        week_embed.set_footer(
            text=f"SBa Season {season} • Sorted by earliest return",
            icon_url=config.sba_logo_url
        )

        # Clear old messages and post new ones
        try:
            await channel.purge(limit=25)
        except discord.errors.Forbidden:
            logger.warning("Could not purge messages in #injury-log (missing permissions)")
        except Exception as e:
            logger.warning(f"Error purging messages in #injury-log: {e}")

        await channel.send(embed=team_embed)
        await channel.send(embed=week_embed)

        logger.info(f"Updated injury log: {len(injuries_raw)} injuries across {len(injuries_by_team)} teams")
        return True

    except Exception as e:
        logger.error(f"Error updating injury log channel: {e}")
        return False


async def _clear_and_post_no_injuries(channel: discord.TextChannel, season: int) -> None:
    """Post a 'no injuries' message when there are no active injuries."""
    config = get_config()

    try:
        await channel.purge(limit=25)
    except Exception:
        pass

    embed = EmbedTemplate.create_base_embed(
        title="🏥 Current Injuries",
        description="No active injuries at this time.",
        color=EmbedColors.SUCCESS,
        timestamp=True
    )
    embed.set_thumbnail(url=config.sba_logo_url)
    embed.set_footer(
        text=f"SBa Season {season}",
        icon_url=config.sba_logo_url
    )

    await channel.send(embed=embed)


async def post_injury_news(
    bot: discord.Client,
    player: Player,
    injury_games: int,
    return_date: str,
    season: int
) -> bool:
    """
    Post an injury announcement to #sba-network-news.

    Args:
        bot: Discord bot instance
        player: Player object who was injured
        injury_games: Number of games player will miss
        return_date: Return date in w##g# format
        season: Current season number

    Returns:
        True if successful, False otherwise
    """
    try:
        config = get_config()
        guild = bot.get_guild(config.guild_id)

        if not guild:
            logger.warning(f"Could not find guild {config.guild_id}")
            return False

        channel = discord.utils.get(
            guild.text_channels,
            name=config.sba_network_news_channel
        )
        if not channel:
            logger.warning(f"Could not find #{config.sba_network_news_channel} channel")
            return False

        # Determine team info
        team_name = "Unknown Team"
        team_color = EmbedColors.WARNING
        team_thumbnail = None

        if player.team:
            team_name = player.team.sname or player.team.lname
            if player.team.color:
                try:
                    team_color = int(player.team.color, 16)
                except ValueError:
                    pass
            team_thumbnail = player.team.thumbnail

        # Create news embed
        embed = EmbedTemplate.create_base_embed(
            title="🚑 Injury Report",
            description=f"**{player.name}** has been placed on the injured list.",
            color=team_color,
            timestamp=True
        )

        embed.add_field(
            name="Player",
            value=f"{player.name} ({player.primary_position})",
            inline=True
        )

        embed.add_field(
            name="Team",
            value=team_name,
            inline=True
        )

        embed.add_field(
            name="Duration",
            value=f"{injury_games} game{'s' if injury_games != 1 else ''}",
            inline=True
        )

        embed.add_field(
            name="Expected Return",
            value=return_date,
            inline=True
        )

        if team_thumbnail:
            embed.set_thumbnail(url=team_thumbnail)

        embed.set_footer(
            text=f"SBa Season {season}",
            icon_url=config.sba_logo_url
        )

        await channel.send(embed=embed)
        logger.info(f"Posted injury news for {player.name}: {injury_games} games")
        return True

    except Exception as e:
        logger.error(f"Error posting injury news: {e}")
        return False


async def post_injury_and_update_log(
    bot: discord.Client,
    player: Player,
    injury_games: int,
    return_date: str,
    season: int
) -> None:
    """
    Convenience function to post injury news and update injury log.

    This is the main entry point for injury logging after an injury is recorded.
    It handles both the news announcement and the full injury log update.

    Args:
        bot: Discord bot instance
        player: Player object who was injured
        injury_games: Number of games player will miss
        return_date: Return date in w##g# format
        season: Current season number
    """
    # Post to sba-network-news
    await post_injury_news(bot, player, injury_games, return_date, season)

    # Update injury-log channel with all current injuries
    await update_injury_log_channel(bot, season)
