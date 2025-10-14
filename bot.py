"""
Discord Bot v2.0 - Main Entry Point

Modern discord.py bot with application commands and proper error handling.
"""
import asyncio
import hashlib
import json
import logging
import os
from logging.handlers import RotatingFileHandler

import discord
from discord.ext import commands

from config import get_config
from exceptions import BotException
from api.client import get_global_client, cleanup_global_client
from utils.random_gen import STARTUP_WATCHING, random_from_list
from views.embeds import EmbedTemplate, EmbedColors


def setup_logging():
    """Configure hybrid logging: human-readable console + structured JSON files."""
    from utils.logging import JSONFormatter
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Configure root logger
    config = get_config()
    logger = logging.getLogger('discord_bot_v2')
    logger.setLevel(getattr(logging, config.log_level.upper()))
    
    # Console handler - detailed format for development debugging
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # JSON file handler - structured logging for monitoring and analysis
    json_handler = RotatingFileHandler(
        'logs/discord_bot_v2.json',
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5
    )
    json_handler.setFormatter(JSONFormatter())
    logger.addHandler(json_handler)
    
    # Configure root logger for third-party libraries (discord.py, aiohttp, etc.)
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.log_level.upper()))
    
    # Add handlers to root logger so third-party loggers inherit them
    if not root_logger.handlers:  # Avoid duplicate handlers
        root_logger.addHandler(console_handler)
        root_logger.addHandler(json_handler)
    
    # Prevent discord_bot_v2 logger from propagating to root to avoid duplicate messages
    # (bot logs will still appear via its own handlers, third-party logs via root handlers)
    # To revert: remove the line below and bot logs will appear twice
    logger.propagate = False
    
    return logger


class SBABot(commands.Bot):
    """Custom bot class for SBA league management."""
    
    def __init__(self):
        # Configure intents
        intents = discord.Intents.default()
        intents.message_content = True  # For legacy commands if needed
        intents.members = True  # For member management
        
        super().__init__(
            command_prefix='!',  # Legacy prefix, primarily using slash commands
            intents=intents,
            description="Major Domo v2.0"
        )
        
        self.logger = logging.getLogger('discord_bot_v2')
    
    async def setup_hook(self):
        """Called when the bot is starting up."""
        self.logger.info("Setting up bot...")
        
        # Load command packages
        await self._load_command_packages()
        
        # Initialize cleanup tasks
        await self._setup_background_tasks()
        
        # Smart command syncing: auto-sync in development if changes detected
        config = get_config()
        if config.is_development:
            if await self._should_sync_commands():
                self.logger.info("Development mode: changes detected, syncing commands...")
                await self._sync_commands()
                await self._save_command_hash()
            else:
                self.logger.info("Development mode: no command changes detected, skipping sync")
        else:
            self.logger.info("Production mode: commands loaded but not auto-synced")
            self.logger.info("Use /sync command to manually sync when needed")
    
    async def _load_command_packages(self):
        """Load all command packages with resilient error handling."""
        from commands.players import setup_players
        from commands.teams import setup_teams
        from commands.league import setup_league
        from commands.custom_commands import setup_custom_commands
        from commands.admin import setup_admin
        from commands.transactions import setup_transactions
        from commands.dice import setup_dice
        from commands.voice import setup_voice
        from commands.utilities import setup_utilities
        from commands.help import setup_help_commands
        from commands.profile import setup_profile_commands
        from commands.soak import setup_soak

        # Define command packages to load
        command_packages = [
            ("players", setup_players),
            ("teams", setup_teams),
            ("league", setup_league),
            ("custom_commands", setup_custom_commands),
            ("admin", setup_admin),
            ("transactions", setup_transactions),
            ("dice", setup_dice),
            ("voice", setup_voice),
            ("utilities", setup_utilities),
            ("help", setup_help_commands),
            ("profile", setup_profile_commands),
            ("soak", setup_soak),
        ]
        
        total_successful = 0
        total_failed = 0
        
        for package_name, setup_func in command_packages:
            try:
                self.logger.info(f"Loading {package_name} commands...")
                successful, failed, failed_modules = await setup_func(self)
                total_successful += successful
                total_failed += failed
                
                if failed == 0:
                    self.logger.info(f"✅ {package_name} commands loaded successfully ({successful} cogs)")
                else:
                    self.logger.warning(f"⚠️  {package_name} commands partially loaded: {successful} successful, {failed} failed")
                    
            except Exception as e:
                self.logger.error(f"❌ Failed to load {package_name} package: {e}", exc_info=True)
                total_failed += 1
        
        # Log overall summary
        if total_failed == 0:
            self.logger.info(f"🎉 All command packages loaded successfully ({total_successful} total cogs)")
        else:
            self.logger.warning(f"⚠️  Command loading completed with issues: {total_successful} successful, {total_failed} failed")
    
    async def _setup_background_tasks(self):
        """Initialize background tasks for the bot."""
        try:
            self.logger.info("Setting up background tasks...")

            # Initialize custom command cleanup task
            from tasks.custom_command_cleanup import setup_cleanup_task
            self.custom_command_cleanup = setup_cleanup_task(self)

            # Initialize voice channel cleanup service
            from commands.voice.cleanup_service import VoiceChannelCleanupService
            self.voice_cleanup_service = VoiceChannelCleanupService()

            # Start voice channel monitoring (includes startup verification)
            import asyncio
            asyncio.create_task(self.voice_cleanup_service.start_monitoring(self))
            self.logger.info("✅ Voice channel cleanup service started")

            self.logger.info("✅ Background tasks initialized successfully")

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize background tasks: {e}", exc_info=True)
    
    async def _should_sync_commands(self) -> bool:
        """Check if commands have changed since last sync."""
        try:
            # Create hash of current command tree
            commands_data = []
            for cmd in self.tree.get_commands():
                # Handle different command types properly
                cmd_dict = {}
                cmd_dict['name'] = cmd.name
                cmd_dict['type'] = type(cmd).__name__
                
                # Add description if available (most command types have this)
                if hasattr(cmd, 'description'):
                    cmd_dict['description'] = cmd.description # type: ignore
                
                # Add parameters for Command objects
                if isinstance(cmd, discord.app_commands.Command):
                    cmd_dict['parameters'] = [
                        {
                            'name': param.name,
                            'description': param.description,
                            'required': param.required,
                            'type': str(param.type)
                        } for param in cmd.parameters
                    ]
                elif isinstance(cmd, discord.app_commands.Group):
                    # For groups, include subcommands
                    cmd_dict['subcommands'] = [subcmd.name for subcmd in cmd.commands]
                
                commands_data.append(cmd_dict)
            
            # Sort for consistent hashing
            commands_data.sort(key=lambda x: x['name'])
            current_hash = hashlib.md5(
                json.dumps(commands_data, sort_keys=True).encode()
            ).hexdigest()
            
            # Compare with stored hash
            hash_file = '.last_command_hash'
            if os.path.exists(hash_file):
                with open(hash_file, 'r') as f:
                    last_hash = f.read().strip()
                return current_hash != last_hash
            else:
                # No previous hash = first run, should sync
                return True
                
        except Exception as e:
            self.logger.warning(f"Error checking command hash: {e}")
            # If we can't determine changes, err on the side of syncing
            return True
    
    async def _save_command_hash(self):
        """Save current command hash for future comparison."""
        try:
            # Create hash of current command tree (same logic as _should_sync_commands)
            commands_data = []
            for cmd in self.tree.get_commands():
                # Handle different command types properly
                cmd_dict = {}
                cmd_dict['name'] = cmd.name
                cmd_dict['type'] = type(cmd).__name__
                
                # Add description if available (most command types have this)
                if hasattr(cmd, 'description'):
                    cmd_dict['description'] = cmd.description # type: ignore
                
                # Add parameters for Command objects
                if isinstance(cmd, discord.app_commands.Command):
                    cmd_dict['parameters'] = [
                        {
                            'name': param.name,
                            'description': param.description,
                            'required': param.required,
                            'type': str(param.type)
                        } for param in cmd.parameters
                    ]
                elif isinstance(cmd, discord.app_commands.Group):
                    # For groups, include subcommands
                    cmd_dict['subcommands'] = [subcmd.name for subcmd in cmd.commands]
                
                commands_data.append(cmd_dict)
            
            commands_data.sort(key=lambda x: x['name'])
            current_hash = hashlib.md5(
                json.dumps(commands_data, sort_keys=True).encode()
            ).hexdigest()
            
            # Save hash to file
            with open('.last_command_hash', 'w') as f:
                f.write(current_hash)
                
        except Exception as e:
            self.logger.warning(f"Error saving command hash: {e}")
    
    async def _sync_commands(self):
        """Internal method to sync commands."""
        config = get_config()
        if config.guild_id:
            guild = discord.Object(id=config.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            self.logger.info(f"Synced {len(synced)} commands to guild {config.guild_id}")
        else:
            synced = await self.tree.sync()
            self.logger.info(f"Synced {len(synced)} commands globally")
    
    async def on_ready(self):
        """Called when the bot is ready."""
        self.logger.info(f"Bot ready! Logged in as {self.user}")
        self.logger.info(f"Connected to {len(self.guilds)} guilds")
        
        # Set activity status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=random_from_list(STARTUP_WATCHING)
        )
        await self.change_presence(activity=activity)
    
    async def on_error(self, event_method: str, /, *args, **kwargs):
        """Global error handler for events."""
        self.logger.error(f"Error in event {event_method}", exc_info=True)
    
    async def close(self):
        """Clean shutdown of the bot."""
        self.logger.info("Bot shutting down...")
        
        # Stop background tasks
        if hasattr(self, 'custom_command_cleanup'):
            try:
                self.custom_command_cleanup.cleanup_task.cancel()
                self.logger.info("Custom command cleanup task stopped")
            except Exception as e:
                self.logger.error(f"Error stopping cleanup task: {e}")

        if hasattr(self, 'voice_cleanup_service'):
            try:
                self.voice_cleanup_service.stop_monitoring()
                self.logger.info("Voice channel cleanup service stopped")
            except Exception as e:
                self.logger.error(f"Error stopping voice cleanup service: {e}")
        
        # Call parent close method
        await super().close()
        self.logger.info("Bot shutdown complete")


# Create global bot instance
bot = SBABot()


@bot.tree.command(name="health", description="Check bot and API health status")
async def health_command(interaction: discord.Interaction):
    """Health check command to verify bot and API connectivity."""
    logger = logging.getLogger('discord_bot_v2')
    
    try:
        # Check API connectivity
        api_status = "✅ Connected"
        try:
            client = await get_global_client()
            # Test API with a simple request
            result = await client.get('current')
            if result:
                api_status = "✅ Connected"
            else:
                api_status = "⚠️ API returned no data"
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            api_status = f"❌ Error: {str(e)}"
        
        # Bot health info
        guild_count = len(bot.guilds)
        
        # Create health status embed
        embed = EmbedTemplate.success(
            title="🏥 Bot Health Check"
        )
        
        embed.add_field(name="Bot Status", value="✅ Online", inline=True)
        embed.add_field(name="API Status", value=api_status, inline=True)
        embed.add_field(name="Guilds", value=str(guild_count), inline=True)
        embed.add_field(name="Latency", value=f"{bot.latency*1000:.1f}ms", inline=True)
        
        if bot.user:
            embed.set_footer(text=f"Bot: {bot.user.name}", icon_url=bot.user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Health check command error: {e}", exc_info=True)
        await interaction.response.send_message(
            f"❌ Health check failed: {str(e)}",
            ephemeral=True
        )


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """Global error handler for application commands."""
    logger = logging.getLogger('discord_bot_v2')
    
    # Handle specific error types
    if isinstance(error, discord.app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"⏰ Command on cooldown. Try again in {error.retry_after:.1f} seconds.",
            ephemeral=True
        )
    elif isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.",
            ephemeral=True
        )
    elif isinstance(error, discord.app_commands.CommandNotFound):
        await interaction.response.send_message(
            "❌ Command not found. Use `/help` to see available commands.",
            ephemeral=True
        )
    elif isinstance(error, BotException):
        # Our custom exceptions - show user-friendly message
        await interaction.response.send_message(
            f"❌ {str(error)}",
            ephemeral=True
        )
    else:
        # Unexpected errors - log and show generic message
        logger.error(f"Unhandled command error: {error}", exc_info=True)
        
        message = "❌ An unexpected error occurred. Please try again."
        config = get_config()
        if config.is_development:
            message += f"\n\nDevelopment error: {str(error)}"
        
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def main():
    """Main entry point."""
    logger = setup_logging()
    
    config = get_config()
    logger.info("Starting Discord Bot v2.0")
    logger.info(f"Environment: {config.environment}")
    logger.info(f"Guild ID: {config.guild_id}")
    
    try:
        await bot.start(config.bot_token)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await cleanup_global_client()
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())