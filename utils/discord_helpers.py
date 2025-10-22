"""
Discord Helper Utilities

Common Discord-related helper functions for channel lookups,
message sending, and formatting.
"""
from typing import Optional, List
import discord
from discord.ext import commands

from models.play import Play
from models.team import Team
from utils.logging import get_contextual_logger

logger = get_contextual_logger(__name__)


async def get_channel_by_name(
    bot: commands.Bot,
    channel_name: str
) -> Optional[discord.TextChannel]:
    """
    Get a text channel by name from the configured guild.

    Args:
        bot: Discord bot instance
        channel_name: Name of the channel to find

    Returns:
        TextChannel if found, None otherwise
    """
    from config import get_config

    config = get_config()
    guild_id = config.guild_id

    if not guild_id:
        logger.error("GUILD_ID not configured")
        return None

    guild = bot.get_guild(guild_id)
    if not guild:
        logger.error(f"Guild {guild_id} not found")
        return None

    channel = discord.utils.get(guild.text_channels, name=channel_name)

    if not channel:
        logger.warning(f"Channel '{channel_name}' not found in guild {guild_id}")
        return None

    return channel


async def send_to_channel(
    bot: commands.Bot,
    channel_name: str,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None
) -> bool:
    """
    Send a message to a channel by name.

    Args:
        bot: Discord bot instance
        channel_name: Name of the channel
        content: Text content to send
        embed: Embed to send

    Returns:
        True if message sent successfully, False otherwise
    """
    channel = await get_channel_by_name(bot, channel_name)

    if not channel:
        logger.error(f"Cannot send to channel '{channel_name}' - not found")
        return False

    try:
        # Build kwargs to avoid passing None for embed
        kwargs = {}
        if content is not None:
            kwargs['content'] = content
        if embed is not None:
            kwargs['embed'] = embed

        await channel.send(**kwargs)
        logger.info(f"Sent message to #{channel_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to send message to #{channel_name}: {e}")
        return False


def format_key_plays(
    plays: List[Play],
    away_team: Team,
    home_team: Team
) -> str:
    """
    Format top plays into embed field text.

    Args:
        plays: List of Play objects (should be sorted by WPA)
        away_team: Away team object
        home_team: Home team object

    Returns:
        Formatted string for embed field, or empty string if no plays
    """
    if not plays:
        return ""

    key_plays_text = ""

    for play in plays:
        # Use the Play.descriptive_text() method (already includes score)
        play_description = play.descriptive_text(away_team, home_team)
        key_plays_text += f"{play_description}\n"

    return key_plays_text


async def set_channel_visibility(
    channel: discord.TextChannel,
    visible: bool,
    reason: Optional[str] = None
) -> bool:
    """
    Set channel visibility for @everyone.

    The bot's permissions are based on its role, not @everyone, so the bot
    will retain access even when @everyone view permission is removed.

    Args:
        channel: Discord text channel to modify
        visible: If True, grant @everyone view permission; if False, deny it
        reason: Optional reason for audit log

    Returns:
        True if permissions updated successfully, False otherwise
    """
    try:
        guild = channel.guild
        everyone_role = guild.default_role

        if visible:
            # Grant @everyone permission to view channel
            default_reason = "Channel made visible to all members"
            await channel.set_permissions(
                everyone_role,
                view_channel=True,
                reason=reason or default_reason
            )
            logger.info(f"Set #{channel.name} to VISIBLE for @everyone")
        else:
            # Remove @everyone view permission
            default_reason = "Channel hidden from members"
            await channel.set_permissions(
                everyone_role,
                view_channel=False,
                reason=reason or default_reason
            )
            logger.info(f"Set #{channel.name} to HIDDEN for @everyone")

        return True

    except discord.Forbidden:
        logger.error(f"Missing permissions to modify #{channel.name} permissions")
        return False
    except Exception as e:
        logger.error(f"Error setting channel visibility for #{channel.name}: {e}")
        return False
