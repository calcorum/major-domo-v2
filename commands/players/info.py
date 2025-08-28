"""
Player Information Commands

Implements slash commands for displaying player information and statistics.
"""
from typing import Optional

import discord
from discord.ext import commands

from services.player_service import player_service
from services.stats_service import stats_service
from exceptions import BotException
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from constants import SBA_CURRENT_SEASON
from views.embeds import EmbedColors, EmbedTemplate


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
    @logged_command("/player")
    async def player_info(
        self,
        interaction: discord.Interaction,
        name: str,
        season: Optional[int] = None
    ):
        """Display player card with statistics."""
        # Defer response for potentially slow API calls
        await interaction.response.defer()
        self.logger.debug("Response deferred")
        
        try:
            # Search for player by name (use season parameter or default to current)
            search_season = season or SBA_CURRENT_SEASON
            self.logger.debug("Starting player search", api_call="get_players_by_name", season=search_season)
            players = await player_service.get_players_by_name(name, search_season)
            self.logger.info("Player search completed", players_found=len(players), season=search_season)
            
            if not players:
                # Try fuzzy search as fallback
                self.logger.info("No exact matches found, attempting fuzzy search", search_term=name)
                fuzzy_players = await player_service.search_players_fuzzy(name, limit=10)
                
                if not fuzzy_players:
                    self.logger.warning("No players found even with fuzzy search", search_term=name)
                    await interaction.followup.send(
                        f"❌ No players found matching '{name}'.",
                        ephemeral=True
                    )
                    return
                
                # Show fuzzy search results for user selection
                self.logger.info("Fuzzy search results found", fuzzy_results_count=len(fuzzy_players))
                fuzzy_list = "\n".join([f"• {p.name} ({p.primary_position})" for p in fuzzy_players[:10]])
                await interaction.followup.send(
                    f"🔍 No exact match found for '{name}'. Did you mean one of these?\n{fuzzy_list}\n\nPlease try again with the exact name.",
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
                
                if player is None:
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
            
            # Get player data and statistics concurrently
            self.logger.debug("Fetching player data and statistics", 
                            player_id=player.id, 
                            season=search_season)
            
            # Fetch player data and stats concurrently for better performance
            import asyncio
            player_task = player_service.get_player(player.id)
            stats_task = stats_service.get_player_stats(player.id, search_season)
            
            player_with_team = await player_task
            batting_stats, pitching_stats = await stats_task
            
            if player_with_team is None:
                self.logger.warning("Failed to get player data, using search result")
                player_with_team = player  # Fallback to search result
            else:
                team_info = f"{player_with_team.team.abbrev}" if hasattr(player_with_team, 'team') and player_with_team.team else "No team"
                self.logger.debug("Player data retrieved", team=team_info, 
                                batting_stats=bool(batting_stats), 
                                pitching_stats=bool(pitching_stats))
            
            # Create comprehensive player embed with statistics
            self.logger.debug("Creating Discord embed with statistics")
            embed = await self._create_player_embed_with_stats(
                player_with_team, 
                search_season, 
                batting_stats, 
                pitching_stats
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            error_msg = "❌ Error retrieving player information."
            
            if interaction.response.is_done():
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                await interaction.response.send_message(error_msg, ephemeral=True)
            raise  # Re-raise to let decorator handle logging
    
    async def _create_player_embed_with_stats(
        self, 
        player, 
        season: int, 
        batting_stats=None, 
        pitching_stats=None
    ) -> discord.Embed:
        """Create a comprehensive player embed with statistics."""
        # Determine embed color based on team
        embed_color = EmbedColors.PRIMARY
        if hasattr(player, 'team') and player.team and hasattr(player.team, 'color'):
            try:
                # Convert hex color string to int
                embed_color = int(player.team.color, 16)
            except (ValueError, TypeError):
                embed_color = EmbedColors.PRIMARY
        
        # Create base embed
        embed = EmbedTemplate.create_base_embed(
            title=f"🏟️ {player.name}",
            color=embed_color
        )
        
        # Set team logo beside player name (as author icon)
        if hasattr(player, 'team') and player.team and hasattr(player.team, 'thumbnail') and player.team.thumbnail:
            embed.set_author(
                name=player.name,
                icon_url=player.team.thumbnail
            )
            # Remove the emoji from title since we're using author
            embed.title = None
        
        # Basic info section
        embed.add_field(
            name="Position",
            value=player.primary_position,
            inline=True
        )
        
        if hasattr(player, 'team') and player.team:
            embed.add_field(
                name="Team",
                value=f"{player.team.abbrev} - {player.team.sname}",
                inline=True
            )
        
        embed.add_field(
            name="sWAR",
            value=f"{player.wara:.1f}",
            inline=True
        )
        
        # All positions if multiple
        if len(player.positions) > 1:
            embed.add_field(
                name="Positions",
                value=", ".join(player.positions),
                inline=True
            )
        
        embed.add_field(
            name="Season",
            value=str(season),
            inline=True
        )
        
        # Add batting stats if available
        if batting_stats:
            self.logger.debug("Adding batting statistics to embed")
            batting_value = (
                f"**AVG/OBP/SLG:** {batting_stats.avg:.3f}/{batting_stats.obp:.3f}/{batting_stats.slg:.3f}\n"
                f"**OPS:** {batting_stats.ops:.3f} | **wOBA:** {batting_stats.woba:.3f}\n"
                f"**HR:** {batting_stats.homerun} | **RBI:** {batting_stats.rbi} | **R:** {batting_stats.run}\n"
                f"**AB:** {batting_stats.ab} | **H:** {batting_stats.hit} | **BB:** {batting_stats.bb} | **SO:** {batting_stats.so}"
            )
            embed.add_field(
                name="⚾ Batting Stats",
                value=batting_value,
                inline=False
            )
        
        # Add pitching stats if available
        if pitching_stats:
            self.logger.debug("Adding pitching statistics to embed")
            ip = pitching_stats.innings_pitched
            pitching_value = (
                f"**W-L:** {pitching_stats.win}-{pitching_stats.loss} | **ERA:** {pitching_stats.era:.2f}\n"
                f"**WHIP:** {pitching_stats.whip:.2f} | **IP:** {ip:.1f}\n"
                f"**SO:** {pitching_stats.so} | **BB:** {pitching_stats.bb} | **H:** {pitching_stats.hits}\n"
                f"**GS:** {pitching_stats.gs} | **SV:** {pitching_stats.saves} | **HLD:** {pitching_stats.hold}"
            )
            embed.add_field(
                name="🥎 Pitching Stats", 
                value=pitching_value,
                inline=False
            )
        
        # Add a note if no stats are available
        if not batting_stats and not pitching_stats:
            embed.add_field(
                name="📊 Statistics",
                value="No statistics available for this season.",
                inline=False
            )
        
        # Set player card as main image
        if player.image:
            embed.set_image(url=player.image)
            self.logger.debug("Player card image added to embed", image_url=player.image)
        
        # Set thumbnail with priority: fancycard → headshot → team logo
        thumbnail_url = None
        thumbnail_source = None
        
        if hasattr(player, 'vanity_card') and player.vanity_card:
            thumbnail_url = player.vanity_card
            thumbnail_source = "fancycard"
        elif hasattr(player, 'headshot') and player.headshot:
            thumbnail_url = player.headshot
            thumbnail_source = "headshot"
        elif hasattr(player, 'team') and player.team and hasattr(player.team, 'thumbnail') and player.team.thumbnail:
            thumbnail_url = player.team.thumbnail
            thumbnail_source = "team logo"
        
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
            self.logger.debug(f"Thumbnail set from {thumbnail_source}", thumbnail_url=thumbnail_url)
        
        # Footer with player ID and additional info
        footer_text = f"Player ID: {player.id}"
        if batting_stats and pitching_stats:
            footer_text += " • Two-way player"
        embed.set_footer(text=footer_text)
        
        return embed


async def setup(bot: commands.Bot):
    """Load the player info commands cog."""
    await bot.add_cog(PlayerInfoCommands(bot))