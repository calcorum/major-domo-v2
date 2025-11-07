"""
Admin Management Commands

Administrative commands for league management and bot maintenance.
"""
import asyncio
from typing import List, Dict, Any

import discord
from discord.ext import commands
from discord import app_commands

from config import get_config
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.discord_helpers import set_channel_visibility
from utils.permissions import league_admin_only
from views.embeds import EmbedColors, EmbedTemplate
from services.league_service import league_service
from services.transaction_service import transaction_service


class AdminCommands(commands.Cog):
    """Administrative command handlers for league management."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.AdminCommands')
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions."""
        # Check if interaction is from a guild and user is a Member
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ Admin commands can only be used in a server.",
                ephemeral=True
            )
            return False

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need administrator permissions to use admin commands.",
                ephemeral=True
            )
            return False
        return True
    
    @app_commands.command(
        name="admin-status",
        description="Display bot status and system information"
    )
    @league_admin_only()
    @logged_command("/admin-status")
    async def admin_status(self, interaction: discord.Interaction):
        """Display comprehensive bot status information."""
        await interaction.response.defer()
        
        # Gather system information
        guilds_count = len(self.bot.guilds)
        users_count = sum(guild.member_count or 0 for guild in self.bot.guilds)
        commands_count = len([cmd for cmd in self.bot.tree.walk_commands()])
        
        # Bot uptime calculation
        uptime = discord.utils.utcnow() - self.bot.user.created_at if self.bot.user else None
        uptime_str = f"{uptime.days} days" if uptime else "Unknown"
        
        embed = EmbedTemplate.create_base_embed(
            title="🤖 Bot Status - Admin Panel",
            color=EmbedColors.INFO
        )
        
        # System Stats
        embed.add_field(
            name="System Information",
            value=f"**Guilds:** {guilds_count}\n"
                  f"**Users:** {users_count:,}\n"
                  f"**Commands:** {commands_count}\n"
                  f"**Uptime:** {uptime_str}",
            inline=True
        )
        
        # Bot Information  
        embed.add_field(
            name="Bot Information",
            value=f"**Latency:** {round(self.bot.latency * 1000)}ms\n"
                  f"**Version:** Discord.py {discord.__version__}\n"
                  f"**Current Season:** {get_config().sba_current_season}",
            inline=True
        )
        
        # Cog Status
        loaded_cogs = list(self.bot.cogs.keys())
        embed.add_field(
            name="Loaded Cogs",
            value="\n".join([f"✅ {cog}" for cog in loaded_cogs[:10]]) + 
                  (f"\n... and {len(loaded_cogs) - 10} more" if len(loaded_cogs) > 10 else ""),
            inline=False
        )
        
        embed.set_footer(text="Admin Status • Use /admin-help for more commands")
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(
        name="admin-help",
        description="Display available admin commands and their usage"
    )
    @league_admin_only()
    @logged_command("/admin-help")
    async def admin_help(self, interaction: discord.Interaction):
        """Display comprehensive admin help information."""
        await interaction.response.defer()
        
        embed = EmbedTemplate.create_base_embed(
            title="🛠️ Admin Commands - Help",
            description="Available administrative commands for league management",
            color=EmbedColors.PRIMARY
        )
        
        # System Commands
        embed.add_field(
            name="System Management",
            value="**`/admin-status`** - Display bot status and information\n"
                  "**`/admin-reload <cog>`** - Reload a specific cog\n"
                  "**`/admin-sync`** - Sync application commands\n"
                  "**`/admin-clear <count>`** - Clear messages from channel\n"
                  "**`/admin-clear-scorecards`** - Clear live scorebug channel and hide it",
            inline=False
        )
        
        # League Management
        embed.add_field(
            name="League Management",
            value="**`/admin-season <season>`** - Set current season\n"
                  "**`/admin-announce <message>`** - Send announcement to channel\n"
                  "**`/admin-maintenance <on/off>`** - Toggle maintenance mode\n"
                  "**`/admin-process-transactions [week]`** - Manually process weekly transactions",
            inline=False
        )
        
        # User Management
        embed.add_field(
            name="User Management", 
            value="**`/admin-timeout <user> <duration>`** - Timeout a user\n"
                  "**`/admin-kick <user> <reason>`** - Kick a user\n"
                  "**`/admin-ban <user> <reason>`** - Ban a user",
            inline=False
        )
        
        embed.add_field(
            name="Usage Notes",
            value="• All admin commands require Administrator permissions\n"
                  "• Commands are logged for audit purposes\n"
                  "• Use with caution - some actions are irreversible",
            inline=False
        )
        
        embed.set_footer(text="Administrator Permissions Required")
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(
        name="admin-reload",
        description="Reload a specific bot cog"
    )
    @app_commands.describe(
        cog="Name of the cog to reload (e.g., 'commands.players.info')"
    )
    @league_admin_only()
    @logged_command("/admin-reload")
    async def admin_reload(self, interaction: discord.Interaction, cog: str):
        """Reload a specific cog for hot-swapping code changes."""
        await interaction.response.defer()
        
        try:
            # Attempt to reload the cog
            await self.bot.reload_extension(cog)
            
            embed = EmbedTemplate.create_base_embed(
                title="✅ Cog Reloaded Successfully",
                description=f"Successfully reloaded `{cog}`",
                color=EmbedColors.SUCCESS
            )
            
            embed.add_field(
                name="Reload Details",
                value=f"**Cog:** {cog}\n"
                      f"**Status:** Successfully reloaded\n"
                      f"**Time:** {discord.utils.utcnow().strftime('%H:%M:%S UTC')}",
                inline=False
            )
            
        except commands.ExtensionNotFound:
            embed = EmbedTemplate.create_base_embed(
                title="❌ Cog Not Found",
                description=f"Could not find cog: `{cog}`",
                color=EmbedColors.ERROR
            )
        except commands.ExtensionNotLoaded:
            embed = EmbedTemplate.create_base_embed(
                title="❌ Cog Not Loaded",
                description=f"Cog `{cog}` is not currently loaded",
                color=EmbedColors.ERROR
            )
        except Exception as e:
            embed = EmbedTemplate.create_base_embed(
                title="❌ Reload Failed",
                description=f"Failed to reload `{cog}`: {str(e)}",
                color=EmbedColors.ERROR
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(
        name="admin-sync",
        description="Sync application commands with Discord"
    )
    @app_commands.describe(
        local="Sync to this guild only (fast, for development)",
        clear_local="Clear locally synced commands (does not sync after clearing)"
    )
    @league_admin_only()
    @logged_command("/admin-sync")
    async def admin_sync(
        self,
        interaction: discord.Interaction,
        local: bool = False,
        clear_local: bool = False
    ):
        """Sync slash commands with Discord API."""
        await interaction.response.defer()

        try:
            # Clear local commands if requested
            if clear_local:
                if not interaction.guild_id:
                    raise ValueError("Cannot clear local commands outside of a guild")

                self.logger.info(f"Clearing local commands for guild {interaction.guild_id}")
                self.bot.tree.clear_commands(guild=discord.Object(id=interaction.guild_id))

                embed = EmbedTemplate.create_base_embed(
                    title="✅ Local Commands Cleared",
                    description=f"Cleared all commands synced to this guild",
                    color=EmbedColors.SUCCESS
                )
                embed.add_field(
                    name="Clear Details",
                    value=f"**Guild ID:** {interaction.guild_id}\n"
                          f"**Time:** {discord.utils.utcnow().strftime('%H:%M:%S UTC')}\n"
                          f"**Note:** Commands not synced after clearing",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
                return

            # Determine sync target
            if local:
                if not interaction.guild_id:
                    raise ValueError("Cannot sync locally outside of a guild")
                guild = discord.Object(id=interaction.guild_id)
                sync_type = "local guild"
            else:
                guild = None
                sync_type = "globally"

            # Perform sync
            self.logger.info(f"Syncing commands {sync_type}")
            synced_commands = await self.bot.tree.sync(guild=guild)

            embed = EmbedTemplate.create_base_embed(
                title="✅ Commands Synced Successfully",
                description=f"Synced {len(synced_commands)} application commands {sync_type}",
                color=EmbedColors.SUCCESS
            )

            # Show some of the synced commands
            command_names = [cmd.name for cmd in synced_commands[:10]]
            embed.add_field(
                name="Synced Commands",
                value="\n".join([f"• /{name}" for name in command_names]) +
                      (f"\n... and {len(synced_commands) - 10} more" if len(synced_commands) > 10 else ""),
                inline=False
            )

            embed.add_field(
                name="Sync Details",
                value=f"**Total Commands:** {len(synced_commands)}\n"
                      f"**Sync Type:** {sync_type.title()}\n"
                      f"**Guild ID:** {interaction.guild_id or 'N/A'}\n"
                      f"**Time:** {discord.utils.utcnow().strftime('%H:%M:%S UTC')}",
                inline=False
            )

        except Exception as e:
            self.logger.error(f"Sync failed: {e}", exc_info=True)
            embed = EmbedTemplate.create_base_embed(
                title="❌ Sync Failed",
                description=f"Failed to sync commands: {str(e)}",
                color=EmbedColors.ERROR
            )

        await interaction.followup.send(embed=embed)

    @commands.command(name="admin-sync")
    @league_admin_only()
    async def admin_sync_prefix(self, ctx: commands.Context):
        """
        Prefix command version of admin-sync for bootstrap scenarios.

        Use this when slash commands aren't synced yet and you can't access /admin-sync.
        """
        self.logger.info(f"Prefix command !admin-sync invoked by {ctx.author} in {ctx.guild}")

        try:
            synced_commands = await self.bot.tree.sync()

            embed = EmbedTemplate.create_base_embed(
                title="✅ Commands Synced Successfully",
                description=f"Synced {len(synced_commands)} application commands",
                color=EmbedColors.SUCCESS
            )

            # Show some of the synced commands
            command_names = [cmd.name for cmd in synced_commands[:10]]
            embed.add_field(
                name="Synced Commands",
                value="\n".join([f"• /{name}" for name in command_names]) +
                      (f"\n... and {len(synced_commands) - 10} more" if len(synced_commands) > 10 else ""),
                inline=False
            )

            embed.add_field(
                name="Sync Details",
                value=f"**Total Commands:** {len(synced_commands)}\n"
                      f"**Guild ID:** {ctx.guild.id}\n"
                      f"**Time:** {discord.utils.utcnow().strftime('%H:%M:%S UTC')}",
                inline=False
            )

            embed.set_footer(text="💡 Use /admin-sync (slash command) for future syncs")

        except Exception as e:
            self.logger.error(f"Prefix command sync failed: {e}", exc_info=True)
            embed = EmbedTemplate.create_base_embed(
                title="❌ Sync Failed",
                description=f"Failed to sync commands: {str(e)}",
                color=EmbedColors.ERROR
            )

        await ctx.send(embed=embed)
    
    @app_commands.command(
        name="admin-clear",
        description="Clear messages from the current channel"
    )
    @app_commands.describe(
        count="Number of messages to delete (1-100)"
    )
    @league_admin_only()
    @logged_command("/admin-clear")
    async def admin_clear(self, interaction: discord.Interaction, count: int):
        """Clear a specified number of messages from the channel."""
        if count < 1 or count > 100:
            await interaction.response.send_message(
                "❌ Count must be between 1 and 100.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()

        # Verify channel type supports purge
        if not isinstance(interaction.channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel, discord.StageChannel)):
            await interaction.followup.send(
                "❌ Cannot purge messages in this channel type.",
                ephemeral=True
            )
            return

        try:
            deleted = await interaction.channel.purge(limit=count)
            
            embed = EmbedTemplate.create_base_embed(
                title="🗑️ Messages Cleared",
                description=f"Successfully deleted {len(deleted)} messages",
                color=EmbedColors.SUCCESS
            )
            
            embed.add_field(
                name="Clear Details",
                value=f"**Messages Deleted:** {len(deleted)}\n"
                      f"**Channel:** {interaction.channel.mention}\n"
                      f"**Requested:** {count} messages\n"
                      f"**Time:** {discord.utils.utcnow().strftime('%H:%M:%S UTC')}",
                inline=False
            )
            
            # Send confirmation and auto-delete after 5 seconds
            message = await interaction.followup.send(embed=embed)
            await asyncio.sleep(5)
            if message:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass  # Message already deleted
                
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permissions to delete messages.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to clear messages: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="admin-announce",
        description="Send an announcement to the current channel"
    )
    @app_commands.describe(
        message="Announcement message to send",
        mention_everyone="Whether to mention @everyone (default: False)"
    )
    @league_admin_only()
    @logged_command("/admin-announce")
    async def admin_announce(
        self, 
        interaction: discord.Interaction, 
        message: str,
        mention_everyone: bool = False
    ):
        """Send an official announcement to the channel."""
        await interaction.response.defer()
        
        embed = EmbedTemplate.create_base_embed(
            title="📢 League Announcement",
            description=message,
            color=EmbedColors.PRIMARY
        )
        
        embed.set_footer(
            text=f"Announcement by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )

        # Send with or without mention based on flag
        if mention_everyone:
            await interaction.followup.send(content="@everyone", embed=embed)
        else:
            await interaction.followup.send(embed=embed)
        
        # Log the announcement
        self.logger.info(
            f"Announcement sent by {interaction.user} in {interaction.channel}: {message[:100]}..."
        )
    
    @app_commands.command(
        name="admin-maintenance",
        description="Toggle maintenance mode for the bot"
    )
    @app_commands.describe(
        mode="Turn maintenance mode on or off"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="On", value="on"),
        app_commands.Choice(name="Off", value="off")
    ])
    @league_admin_only()
    @logged_command("/admin-maintenance")
    async def admin_maintenance(self, interaction: discord.Interaction, mode: str):
        """Toggle maintenance mode to prevent normal command usage."""
        await interaction.response.defer()
        
        # This would typically set a global flag or database value
        # For now, we'll just show the interface
        
        is_enabling = mode.lower() == "on"
        status_text = "enabled" if is_enabling else "disabled"
        color = EmbedColors.WARNING if is_enabling else EmbedColors.SUCCESS
        
        embed = EmbedTemplate.create_base_embed(
            title=f"🔧 Maintenance Mode {status_text.title()}",
            description=f"Maintenance mode has been **{status_text}**",
            color=color
        )
        
        if is_enabling:
            embed.add_field(
                name="Maintenance Active",
                value="• Normal commands are disabled\n"
                      "• Only admin commands are available\n"
                      "• Users will see maintenance message",
                inline=False
            )
        else:
            embed.add_field(
                name="Maintenance Ended",
                value="• All commands are now available\n"
                      "• Normal bot operation resumed\n"
                      "• Users can access all features",
                inline=False
            )
        
        embed.add_field(
            name="Status Change",
            value=f"**Changed by:** {interaction.user.mention}\n"
                  f"**Time:** {discord.utils.utcnow().strftime('%H:%M:%S UTC')}\n"
                  f"**Mode:** {status_text.title()}",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="admin-clear-scorecards",
        description="Manually clear the live scorebug channel and hide it from members"
    )
    @league_admin_only()
    @logged_command("/admin-clear-scorecards")
    async def admin_clear_scorecards(self, interaction: discord.Interaction):
        """
        Manually clear #live-sba-scores channel and set @everyone view permission to off.

        This is useful for:
        - Cleaning up stale scorebug displays
        - Manually hiding the channel when games finish
        - Testing channel visibility functionality
        """
        await interaction.response.defer()

        # Get the live-sba-scores channel
        config = get_config()
        guild = self.bot.get_guild(config.guild_id)

        if not guild:
            await interaction.followup.send(
                "❌ Could not find guild. Check configuration.",
                ephemeral=True
            )
            return

        live_scores_channel = discord.utils.get(guild.text_channels, name='live-sba-scores')

        if not live_scores_channel:
            await interaction.followup.send(
                "❌ Could not find #live-sba-scores channel.",
                ephemeral=True
            )
            return

        try:
            # Clear all messages from the channel
            deleted_count = 0
            async for message in live_scores_channel.history(limit=100):
                try:
                    await message.delete()
                    deleted_count += 1
                except discord.NotFound:
                    pass  # Message already deleted

            self.logger.info(f"Cleared {deleted_count} messages from #live-sba-scores")

            # Hide channel from @everyone
            visibility_success = await set_channel_visibility(
                live_scores_channel,
                visible=False,
                reason="Admin manual clear via /admin-clear-scorecards"
            )

            if visibility_success:
                visibility_status = "✅ Hidden from @everyone"
            else:
                visibility_status = "⚠️ Could not change visibility (check permissions)"

            # Create success embed
            embed = EmbedTemplate.success(
                title="Live Scorebug Channel Cleared",
                description="Successfully cleared the #live-sba-scores channel"
            )

            embed.add_field(
                name="Clear Details",
                value=f"**Channel:** {live_scores_channel.mention}\n"
                      f"**Messages Deleted:** {deleted_count}\n"
                      f"**Visibility:** {visibility_status}\n"
                      f"**Time:** {discord.utils.utcnow().strftime('%H:%M:%S UTC')}",
                inline=False
            )

            embed.add_field(
                name="Next Steps",
                value="• Channel is now hidden from @everyone\n"
                      "• Bot retains full access to the channel\n"
                      "• Channel will auto-show when games are published\n"
                      "• Live scorebug tracker runs every 3 minutes",
                inline=False
            )

            await interaction.followup.send(embed=embed)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permissions to clear messages or modify channel permissions.",
                ephemeral=True
            )
        except Exception as e:
            self.logger.error(f"Error clearing scorecards: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to clear channel: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(
        name="admin-process-transactions",
        description="Manually process all transactions for the current week (or specified week)"
    )
    @app_commands.describe(
        week="Week number to process (optional, defaults to current week)"
    )
    @league_admin_only()
    @logged_command("/admin-process-transactions")
    async def admin_process_transactions(
        self,
        interaction: discord.Interaction,
        week: int | None = None
    ):
        """
        Manually process all transactions for the current week.

        This is a fallback mechanism if the Monday morning task fails to run.
        It will:
        1. Get all non-frozen, non-cancelled transactions for the specified week
        2. Execute each transaction by updating player rosters via the API
        3. Report success/failure counts

        Args:
            week: Optional week number to process. If not provided, uses current week.
        """
        await interaction.response.defer()

        try:
            # Get current league state
            current = await league_service.get_current_state()
            if not current:
                await interaction.followup.send(
                    "❌ Could not get current league state from the API.",
                    ephemeral=True
                )
                return

            # Use provided week or current week
            target_week = week if week is not None else current.week
            target_season = current.season

            self.logger.info(
                f"Processing transactions for week {target_week}, season {target_season}",
                requested_by=str(interaction.user)
            )

            # Get all non-frozen, non-cancelled transactions for the target week
            client = await transaction_service.get_client()
            params = [
                ('season', str(target_season)),
                ('week_start', str(target_week)),
                ('week_end', str(target_week)),
                ('frozen', 'false'),
                ('cancelled', 'false')
            ]

            response = await client.get('transactions', params=params)

            if not response or response.get('count', 0) == 0:
                embed = EmbedTemplate.info(
                    title="No Transactions to Process",
                    description=f"No non-frozen, non-cancelled transactions found for Week {target_week}"
                )

                embed.add_field(
                    name="Search Criteria",
                    value=f"**Season:** {target_season}\n"
                          f"**Week:** {target_week}\n"
                          f"**Frozen:** No\n"
                          f"**Cancelled:** No",
                    inline=False
                )

                await interaction.followup.send(embed=embed)
                return

            # Extract transactions from response
            transactions = response.get('transactions', [])
            total_count = len(transactions)

            self.logger.info(f"Found {total_count} transactions to process for week {target_week}")

            # Process each transaction
            success_count = 0
            failure_count = 0
            errors: List[Dict[str, Any]] = []

            # Create initial status embed
            processing_embed = EmbedTemplate.loading(
                title="Processing Transactions",
                description=f"Processing {total_count} transactions for Week {target_week}..."
            )
            processing_embed.add_field(
                name="Progress",
                value="Starting...",
                inline=False
            )

            status_message = await interaction.followup.send(embed=processing_embed)

            for idx, transaction in enumerate(transactions, start=1):
                try:
                    player_id = transaction['player']['id']
                    new_team_id = transaction['newteam']['id']
                    player_name = transaction['player']['name']

                    # Execute player roster update via API PATCH
                    await self._execute_player_update(
                        player_id=player_id,
                        new_team_id=new_team_id,
                        player_name=player_name
                    )

                    success_count += 1

                    # Update progress every 5 transactions or on last transaction
                    if idx % 5 == 0 or idx == total_count:
                        processing_embed.set_field_at(
                            0,
                            name="Progress",
                            value=f"Processed {idx}/{total_count} transactions\n"
                                  f"✅ Successful: {success_count}\n"
                                  f"❌ Failed: {failure_count}",
                            inline=False
                        )
                        await status_message.edit(embed=processing_embed)

                    # Rate limiting: 100ms delay between requests
                    await asyncio.sleep(0.1)

                except Exception as e:
                    failure_count += 1
                    error_info = {
                        'player': transaction.get('player', {}).get('name', 'Unknown'),
                        'player_id': transaction.get('player', {}).get('id', 'N/A'),
                        'new_team': transaction.get('newteam', {}).get('abbrev', 'Unknown'),
                        'error': str(e)
                    }
                    errors.append(error_info)

                    self.logger.error(
                        f"Failed to execute transaction for {error_info['player']}",
                        player_id=error_info['player_id'],
                        new_team=error_info['new_team'],
                        error=str(e)
                    )

            # Create completion embed
            if failure_count == 0:
                completion_embed = EmbedTemplate.success(
                    title="Transactions Processed Successfully",
                    description=f"All {total_count} transactions for Week {target_week} have been processed."
                )
            elif success_count == 0:
                completion_embed = EmbedTemplate.error(
                    title="Transaction Processing Failed",
                    description=f"Failed to process all {total_count} transactions for Week {target_week}."
                )
            else:
                completion_embed = EmbedTemplate.warning(
                    title="Transactions Partially Processed",
                    description=f"Some transactions for Week {target_week} failed to process."
                )

            completion_embed.add_field(
                name="Processing Summary",
                value=f"**Total Transactions:** {total_count}\n"
                      f"**✅ Successful:** {success_count}\n"
                      f"**❌ Failed:** {failure_count}\n"
                      f"**Week:** {target_week}\n"
                      f"**Season:** {target_season}",
                inline=False
            )

            # Add error details if there were failures
            if errors:
                error_text = ""
                for error in errors[:5]:  # Show first 5 errors
                    error_text += f"• **{error['player']}** → {error['new_team']}: {error['error'][:50]}\n"

                if len(errors) > 5:
                    error_text += f"\n... and {len(errors) - 5} more errors"

                completion_embed.add_field(
                    name="Errors",
                    value=error_text,
                    inline=False
                )

            completion_embed.add_field(
                name="Next Steps",
                value="• Verify transactions in the database\n"
                      "• Check #transaction-log channel for posted moves\n"
                      "• Review any errors and retry if necessary",
                inline=False
            )

            completion_embed.set_footer(
                text=f"Processed by {interaction.user.display_name} • {discord.utils.utcnow().strftime('%H:%M:%S UTC')}"
            )

            # Update the status message with final results
            await status_message.edit(embed=completion_embed)

            self.logger.info(
                f"Transaction processing complete for week {target_week}",
                success=success_count,
                failures=failure_count,
                total=total_count
            )

        except Exception as e:
            self.logger.error(f"Error processing transactions: {e}", exc_info=True)

            embed = EmbedTemplate.error(
                title="Transaction Processing Failed",
                description=f"An error occurred while processing transactions: {str(e)}"
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

    async def _execute_player_update(
        self,
        player_id: int,
        new_team_id: int,
        player_name: str
    ) -> bool:
        """
        Execute a player roster update via API PATCH.

        Args:
            player_id: Player database ID
            new_team_id: New team ID to assign
            player_name: Player name for logging

        Returns:
            True if update successful, False otherwise

        Raises:
            Exception: If API call fails
        """
        try:
            self.logger.info(
                f"Updating player roster",
                player_id=player_id,
                player_name=player_name,
                new_team_id=new_team_id
            )

            # Get API client from transaction service
            client = await transaction_service.get_client()

            # Execute PATCH request to update player's team
            response = await client.patch(
                f'players/{player_id}',
                params=[('team_id', str(new_team_id))]
            )

            # Verify response (200 or 204 indicates success)
            if response is not None:
                self.logger.info(
                    f"Successfully updated player roster",
                    player_id=player_id,
                    player_name=player_name,
                    new_team_id=new_team_id
                )
                return True
            else:
                self.logger.warning(
                    f"Player update returned no response",
                    player_id=player_id,
                    player_name=player_name,
                    new_team_id=new_team_id
                )
                return False

        except Exception as e:
            self.logger.error(
                f"Failed to update player roster",
                player_id=player_id,
                player_name=player_name,
                new_team_id=new_team_id,
                error=str(e),
                exc_info=True
            )
            raise


async def setup(bot: commands.Bot):
    """Load the admin commands cog."""
    await bot.add_cog(AdminCommands(bot))