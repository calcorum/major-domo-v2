"""
Player Information Commands

Implements slash commands for displaying player information and statistics.
"""
from typing import Optional, List

import discord
from discord.ext import commands

from config import get_config

from services.player_service import player_service
from services.stats_service import stats_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from views.players import PlayerStatsView


async def player_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[discord.app_commands.Choice[str]]:
    """Autocomplete for player names."""
    if len(current) < 2:
        return []

    try:
        # Use the dedicated search endpoint to get matching players
        players = await player_service.search_players(current, limit=25, season=get_config().sba_season)

        # Convert to discord choices, limiting to 25 (Discord's max)
        choices = []
        for player in players[:25]:
            # Format: "Player Name (Position) - Team"
            display_name = f"{player.name} ({player.primary_position})"
            if hasattr(player, 'team') and player.team:
                display_name += f" - {player.team.abbrev}"

            choices.append(discord.app_commands.Choice(
                name=display_name,
                value=player.name
            ))

        return choices

    except Exception:
        # Return empty list on error to avoid breaking autocomplete
        return []


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
    @discord.app_commands.autocomplete(name=player_name_autocomplete)
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
        
        # Search for player by name (use season parameter or default to current)
        search_season = season or get_config().sba_season
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
        player_with_team, (batting_stats, pitching_stats) = await asyncio.gather(
            player_service.get_player(player.id),
            stats_service.get_player_stats(player.id, search_season)
        )
        
        if player_with_team is None:
            self.logger.warning("Failed to get player data, using search result")
            player_with_team = player  # Fallback to search result
        else:
            team_info = f"{player_with_team.team.abbrev}" if hasattr(player_with_team, 'team') and player_with_team.team else "No team"
            self.logger.debug("Player data retrieved", team=team_info, 
                            batting_stats=bool(batting_stats), 
                            pitching_stats=bool(pitching_stats))
        
        # Create interactive player view with toggleable statistics
        self.logger.debug("Creating PlayerStatsView with toggleable statistics")
        view = PlayerStatsView(
            player=player_with_team,
            season=search_season,
            batting_stats=batting_stats,
            pitching_stats=pitching_stats,
            user_id=None # setting to None so any GM can toggle the stats views
        )

        # Get initial embed with stats hidden
        embed = await view.get_initial_embed()

        # Send with interactive view
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    """Load the player info commands cog."""
    await bot.add_cog(PlayerInfoCommands(bot))