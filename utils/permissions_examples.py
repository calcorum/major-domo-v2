"""
Permission Decorator Usage Examples

This file demonstrates how to use the permission decorators for different
command access patterns across multiple servers.
"""
import discord
from discord.ext import commands
from discord import app_commands

from utils.permissions import (
    global_command,
    league_only,
    requires_team,
    admin_only,
    league_admin_only
)
from utils.decorators import logged_command


# Example 1: Global Command (Available Everywhere)
# Use case: Dice rolling, utilities, weather, etc.
class GlobalCommandExample(commands.Cog):
    """Commands available in all servers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="roll", description="Roll dice")
    @global_command()  # Optional - commands are global by default
    @logged_command("/roll")
    async def roll_dice(self, interaction: discord.Interaction, dice: str):
        """
        Available in ALL servers.
        Anyone can use this command.
        """
        await interaction.response.defer()
        # Dice rolling logic here
        await interaction.followup.send(f"🎲 Rolled {dice}")


# Example 2: League-Only Command
# Use case: Team info, player stats, league standings, etc.
class LeagueCommandExample(commands.Cog):
    """Commands only available in the league server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="team", description="View team information")
    @league_only()  # Restricts to league server
    @logged_command("/team")
    async def team_info(self, interaction: discord.Interaction, abbrev: str):
        """
        Only works in the league server.
        Shows error in other servers.
        """
        await interaction.response.defer()
        # Team lookup logic here
        await interaction.followup.send(f"Team info for {abbrev}")


# Example 3: Global Command with Team Requirement
# Use case: User wants to use /mymoves from any server, but must have a team
class GlobalTeamCommandExample(commands.Cog):
    """Global commands that require league participation."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="mymoves", description="View your pending moves")
    @requires_team()  # Works anywhere, but user must have a team
    @logged_command("/mymoves")
    async def my_moves(self, interaction: discord.Interaction):
        """
        Available in ALL servers.
        But user must have a team in the league.
        Team data is accessible via interaction.extras['user_team']
        """
        await interaction.response.defer()

        # Access the user's team data
        user_team = interaction.extras.get('user_team')
        if user_team:
            team_name = user_team['name']
            await interaction.followup.send(f"Moves for {team_name}...")
        else:
            # This shouldn't happen - decorator handles it
            await interaction.followup.send("Error: No team found")


# Example 4: Admin Command (Global but Requires Admin)
# Use case: Bot management commands that work in any server
class AdminCommandExample(commands.Cog):
    """Admin commands available in any server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="sync", description="Sync bot commands")
    @admin_only()  # Requires server admin permissions
    @logged_command("/sync")
    async def sync_commands(self, interaction: discord.Interaction):
        """
        Available in ALL servers.
        But user must be a server administrator.
        """
        await interaction.response.defer(ephemeral=True)
        # Command sync logic here
        await interaction.followup.send("✅ Commands synced", ephemeral=True)


# Example 5: League Admin Command
# Use case: League-specific admin functions
class LeagueAdminCommandExample(commands.Cog):
    """Admin commands for league management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="force-process", description="Force transaction processing")
    @league_admin_only()  # Must be admin AND in league server
    @logged_command("/force-process")
    async def force_process(self, interaction: discord.Interaction):
        """
        Only works in the league server.
        User must be a server administrator.
        """
        await interaction.response.defer(ephemeral=True)
        # Transaction processing logic here
        await interaction.followup.send("✅ Transactions processed", ephemeral=True)


# Example 6: Combining Multiple Decorators
# Use case: Complex permission requirements
class CombinedPermissionsExample(commands.Cog):
    """Commands with multiple permission requirements."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="my-league-moves", description="View your moves (league server only)")
    @league_only()  # Must be in league server
    @requires_team()  # AND must have a team
    @logged_command("/my-league-moves")
    async def league_moves(self, interaction: discord.Interaction):
        """
        Only works in league server.
        User must have a team.
        Combines both restrictions.
        """
        await interaction.response.defer()

        user_team = interaction.extras.get('user_team')
        team_name = user_team['name'] if user_team else "Unknown"

        await interaction.followup.send(f"League moves for {team_name}...")


# Example 7: Package-Level Organization
# How to organize commands by scope in your packages

# In commands/dice/__init__.py (GLOBAL commands)
async def setup_dice(bot: commands.Bot):
    """All dice commands are global - available everywhere."""
    await bot.add_cog(DiceCommands(bot))
    return 1, 0, []


# In commands/league/__init__.py (LEAGUE-ONLY commands)
async def setup_league(bot: commands.Bot):
    """All league commands are league-only - use @league_only() decorator."""
    await bot.add_cog(LeagueCommands(bot))
    return 1, 0, []


# In commands/transactions/__init__.py (MIXED commands)
async def setup_transactions(bot: commands.Bot):
    """
    Mixed scope commands:
    - /trade: @league_only() - complex UI, league server only
    - /mymoves: @requires_team() - global but needs team
    - /legal: @league_only() - lookup command for league context
    """
    await bot.add_cog(TransactionCommands(bot))
    return 1, 0, []


"""
Summary of Permission Patterns:

1. GLOBAL (no decorator needed):
   - Dice rolling
   - Weather
   - Utilities
   - General help

2. @league_only():
   - Team information
   - Player stats
   - League standings
   - Schedule
   - Rosters

3. @requires_team():
   - My moves (can check from anywhere)
   - My team (if you want global access)
   - Personal league stats

4. @admin_only():
   - Bot sync
   - Bot shutdown
   - System management

5. @league_admin_only():
   - Force process transactions
   - League configuration
   - Season management

6. @league_only() + @requires_team():
   - Trade initiation
   - Advanced league features
   - GM-only league commands
"""
