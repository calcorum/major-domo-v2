"""
Transaction Logging Utility

Provides centralized function for posting transaction notifications
to the #transaction-log channel.
"""
from typing import List, Optional, Dict
import discord

from config import get_config
from models.transaction import Transaction
from models.team import Team
from models.trade import Trade
from services.trade_builder import TradeBuilder
from views.embeds import EmbedTemplate, EmbedColors
from utils.logging import get_contextual_logger

logger = get_contextual_logger(f'{__name__}')


async def post_transaction_to_log(
    bot: discord.Client,
    transactions: List[Transaction],
    team: Optional[Team] = None
) -> bool:
    """
    Post a transaction to the #transaction-log channel.

    Args:
        bot: Discord bot instance
        transactions: List of Transaction objects to post
        team: Optional team override (if None, determined from transactions)

    Returns:
        True if posted successfully, False otherwise
    """
    try:
        if not transactions:
            logger.warning("No transactions provided to post_transaction_to_log")
            return False

        # Get guild and channel
        config = get_config()
        guild = bot.get_guild(config.guild_id)
        if not guild:
            logger.warning(f"Could not find guild {config.guild_id}")
            return False

        channel = discord.utils.get(guild.text_channels, name='transaction-log')
        if not channel:
            logger.warning("Could not find #transaction-log channel")
            return False

        # Determine the team for the embed (team making the moves)
        if team is None:
            team = await _determine_team_from_transactions(transactions)

        # Build move string
        move_string = ""
        week_num = transactions[0].week
        season = transactions[0].season

        for txn in transactions:
            # Format: PlayerName (sWAR) from OLDTEAM to NEWTEAM
            move_string += (
                f'**{txn.player.name}** ({txn.player.wara:.2f}) '
                f'from {txn.oldteam.abbrev} to {txn.newteam.abbrev}\n'
            )

        # Create embed matching legacy format
        embed = EmbedTemplate.create_base_embed(
            title=f'Week {week_num} Transaction',
            description=team.sname if hasattr(team, 'sname') else team.lname,
            color=EmbedColors.INFO
        )

        # Set team color if available
        if hasattr(team, 'color') and team.color:
            try:
                # Remove # if present and convert to int
                color_hex = team.color.replace('#', '')
                embed.color = discord.Color(int(color_hex, 16))
            except (ValueError, AttributeError):
                pass  # Use default color on error

        # Set team thumbnail if available
        if hasattr(team, 'thumbnail') and team.thumbnail:
            embed.set_thumbnail(url=team.thumbnail)

        # Add player moves field
        embed.add_field(name='Player Moves', value=move_string, inline=False)

        # Add footer with SBA branding using current season from transaction
        embed.set_footer(
            text=f"SBa Season {season}",
            icon_url="https://sombaseball.ddns.net/static/images/sba-logo.png"
        )

        # Post to channel
        await channel.send(embed=embed)
        logger.info(f"Transaction posted to log: {transactions[0].moveid}, {len(transactions)} moves")
        return True

    except Exception as e:
        logger.error(f"Error posting transaction to log: {e}")
        return False


async def _determine_team_from_transactions(transactions: List[Transaction]) -> Team:
    """
    Determine which team to display for the transaction embed.

    Uses the major league affiliate of the team involved in the transaction
    to ensure consistent branding (no MiL or IL team logos).

    Logic:
    - Use newteam's ML affiliate if it's not FA
    - Otherwise use oldteam's ML affiliate if it's not FA
    - Otherwise default to newteam

    Args:
        transactions: List of transactions

    Returns:
        Team to display in the embed (always Major League team)
    """
    first_move = transactions[0]

    # Check newteam first
    if first_move.newteam.abbrev.upper() != 'FA':
        try:
            return await first_move.newteam.major_league_affiliate()
        except Exception as e:
            logger.warning(f"Could not get ML affiliate for {first_move.newteam.abbrev}: {e}")
            return first_move.newteam

    # Check oldteam
    if first_move.oldteam.abbrev.upper() != 'FA':
        try:
            return await first_move.oldteam.major_league_affiliate()
        except Exception as e:
            logger.warning(f"Could not get ML affiliate for {first_move.oldteam.abbrev}: {e}")
            return first_move.oldteam

    # Default to newteam (both are FA)
    return first_move.newteam


async def post_trade_to_log(
    bot: discord.Client,
    builder: TradeBuilder,
    transactions: List[Transaction],
    effective_week: int
) -> bool:
    """
    Post a completed trade to the #transaction-log channel.

    Creates a rich embed showing all teams involved and player movements
    in a clear, organized format.

    Args:
        bot: Discord bot instance
        builder: TradeBuilder with trade details
        transactions: List of created Transaction objects
        effective_week: Week the trade takes effect

    Returns:
        True if posted successfully, False otherwise
    """
    try:
        if not transactions:
            logger.warning("No transactions provided to post_trade_to_log")
            return False

        # Get guild and channel
        config = get_config()
        guild = bot.get_guild(config.guild_id)
        if not guild:
            logger.warning(f"Could not find guild {config.guild_id}")
            return False

        channel = discord.utils.get(guild.text_channels, name='transaction-log')
        if not channel:
            logger.warning("Could not find #transaction-log channel")
            return False

        # Get participating teams
        teams = builder.participating_teams
        team_abbrevs = " ↔ ".join(t.abbrev for t in teams)

        # Create the trade embed
        embed = EmbedTemplate.create_base_embed(
            title=f"🤝 Trade Complete: {team_abbrevs}",
            description=f"**Week {effective_week}** • Season {builder.trade.season}",
            color=EmbedColors.SUCCESS
        )

        # Group transactions by receiving team (who's getting who)
        moves_by_receiver: Dict[str, List[str]] = {}
        for txn in transactions:
            # Get the ML affiliate for proper team naming
            try:
                receiving_team = await txn.newteam.major_league_affiliate()
                receiving_abbrev = receiving_team.abbrev
            except Exception:
                receiving_abbrev = txn.newteam.abbrev

            if receiving_abbrev not in moves_by_receiver:
                moves_by_receiver[receiving_abbrev] = []

            # Format: PlayerName (sWAR) from OLDTEAM
            try:
                sending_team = await txn.oldteam.major_league_affiliate()
                sending_abbrev = sending_team.abbrev
            except Exception:
                sending_abbrev = txn.oldteam.abbrev

            moves_by_receiver[receiving_abbrev].append(
                f"**{txn.player.name}** ({txn.player.wara:.2f}) from {sending_abbrev}"
            )

        # Add a field for each team receiving players
        for team_abbrev, moves in moves_by_receiver.items():
            # Find the team object for potential thumbnail
            team_obj = next((t for t in teams if t.abbrev == team_abbrev), None)
            team_name = team_obj.sname if team_obj else team_abbrev

            embed.add_field(
                name=f"📥 {team_name} receives:",
                value="\n".join(moves),
                inline=False
            )

        # Set thumbnail to first team's logo (or could alternate)
        primary_team = teams[0] if teams else None
        if primary_team and hasattr(primary_team, 'thumbnail') and primary_team.thumbnail:
            embed.set_thumbnail(url=primary_team.thumbnail)

        # Set team color from first team
        if primary_team and hasattr(primary_team, 'color') and primary_team.color:
            try:
                color_hex = primary_team.color.replace('#', '')
                embed.color = discord.Color(int(color_hex, 16))
            except (ValueError, AttributeError):
                pass

        # Add footer with trade ID and SBA branding
        embed.set_footer(
            text=f"Trade ID: {builder.trade_id} • SBA Season {builder.trade.season}",
            icon_url="https://sombaseball.ddns.net/static/images/sba-logo.png"
        )

        # Post to channel
        await channel.send(embed=embed)
        logger.info(f"Trade posted to log: {builder.trade_id}, {len(transactions)} moves, {len(teams)} teams")
        return True

    except Exception as e:
        logger.error(f"Error posting trade to log: {e}")
        return False
