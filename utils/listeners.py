"""
Message Listener Utilities

Provides reusable components for on_message listeners including common message
filtering patterns.
"""
import logging
from typing import Callable
import discord
from config import get_config

logger = logging.getLogger(f'{__name__}.message_filters')


def should_ignore_bot_messages(message: discord.Message) -> bool:
    """
    Check if message should be ignored because it's from a bot.

    Args:
        message: Discord message object

    Returns:
        bool: True if message should be ignored (author is a bot)
    """
    return message.author.bot


def should_ignore_empty_messages(message: discord.Message) -> bool:
    """
    Check if message should be ignored because it has no content.

    Args:
        message: Discord message object

    Returns:
        bool: True if message should be ignored (no content)
    """
    return not message.content


def should_ignore_command_prefix(message: discord.Message, prefix: str = '!') -> bool:
    """
    Check if message should be ignored because it starts with a command prefix.

    Args:
        message: Discord message object
        prefix: Command prefix to check for (default: '!')

    Returns:
        bool: True if message should be ignored (starts with prefix)
    """
    return message.content.startswith(prefix)


def should_ignore_dms(message: discord.Message) -> bool:
    """
    Check if message should be ignored because it's a DM (no guild).

    Args:
        message: Discord message object

    Returns:
        bool: True if message should be ignored (no guild)
    """
    return not message.guild


def should_ignore_wrong_guild(message: discord.Message) -> bool:
    """
    Check if message should be ignored because it's from the wrong guild.

    Args:
        message: Discord message object

    Returns:
        bool: True if message should be ignored (wrong guild or no guild)
    """
    if not message.guild:
        return True

    guild_id = get_config().guild_id
    return message.guild.id != guild_id


def should_process_message(
    message: discord.Message,
    *filters: Callable[[discord.Message], bool]
) -> bool:
    """
    Check if a message should be processed based on provided filters.

    Args:
        message: Discord message object
        *filters: Variable number of filter functions that return True if message should be ignored

    Returns:
        bool: True if message should be processed (all filters returned False),
              False if message should be ignored (any filter returned True)

    Example:
        if should_process_message(
            message,
            should_ignore_bot_messages,
            should_ignore_empty_messages,
            should_ignore_dms,
            should_ignore_wrong_guild
        ):
            # Process the message
            pass
    """
    for filter_func in filters:
        if filter_func(message):
            return False

    return True


# Pre-defined filter sets for common use cases

BASIC_FILTERS = (
    should_ignore_bot_messages,
    should_ignore_empty_messages,
)
"""Basic filters: Ignore bots and empty messages."""

GUILD_FILTERS = (
    should_ignore_bot_messages,
    should_ignore_empty_messages,
    should_ignore_dms,
    should_ignore_wrong_guild,
)
"""Guild filters: Basic filters + guild validation."""

COMMAND_FILTERS = (
    should_ignore_bot_messages,
    should_ignore_empty_messages,
    should_ignore_command_prefix,
    should_ignore_dms,
    should_ignore_wrong_guild,
)
"""Command filters: Guild filters + command prefix check."""
