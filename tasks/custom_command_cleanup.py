"""
Custom Command Cleanup Task for Discord Bot v2.0

Modern automated cleanup system with better notifications and logging.
"""
import asyncio
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional

import discord
from discord.ext import commands, tasks

from services.custom_commands_service import custom_commands_service
from models.custom_command import CustomCommand
from utils.logging import get_contextual_logger
from views.embeds import EmbedTemplate, EmbedColors
from config import get_config


class CustomCommandCleanupTask:
    """Automated cleanup task for custom commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.CustomCommandCleanupTask')
        self.logger.info("Custom command cleanup task initialized")
        
        # Start the cleanup task
        self.cleanup_task.start()
    
    def cog_unload(self):
        """Stop the task when cog is unloaded."""
        self.cleanup_task.cancel()
    
    @tasks.loop(hours=24)  # Run once per day
    async def cleanup_task(self):
        """Main cleanup task that runs daily."""
        try:
            self.logger.info("Starting custom command cleanup task")
            
            config = get_config()
            
            # Only run on the configured guild
            if not config.guild_id:
                self.logger.info("No guild ID configured, skipping cleanup")
                return
            
            guild = self.bot.get_guild(config.guild_id)
            if not guild:
                self.logger.warning("Could not find configured guild, skipping cleanup")
                return
            
            # Run cleanup operations
            warning_count = await self._send_warnings(guild)
            deletion_count = await self._delete_old_commands(guild)
            
            # Log summary
            self.logger.info(
                "Custom command cleanup completed",
                warnings_sent=warning_count,
                commands_deleted=deletion_count
            )
            
            # Optionally send admin summary (if admin channel is configured)
            await self._send_admin_summary(guild, warning_count, deletion_count)
            
        except Exception as e:
            self.logger.error("Error in custom command cleanup task", error=e)
    
    @cleanup_task.before_loop
    async def before_cleanup(self):
        """Wait for bot to be ready before starting cleanup."""
        await self.bot.wait_until_ready()
        self.logger.info("Bot is ready, custom command cleanup task starting")
    
    async def _send_warnings(self, guild: discord.Guild) -> int:
        """
        Send warnings to users whose commands will be deleted soon.
        
        Returns:
            Number of users who received warnings
        """
        try:
            # Get commands needing warnings
            commands_needing_warning = await custom_commands_service.get_commands_needing_warning()
            
            if not commands_needing_warning:
                self.logger.debug("No commands needing warnings")
                return 0
            
            # Group commands by creator
            warnings_by_creator: Dict[int, List[CustomCommand]] = {}
            for command in commands_needing_warning:
                creator_id = command.creator.discord_id
                if creator_id not in warnings_by_creator:
                    warnings_by_creator[creator_id] = []
                warnings_by_creator[creator_id].append(command)
            
            # Send warnings to each creator
            warnings_sent = 0
            for creator_discord_id, commands in warnings_by_creator.items():
                try:
                    member = guild.get_member(creator_discord_id)
                    if not member:
                        self.logger.warning(
                            "Could not find member for warning",
                            discord_id=creator_discord_id
                        )
                        continue
                    
                    # Create warning embed
                    embed = await self._create_warning_embed(commands)
                    
                    # Send DM
                    try:
                        await member.send(embed=embed)
                        warnings_sent += 1
                        
                        # Mark warnings as sent
                        for command in commands:
                            await custom_commands_service.mark_warning_sent(command.name)
                        
                        self.logger.info(
                            "Warning sent to user",
                            discord_id=creator_discord_id,
                            command_count=len(commands)
                        )
                        
                    except discord.Forbidden:
                        self.logger.warning(
                            "Could not send DM to user (DMs disabled)",
                            discord_id=creator_discord_id
                        )
                    except discord.HTTPException as e:
                        self.logger.error(
                            "Failed to send warning DM",
                            discord_id=creator_discord_id,
                            error=e
                        )
                
                except Exception as e:
                    self.logger.error(
                        "Error processing warning for creator",
                        discord_id=creator_discord_id,
                        error=e
                    )
                
                # Add small delay between DMs to avoid rate limits
                await asyncio.sleep(1)
            
            return warnings_sent
            
        except Exception as e:
            self.logger.error("Error in _send_warnings", error=e)
            return 0
    
    async def _delete_old_commands(self, guild: discord.Guild) -> int:
        """
        Delete commands that are eligible for deletion.
        
        Returns:
            Number of commands deleted
        """
        try:
            # Get commands eligible for deletion
            commands_to_delete = await custom_commands_service.get_commands_eligible_for_deletion()
            
            if not commands_to_delete:
                self.logger.debug("No commands eligible for deletion")
                return 0
            
            # Group commands by creator for notifications
            deletions_by_creator: Dict[int, List[CustomCommand]] = {}
            for command in commands_to_delete:
                creator_id = command.creator.discord_id
                if creator_id not in deletions_by_creator:
                    deletions_by_creator[creator_id] = []
                deletions_by_creator[creator_id].append(command)
            
            # Delete commands and notify creators
            total_deleted = 0
            for creator_discord_id, commands in deletions_by_creator.items():
                try:
                    # Delete the commands
                    command_names = [cmd.name for cmd in commands]
                    deleted_count = await custom_commands_service.bulk_delete_commands(command_names)
                    total_deleted += deleted_count
                    
                    if deleted_count > 0:
                        # Notify the creator
                        member = guild.get_member(creator_discord_id)
                        if member:
                            embed = await self._create_deletion_embed(commands[:deleted_count])
                            
                            try:
                                await member.send(embed=embed)
                                self.logger.info(
                                    "Deletion notification sent to user",
                                    discord_id=creator_discord_id,
                                    commands_deleted=deleted_count
                                )
                            except (discord.Forbidden, discord.HTTPException) as e:
                                self.logger.warning(
                                    "Could not send deletion notification",
                                    discord_id=creator_discord_id,
                                    error=e
                                )
                    
                    self.logger.info(
                        "Commands deleted for creator",
                        discord_id=creator_discord_id,
                        commands_deleted=deleted_count
                    )
                
                except Exception as e:
                    self.logger.error(
                        "Error deleting commands for creator",
                        discord_id=creator_discord_id,
                        error=e
                    )
                
                # Add small delay between operations
                await asyncio.sleep(0.5)
            
            return total_deleted
            
        except Exception as e:
            self.logger.error("Error in _delete_old_commands", error=e)
            return 0
    
    async def _create_warning_embed(self, commands: List[CustomCommand]) -> discord.Embed:
        """Create warning embed for commands about to be deleted."""
        plural = len(commands) > 1
        
        embed = EmbedTemplate.warning(
            title="Custom Command Cleanup Warning",
            description=f"The following custom command{'s' if plural else ''} will be deleted in 30 days if not used:"
        )
        
        # List commands
        command_list = []
        for cmd in commands[:10]:  # Limit to 10 commands in the embed
            days_unused = cmd.days_since_last_use or 0
            command_list.append(f"• **{cmd.name}** (unused for {days_unused} days)")
        
        if len(commands) > 10:
            command_list.append(f"• ... and {len(commands) - 10} more commands")
        
        embed.add_field(
            name=f"Command{'s' if plural else ''} at Risk",
            value='\n'.join(command_list),
            inline=False
        )
        
        embed.add_field(
            name="💡 How to Keep Your Commands",
            value="Simply use your commands with `/cc <command_name>` to reset the deletion timer.",
            inline=False
        )
        
        embed.add_field(
            name="📋 Manage Your Commands",
            value="Use `/cc-mine` to view and manage all your custom commands.",
            inline=False
        )
        
        embed.set_footer(text="This is an automated cleanup to keep the command list manageable")
        
        return embed
    
    async def _create_deletion_embed(self, commands: List[CustomCommand]) -> discord.Embed:
        """Create deletion notification embed."""
        plural = len(commands) > 1
        
        embed = EmbedTemplate.error(
            title="Custom Commands Deleted",
            description=f"The following custom command{'s' if plural else ''} {'have' if plural else 'has'} been automatically deleted due to inactivity:"
        )
        
        # List deleted commands
        command_list = []
        for cmd in commands[:10]:  # Limit to 10 commands in the embed
            days_unused = cmd.days_since_last_use or 0
            use_count = cmd.use_count
            command_list.append(f"• **{cmd.name}** ({use_count} uses, unused for {days_unused} days)")
        
        if len(commands) > 10:
            command_list.append(f"• ... and {len(commands) - 10} more commands")
        
        embed.add_field(
            name=f"Deleted Command{'s' if plural else ''}",
            value='\n'.join(command_list),
            inline=False
        )
        
        embed.add_field(
            name="📝 Create New Commands",
            value="You can create new custom commands anytime with `/cc-create`.",
            inline=False
        )
        
        embed.set_footer(text="Commands are deleted after 90 days of inactivity to keep the system manageable")
        
        return embed
    
    async def _send_admin_summary(
        self, 
        guild: discord.Guild, 
        warnings_sent: int, 
        commands_deleted: int
    ) -> None:
        """
        Send cleanup summary to admin channel (if configured).
        
        Args:
            guild: The guild where cleanup occurred
            warnings_sent: Number of warning messages sent
            commands_deleted: Number of commands deleted
        """
        try:
            # Only send summary if there was activity
            if warnings_sent == 0 and commands_deleted == 0:
                return
            
            # Look for common admin channel names
            admin_channel_names = ['admin', 'bot-logs', 'mod-logs', 'logs']
            admin_channel = None
            
            for channel_name in admin_channel_names:
                admin_channel = discord.utils.get(guild.text_channels, name=channel_name)
                if admin_channel:
                    break
            
            if not admin_channel:
                self.logger.debug("No admin channel found for cleanup summary")
                return
            
            # Check if bot has permission to send messages
            if not admin_channel.permissions_for(guild.me).send_messages:
                self.logger.warning("No permission to send to admin channel")
                return
            
            # Create summary embed
            embed = EmbedTemplate.info(
                title="🧹 Custom Command Cleanup Summary",
                description="Daily cleanup task completed"
            )
            
            if warnings_sent > 0:
                embed.add_field(
                    name="⚠️ Warnings Sent",
                    value=f"{warnings_sent} user{'s' if warnings_sent != 1 else ''} notified about commands at risk",
                    inline=True
                )
            
            if commands_deleted > 0:
                embed.add_field(
                    name="🗑️ Commands Deleted",
                    value=f"{commands_deleted} inactive command{'s' if commands_deleted != 1 else ''} removed",
                    inline=True
                )
            
            # Get current statistics
            stats = await custom_commands_service.get_statistics()
            embed.add_field(
                name="📊 Current Stats",
                value=f"**Active Commands:** {stats.active_commands}\n**Total Creators:** {stats.total_creators}",
                inline=True
            )
            
            embed.set_footer(text=f"Next cleanup: {datetime.now(UTC) + timedelta(days=1):%Y-%m-%d}")
            
            await admin_channel.send(embed=embed)
            
            self.logger.info("Admin cleanup summary sent", channel=admin_channel.name)
            
        except Exception as e:
            self.logger.error("Error sending admin summary", error=e)


def setup_cleanup_task(bot: commands.Bot) -> CustomCommandCleanupTask:
    """Set up the custom command cleanup task."""
    return CustomCommandCleanupTask(bot)