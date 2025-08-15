"""
Player Information Commands

Implements slash commands for displaying player information and statistics.
"""
from typing import Optional

import discord
from discord.ext import commands

from services.player_service import player_service
from exceptions import BotException
from utils.logging import get_contextual_logger, set_discord_context
from constants import SBA_CURRENT_SEASON


class PlayerInfoCommands(commands.Cog):
    """Player information and statistics command handlers."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.PlayerInfoCommands')
    
    @discord.app_commands.command(
        name="player",
        description="Display player information and statistics"
    )
    @discord.app_commands.describe(
        name="Player name to search for",
        season="Season to show stats for (defaults to current season)"
    )
    async def player_info(
        self,
        interaction: discord.Interaction,
        name: str,
        season: Optional[int] = None
    ):
        """Display player card with statistics."""
        # Set up logging context for this command
        set_discord_context(
            interaction=interaction,
            command="/player",
            player_name=name,
            season=season
        )
        
        # Start operation timing and tracing
        trace_id = self.logger.start_operation("player_info_command")
        
        try:
            self.logger.info("Player info command started")
            
            # Defer response for potentially slow API calls
            await interaction.response.defer()
            self.logger.debug("Response deferred")
            
            # Search for player by name (use season parameter or default to current)
            search_season = season or SBA_CURRENT_SEASON
            self.logger.debug("Starting player search", api_call="get_players_by_name", season=search_season)
            players = await player_service.get_players_by_name(name, search_season)
            self.logger.info("Player search completed", players_found=len(players), season=search_season)
            
            if not players:
                self.logger.warning("No players found for search", search_term=name)
                await interaction.followup.send(
                    f"❌ No players found matching '{name}'.",
                    ephemeral=True
                )
                return
            
            # If multiple players, try exact match first
            player = None
            if len(players) == 1:
                player = players[0]
                self.logger.debug("Single player found", player_id=player.id, player_name=player.name)
            else:
                self.logger.debug("Multiple players found, attempting exact match", candidate_count=len(players))
                
                # Try exact match
                for p in players:
                    if p.name.lower() == name.lower():
                        player = p
                        self.logger.debug("Exact match found", player_id=player.id, player_name=player.name)
                        break
                
                if not player:
                    # Show multiple options
                    candidate_names = [p.name for p in players[:10]]
                    self.logger.info("Multiple candidates found, requiring user clarification", 
                                   candidates=candidate_names)
                    
                    player_list = "\n".join([f"• {p.name} ({p.primary_position})" for p in players[:10]])
                    await interaction.followup.send(
                        f"🔍 Multiple players found for '{name}':\n{player_list}\n\nPlease be more specific.",
                        ephemeral=True
                    )
                    return
            
            # Get player with team information
            self.logger.debug("Fetching player with team information", 
                            player_id=player.id, 
                            api_call="get_player_with_team")
            
            player_with_team = await player_service.get_player_with_team(player.id)
            if not player_with_team:
                self.logger.warning("Failed to get player with team, using basic player data")
                player_with_team = player  # Fallback to player without team
            else:
                team_info = f"{player_with_team.team.abbrev}" if hasattr(player_with_team, 'team') and player_with_team.team else "No team"
                self.logger.debug("Player with team information retrieved", team=team_info)
            
            # Create player embed
            self.logger.debug("Creating Discord embed")
            embed = discord.Embed(
                title=f"🏟️ {player_with_team.name}",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Basic info
            embed.add_field(
                name="Position",
                value=player_with_team.primary_position,
                inline=True
            )
            
            if hasattr(player_with_team, 'team') and player_with_team.team:
                embed.add_field(
                    name="Team",
                    value=f"{player_with_team.team.abbrev} - {player_with_team.team.sname}",
                    inline=True
                )
            
            embed.add_field(
                name="WARA",
                value=f"{player_with_team.wara:.1f}",
                inline=True
            )
            
            season_text = season or player_with_team.season
            embed.add_field(
                name="Season",
                value=str(season_text),
                inline=True
            )
            
            # All positions if multiple
            if len(player_with_team.positions) > 1:
                embed.add_field(
                    name="All Positions",
                    value=", ".join(player_with_team.positions),
                    inline=True
                )
            
            # Player image if available
            if player_with_team.image:
                embed.set_thumbnail(url=player_with_team.image)
                self.logger.debug("Player image added to embed", image_url=player_with_team.image)
            
            embed.set_footer(text=f"Player ID: {player_with_team.id}")
            
            await interaction.followup.send(embed=embed)
            self.logger.info("Player info command completed successfully", 
                           final_player_id=player_with_team.id,
                           final_player_name=player_with_team.name)
            
        except Exception as e:
            self.logger.error("Player info command failed", error=e)
            error_msg = "❌ Error retrieving player information."
            
            if interaction.response.is_done():
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                await interaction.response.send_message(error_msg, ephemeral=True)


async def setup(bot: commands.Bot):
    """Load the player info commands cog."""
    await bot.add_cog(PlayerInfoCommands(bot))