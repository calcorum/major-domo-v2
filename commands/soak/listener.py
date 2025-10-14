"""
Soak Message Listener

Monitors all messages for soak mentions and responds with disappointment GIFs.
"""
import re
import os
import logging
import discord
from discord.ext import commands

from .tracker import SoakTracker
from .giphy_service import get_tier_for_seconds, get_disappointment_gif

logger = logging.getLogger(f'{__name__}.SoakListener')

# Regex pattern to detect soak variations (whole word only)
SOAK_PATTERN = re.compile(r'\b(soak|soaking|soaked|soaker)\b', re.IGNORECASE)


class SoakListener(commands.Cog):
    """Listens for soak mentions and responds with appropriate disappointment."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tracker = SoakTracker()
        logger.info("SoakListener cog initialized")

    @commands.Cog.listener(name='on_message')
    async def on_message_listener(self, message: discord.Message):
        """
        Listen for messages containing soak mentions.

        Args:
            message: Discord message object
        """
        # Ignore bot messages to prevent loops
        if message.author.bot:
            return

        # Ignore messages that start with command prefix (legacy pattern)
        if message.content.startswith('!'):
            return

        # Check guild ID matches configured guild (optional security)
        guild_id = os.environ.get('GUILD_ID')
        if guild_id and message.guild and message.guild.id != int(guild_id):
            return

        # Check if message contains soak
        if not SOAK_PATTERN.search(message.content):
            return

        logger.info(f"Soak detected in message from {message.author.name} (ID: {message.author.id})")

        try:
            # Get time since last soak
            time_since = self.tracker.get_time_since_last_soak()

            # Determine disappointment tier
            seconds_elapsed = int(time_since.total_seconds()) if time_since else None
            tier_key = get_tier_for_seconds(seconds_elapsed)

            logger.info(f"Disappointment tier: {tier_key} (elapsed: {seconds_elapsed}s)")

            # Format time string for message
            time_string = self._format_time_string(time_since)

            # Fetch GIF from Giphy
            gif_url = await get_disappointment_gif(tier_key)

            # Post response to channel
            try:
                if gif_url:
                    # Post message with GIF
                    await message.channel.send(f"It has been [{time_string}]({gif_url}) since soaking was mentioned.")
                else:
                    # Fallback to text-only with emoji if GIF fetch failed
                    await message.channel.send(f"😞 It has been {time_string} since soaking was mentioned.")
                    logger.warning("Failed to fetch GIF, sent text-only response")

            except discord.Forbidden:
                logger.error(f"Missing permissions to send message in channel {message.channel.id}")
            except Exception as e:
                logger.error(f"Error sending soak response: {e}")

            # Record this soak mention
            self.tracker.record_soak(
                user_id=message.author.id,
                username=message.author.name,
                display_name=message.author.display_name,
                channel_id=message.channel.id,
                message_id=message.id
            )

        except Exception as e:
            logger.error(f"Error processing soak mention: {e}", exc_info=True)

    def _format_time_string(self, time_since) -> str:
        """
        Format timedelta into human-readable string.

        Args:
            time_since: timedelta object or None

        Returns:
            Formatted time string (e.g., "5 minutes", "2 hours", "3 days")
        """
        if time_since is None:
            return "never"

        total_seconds = int(time_since.total_seconds())

        if total_seconds < 60:
            # Less than 1 minute
            return f"{total_seconds} seconds"
        elif total_seconds < 3600:
            # Less than 1 hour
            minutes = total_seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif total_seconds < 86400:
            # Less than 1 day
            hours = total_seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            # 1 day or more
            days = time_since.days
            return f"{days} day{'s' if days != 1 else ''}"
