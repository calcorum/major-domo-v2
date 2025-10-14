"""
Soak Info Commands

Provides information about soak mentions without triggering the easter egg.
"""
import discord
from discord import app_commands
from discord.ext import commands

from utils.decorators import logged_command
from utils.logging import get_contextual_logger
from views.embeds import EmbedTemplate, EmbedColors
from .tracker import SoakTracker
from .giphy_service import get_tier_for_seconds, get_tier_description


class SoakInfoCommands(commands.Cog):
    """Soak information command handlers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.SoakInfoCommands')
        self.tracker = SoakTracker()
        self.logger.info("SoakInfoCommands cog initialized")

    @app_commands.command(name="lastsoak", description="Get information about the last soak mention")
    @logged_command("/lastsoak")
    async def last_soak(self, interaction: discord.Interaction):
        """Show information about the last soak mention."""
        await interaction.response.defer(ephemeral=True)

        last_soak = self.tracker.get_last_soak()

        # Handle case where soak has never been mentioned
        if not last_soak:
            embed = EmbedTemplate.info(
                title="Last Soak",
                description="No one has said the forbidden word yet. 🤫"
            )
            embed.add_field(
                name="Total Mentions",
                value="0",
                inline=False
            )
            await interaction.followup.send(embed=embed)
            return

        # Calculate time since last soak
        time_since = self.tracker.get_time_since_last_soak()
        total_count = self.tracker.get_soak_count()

        # Determine disappointment tier
        tier_key = get_tier_for_seconds(int(time_since.total_seconds()) if time_since else None)
        tier_description = get_tier_description(tier_key)

        # Create embed
        embed = EmbedTemplate.create_base_embed(
            title="📊 Last Soak",
            description="Information about the most recent soak mention",
            color=EmbedColors.INFO
        )

        # Parse timestamp for Discord formatting
        try:
            from datetime import datetime
            timestamp_str = last_soak["timestamp"]
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            unix_timestamp = int(timestamp.timestamp())

            # Add relative time with warning if very recent
            time_field_value = f"<t:{unix_timestamp}:R>"
            if time_since and time_since.total_seconds() < 1800:  # Less than 30 minutes
                time_field_value += "\n\n😤 Way too soon!"

            embed.add_field(
                name="Last Mentioned",
                value=time_field_value,
                inline=False
            )
        except Exception as e:
            self.logger.error(f"Error parsing timestamp: {e}")
            embed.add_field(
                name="Last Mentioned",
                value="Error parsing timestamp",
                inline=False
            )

        # Add user info
        user_mention = f"<@{last_soak['user_id']}>"
        display_name = last_soak.get('display_name', last_soak.get('username', 'Unknown'))
        embed.add_field(
            name="By",
            value=f"{user_mention} ({display_name})",
            inline=True
        )

        # Add message link
        try:
            guild_id = interaction.guild_id
            channel_id = last_soak['channel_id']
            message_id = last_soak['message_id']
            jump_url = f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
            embed.add_field(
                name="Message",
                value=f"[Jump to message]({jump_url})",
                inline=True
            )
        except Exception as e:
            self.logger.error(f"Error creating jump URL: {e}")

        # Add total count
        embed.add_field(
            name="Total Mentions",
            value=str(total_count),
            inline=True
        )

        # Add disappointment level
        embed.add_field(
            name="Disappointment Level",
            value=f"{tier_key.replace('_', ' ').title()}: {tier_description}",
            inline=False
        )

        await interaction.followup.send(embed=embed)
