"""
Spoiler Message Listener

Monitors all messages for Discord spoiler tags and responds with "Deez Watch!".
Discord spoilers use || markers, so we detect messages with two or more instances.
"""
import logging
import random
import discord
from discord.ext import commands

from utils.listeners import should_process_message, COMMAND_FILTERS

logger = logging.getLogger(f'{__name__}.SpoilerListener')


class SpoilerListener(commands.Cog):
    """Listens for spoiler tags and responds with Deez Watch!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("SpoilerListener cog initialized")

    @commands.Cog.listener(name='on_message')
    async def on_message_listener(self, message: discord.Message):
        """
        Listen for messages containing Discord spoiler tags (||).

        Args:
            message: Discord message object
        """
        # Apply common message filters
        if not should_process_message(message, *COMMAND_FILTERS):
            return

        # Check if message contains two or more instances of "||" (spoiler syntax)
        spoiler_count = message.content.count("||")
        if spoiler_count < 2:
            return

        logger.info(
            f"Spoiler detected in message from {message.author.name} "
            f"(ID: {message.author.id}) with {spoiler_count // 2} spoiler tag(s)"
        )

        split_text = message.content.split('||')
        spoiler_text = split_text[1]
        if len(split_text) > 3 and 'z' not in spoiler_text:
            chance = 'Low'
        elif 8 <= len(spoiler_text) <= 10:
            chance = 'High'
        elif 'z' in spoiler_text:
            chance = 'Medium'
        else:
            d1000 = random.randint(1, 1000)
            if d1000 <= 300:
                chance = 'Low'
            elif d1000 <= 600:
                chance = 'Medium'
            elif d1000 <= 900:
                chance = 'High'
            elif d1000 <= 950:
                chance = 'Miniscule'
            elif d1000 <= 980:
                chance = 'Throbbing'
            else:
                chance = 'Deez Nuts'

        try:
            # Find the "Deez Watch" role in the guild
            deez_watch_role = None
            if message.guild:
                deez_watch_role = discord.utils.get(message.guild.roles, name="Deez Watch")

            # Post response to channel with role ping if available
            if deez_watch_role:
                await message.channel.send(f"{deez_watch_role.mention} there is a **{chance}** chance this is a deez nuts joke!")
                logger.debug("Spoiler alert posted with role mention")
            else:
                # Fallback if role doesn't exist
                await message.channel.send("Deez Watch!")
                logger.warning("Deez Watch role not found, posted without mention")

        except discord.Forbidden:
            logger.error(
                f"Missing permissions to send message in channel {message.channel.id}"
            )
        except Exception as e:
            logger.error(f"Error sending spoiler response: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    """Load the spoiler listener cog."""
    await bot.add_cog(SpoilerListener(bot))
