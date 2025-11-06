"""
Admin User Management Commands

User-focused administrative commands for moderation and user management.
"""
from typing import Optional, Union
import asyncio
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord import app_commands

from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.permissions import league_admin_only
from views.embeds import EmbedColors, EmbedTemplate


class UserManagementCommands(commands.Cog):
    """User management command handlers for moderation."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.UserManagementCommands')
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need administrator permissions to use admin commands.",
                ephemeral=True
            )
            return False
        return True
    
    @app_commands.command(
        name="admin-timeout",
        description="Timeout a user for a specified duration"
    )
    @app_commands.describe(
        user="User to timeout",
        duration="Duration in minutes (1-10080, max 7 days)",
        reason="Reason for the timeout"
    )
    @league_admin_only()
    @logged_command("/admin-timeout")
    async def admin_timeout(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        duration: int,
        reason: Optional[str] = "No reason provided"
    ):
        """Timeout a user for a specified duration."""
        if duration < 1 or duration > 10080:  # Max 7 days in minutes
            await interaction.response.send_message(
                "❌ Duration must be between 1 minute and 7 days (10080 minutes).",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Calculate timeout end time
            timeout_until = discord.utils.utcnow() + timedelta(minutes=duration)
            
            # Apply timeout
            await user.timeout(timeout_until, reason=f"By {interaction.user}: {reason}")
            
            embed = EmbedTemplate.create_base_embed(
                title="⏰ User Timed Out",
                description=f"{user.mention} has been timed out",
                color=EmbedColors.WARNING
            )
            
            embed.add_field(
                name="Timeout Details",
                value=f"**User:** {user.display_name} ({user.mention})\n"
                      f"**Duration:** {duration} minutes\n"
                      f"**Until:** {discord.utils.format_dt(timeout_until, 'F')}\n"
                      f"**Reason:** {reason}",
                inline=False
            )
            
            embed.add_field(
                name="Action Details",
                value=f"**Moderator:** {interaction.user.mention}\n"
                      f"**Time:** {discord.utils.utcnow().strftime('%H:%M:%S UTC')}",
                inline=False
            )
            
            embed.set_thumbnail(url=user.display_avatar.url)
            
            await interaction.followup.send(embed=embed)
            
            # Log the action
            self.logger.info(
                f"User {user} timed out by {interaction.user} for {duration} minutes. Reason: {reason}"
            )
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permissions to timeout this user.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Failed to timeout user: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="admin-untimeout",
        description="Remove timeout from a user"
    )
    @app_commands.describe(
        user="User to remove timeout from",
        reason="Reason for removing the timeout"
    )
    @league_admin_only()
    @logged_command("/admin-untimeout")
    async def admin_untimeout(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: Optional[str] = "Timeout removed by admin"
    ):
        """Remove timeout from a user."""
        await interaction.response.defer()
        
        if not user.is_timed_out():
            await interaction.followup.send(
                f"❌ {user.display_name} is not currently timed out.",
                ephemeral=True
            )
            return
        
        try:
            await user.timeout(None, reason=f"By {interaction.user}: {reason}")
            
            embed = EmbedTemplate.create_base_embed(
                title="✅ Timeout Removed",
                description=f"Timeout removed for {user.mention}",
                color=EmbedColors.SUCCESS
            )
            
            embed.add_field(
                name="Action Details",
                value=f"**User:** {user.display_name} ({user.mention})\n"
                      f"**Reason:** {reason}\n"
                      f"**Moderator:** {interaction.user.mention}\n"
                      f"**Time:** {discord.utils.utcnow().strftime('%H:%M:%S UTC')}",
                inline=False
            )
            
            embed.set_thumbnail(url=user.display_avatar.url)
            
            await interaction.followup.send(embed=embed)
            
            self.logger.info(
                f"Timeout removed from {user} by {interaction.user}. Reason: {reason}"
            )
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permissions to remove timeout from this user.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Failed to remove timeout: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="admin-kick",
        description="Kick a user from the server"
    )
    @app_commands.describe(
        user="User to kick",
        reason="Reason for the kick"
    )
    @league_admin_only()
    @logged_command("/admin-kick")
    async def admin_kick(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: Optional[str] = "No reason provided"
    ):
        """Kick a user from the server."""
        await interaction.response.defer()
        
        # Safety check - don't kick yourself or other admins
        if user == interaction.user:
            await interaction.followup.send(
                "❌ You cannot kick yourself.",
                ephemeral=True
            )
            return
        
        if user.guild_permissions.administrator:
            await interaction.followup.send(
                "❌ Cannot kick administrators.",
                ephemeral=True
            )
            return
        
        try:
            # Store user info before kicking
            user_name = user.display_name
            user_id = user.id
            user_avatar = user.display_avatar.url
            
            await user.kick(reason=f"By {interaction.user}: {reason}")
            
            embed = EmbedTemplate.create_base_embed(
                title="👋 User Kicked",
                description=f"{user_name} has been kicked from the server",
                color=EmbedColors.WARNING
            )
            
            embed.add_field(
                name="Kick Details",
                value=f"**User:** {user_name} (ID: {user_id})\n"
                      f"**Reason:** {reason}\n"
                      f"**Moderator:** {interaction.user.mention}\n"
                      f"**Time:** {discord.utils.utcnow().strftime('%H:%M:%S UTC')}",
                inline=False
            )
            
            embed.set_thumbnail(url=user_avatar)
            
            await interaction.followup.send(embed=embed)
            
            self.logger.warning(
                f"User {user_name} (ID: {user_id}) kicked by {interaction.user}. Reason: {reason}"
            )
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permissions to kick this user.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Failed to kick user: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="admin-ban",
        description="Ban a user from the server"
    )
    @app_commands.describe(
        user="User to ban",
        reason="Reason for the ban",
        delete_messages="Whether to delete user's messages (default: False)"
    )
    @league_admin_only()
    @logged_command("/admin-ban")
    async def admin_ban(
        self,
        interaction: discord.Interaction,
        user: Union[discord.Member, discord.User],
        reason: Optional[str] = "No reason provided",
        delete_messages: bool = False
    ):
        """Ban a user from the server."""
        await interaction.response.defer()
        
        # Safety checks
        if isinstance(user, discord.Member):
            if user == interaction.user:
                await interaction.followup.send(
                    "❌ You cannot ban yourself.",
                    ephemeral=True
                )
                return
            
            if user.guild_permissions.administrator:
                await interaction.followup.send(
                    "❌ Cannot ban administrators.",
                    ephemeral=True
                )
                return
        
        try:
            # Store user info before banning
            user_name = user.display_name if hasattr(user, 'display_name') else user.name
            user_id = user.id
            user_avatar = user.display_avatar.url
            
            # Delete messages from last day if requested
            delete_days = 1 if delete_messages else 0
            
            await interaction.guild.ban(
                user, 
                reason=f"By {interaction.user}: {reason}",
                delete_message_days=delete_days
            )
            
            embed = EmbedTemplate.create_base_embed(
                title="🔨 User Banned",
                description=f"{user_name} has been banned from the server",
                color=EmbedColors.ERROR
            )
            
            embed.add_field(
                name="Ban Details",
                value=f"**User:** {user_name} (ID: {user_id})\n"
                      f"**Reason:** {reason}\n"
                      f"**Messages Deleted:** {'Yes (1 day)' if delete_messages else 'No'}\n"
                      f"**Moderator:** {interaction.user.mention}\n"
                      f"**Time:** {discord.utils.utcnow().strftime('%H:%M:%S UTC')}",
                inline=False
            )
            
            embed.set_thumbnail(url=user_avatar)
            
            await interaction.followup.send(embed=embed)
            
            self.logger.warning(
                f"User {user_name} (ID: {user_id}) banned by {interaction.user}. Reason: {reason}"
            )
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permissions to ban this user.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Failed to ban user: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="admin-unban",
        description="Unban a user from the server"
    )
    @app_commands.describe(
        user_id="User ID to unban",
        reason="Reason for the unban"
    )
    @league_admin_only()
    @logged_command("/admin-unban")
    async def admin_unban(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: Optional[str] = "Ban lifted by admin"
    ):
        """Unban a user from the server."""
        await interaction.response.defer()
        
        try:
            # Convert user_id to int
            user_id_int = int(user_id)
        except ValueError:
            await interaction.followup.send(
                "❌ Invalid user ID format.",
                ephemeral=True
            )
            return
        
        try:
            # Get the user object
            user = await self.bot.fetch_user(user_id_int)
            
            # Check if user is actually banned
            try:
                ban_entry = await interaction.guild.fetch_ban(user)
                ban_reason = ban_entry.reason or "No reason recorded"
            except discord.NotFound:
                await interaction.followup.send(
                    f"❌ User {user.name} is not banned.",
                    ephemeral=True
                )
                return
            
            # Unban the user
            await interaction.guild.unban(user, reason=f"By {interaction.user}: {reason}")
            
            embed = EmbedTemplate.create_base_embed(
                title="✅ User Unbanned",
                description=f"{user.name} has been unbanned",
                color=EmbedColors.SUCCESS
            )
            
            embed.add_field(
                name="Unban Details",
                value=f"**User:** {user.name} (ID: {user_id})\n"
                      f"**Original Ban:** {ban_reason}\n"
                      f"**Unban Reason:** {reason}\n"
                      f"**Moderator:** {interaction.user.mention}\n"
                      f"**Time:** {discord.utils.utcnow().strftime('%H:%M:%S UTC')}",
                inline=False
            )
            
            embed.set_thumbnail(url=user.display_avatar.url)
            
            await interaction.followup.send(embed=embed)
            
            self.logger.info(
                f"User {user.name} (ID: {user_id}) unbanned by {interaction.user}. Reason: {reason}"
            )
            
        except discord.NotFound:
            await interaction.followup.send(
                f"❌ Could not find user with ID {user_id}.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permissions to unban users.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Failed to unban user: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="admin-userinfo",
        description="Display detailed information about a user"
    )
    @app_commands.describe(
        user="User to get information about"
    )
    @league_admin_only()
    @logged_command("/admin-userinfo")
    async def admin_userinfo(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        """Display comprehensive user information."""
        await interaction.response.defer()
        
        embed = EmbedTemplate.create_base_embed(
            title=f"👤 User Information - {user.display_name}",
            color=EmbedColors.INFO
        )
        
        # Basic user info
        embed.add_field(
            name="Basic Information",
            value=f"**Username:** {user.name}\n"
                  f"**Display Name:** {user.display_name}\n"
                  f"**User ID:** {user.id}\n"
                  f"**Bot:** {'Yes' if user.bot else 'No'}",
            inline=True
        )
        
        # Account dates
        created_at = discord.utils.format_dt(user.created_at, 'F')
        joined_at = discord.utils.format_dt(user.joined_at, 'F') if user.joined_at else 'Unknown'
        
        embed.add_field(
            name="Account Dates",
            value=f"**Account Created:** {created_at}\n"
                  f"**Joined Server:** {joined_at}",
            inline=True
        )
        
        # Status and activity
        status_emoji = {
            discord.Status.online: "🟢",
            discord.Status.idle: "🟡", 
            discord.Status.dnd: "🔴",
            discord.Status.offline: "⚫"
        }.get(user.status, "❓")
        
        activity_text = "None"
        if user.activity:
            if user.activity.type == discord.ActivityType.playing:
                activity_text = f"Playing {user.activity.name}"
            elif user.activity.type == discord.ActivityType.listening:
                activity_text = f"Listening to {user.activity.name}"
            elif user.activity.type == discord.ActivityType.watching:
                activity_text = f"Watching {user.activity.name}"
            else:
                activity_text = str(user.activity)
        
        embed.add_field(
            name="Status & Activity",
            value=f"**Status:** {status_emoji} {user.status.name.title()}\n"
                  f"**Activity:** {activity_text}",
            inline=False
        )
        
        # Roles
        roles = [role.mention for role in user.roles[1:]]  # Skip @everyone
        roles_text = ", ".join(roles[-10:]) if roles else "No roles"
        if len(roles) > 10:
            roles_text += f"\n... and {len(roles) - 10} more"
        
        embed.add_field(
            name="Roles",
            value=roles_text,
            inline=False
        )
        
        # Permissions check
        perms = []
        if user.guild_permissions.administrator:
            perms.append("Administrator")
        if user.guild_permissions.manage_guild:
            perms.append("Manage Server")
        if user.guild_permissions.manage_channels:
            perms.append("Manage Channels")
        if user.guild_permissions.manage_messages:
            perms.append("Manage Messages")
        if user.guild_permissions.kick_members:
            perms.append("Kick Members")
        if user.guild_permissions.ban_members:
            perms.append("Ban Members")
        
        embed.add_field(
            name="Key Permissions",
            value=", ".join(perms) if perms else "None",
            inline=False
        )
        
        # Timeout status
        if user.is_timed_out():
            timeout_until = discord.utils.format_dt(user.timed_out_until, 'F')
            embed.add_field(
                name="⏰ Timeout Status",
                value=f"**Timed out until:** {timeout_until}",
                inline=False
            )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    """Load the user management commands cog."""
    await bot.add_cog(UserManagementCommands(bot))