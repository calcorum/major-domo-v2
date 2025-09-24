"""
Modern /dropadd Command

Interactive transaction builder with real-time validation and elegant UX.
"""
from typing import Optional, List

import discord
from discord.ext import commands
from discord import app_commands

from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from constants import SBA_CURRENT_SEASON

from services.transaction_builder import (
    TransactionBuilder, 
    RosterType,
    TransactionMove,
    get_transaction_builder,
    clear_transaction_builder
)
from services.player_service import player_service
from services.team_service import team_service
from views.transaction_embed import TransactionEmbedView, create_transaction_embed


class DropAddCommands(commands.Cog):
    """Modern transaction builder commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.DropAddCommands')
    
    async def player_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """
        Autocomplete for player names.
        
        Args:
            interaction: Discord interaction
            current: Current input from user
            
        Returns:
            List of player name choices
        """
        if len(current) < 2:
            return []
        
        try:
            # Search for players using the new dedicated search endpoint
            players = await player_service.search_players(current, limit=25, season=SBA_CURRENT_SEASON)

            # Format choices for Discord autocomplete
            choices = []
            for player in players:
                # Format: "Player Name (POS - TEAM)"
                team_info = f"{player.primary_position}"
                if hasattr(player, 'team') and player.team:
                    team_info += f" - {player.team.abbrev}"

                choice_name = f"{player.name} ({team_info})"
                choices.append(app_commands.Choice(name=choice_name, value=player.name))

            return choices
            
        except Exception as e:
            self.logger.error(f"Error in player autocomplete: {e}")
            return []
    
    @app_commands.command(
        name="dropadd",
        description="Interactive transaction builder for player moves"
    )
    @app_commands.describe(
        player="Player name (optional - can add later)",
        destination="Where to move the player: Major League, Minor League, Injured List, or Free Agency"
    )
    @app_commands.autocomplete(player=player_autocomplete)
    @app_commands.choices(destination=[
        app_commands.Choice(name="Major League", value="ml"),
        app_commands.Choice(name="Minor League", value="mil"),
        app_commands.Choice(name="Injured List", value="il"),
        app_commands.Choice(name="Free Agency", value="fa")
    ])
    @logged_command("/dropadd")
    async def dropadd(
        self,
        interaction: discord.Interaction,
        player: Optional[str] = None,
        destination: Optional[str] = None
    ):
        """Interactive transaction builder for complex player moves."""
        await interaction.response.defer()
        
        # Get user's major league team
        major_league_teams = await team_service.get_teams_by_owner(
            interaction.user.id,
            SBA_CURRENT_SEASON,
            roster_type="ml"
        )

        if not major_league_teams:
            await interaction.followup.send(
                "❌ You don't appear to own a major league team in the current season.",
                ephemeral=True
            )
            return

        team = major_league_teams[0]  # Use first major league team
        
        # Get or create transaction builder
        builder = get_transaction_builder(interaction.user.id, team)
        
        # If player and destination provided, try to add the move immediately
        if player and destination:
            success = await self._add_quick_move(builder, player, destination)
            if success:
                self.logger.info(f"Quick move added for {team.abbrev}: {player} → {destination}")
            else:
                self.logger.warning(f"Failed to add quick move: {player} → {destination}")
        
        # Create and display interactive embed
        embed = await create_transaction_embed(builder)
        view = TransactionEmbedView(builder, interaction.user.id)
        
        await interaction.followup.send(embed=embed, view=view)
    
    async def _add_quick_move(
        self, 
        builder: TransactionBuilder, 
        player_name: str, 
        destination_str: str
    ) -> bool:
        """
        Add a move quickly from command parameters by auto-determining the action.
        
        Args:
            builder: TransactionBuilder instance
            player_name: Name of player to move
            destination_str: Destination string (ml, mil, fa)
            
        Returns:
            True if move was added successfully
        """
        try:
            # Find player using the new search endpoint
            players = await player_service.search_players(player_name, limit=10, season=SBA_CURRENT_SEASON)
            if not players:
                self.logger.error(f"Player not found: {player_name}")
                return False
            
            # Use exact match if available, otherwise first result
            player = None
            for p in players:
                if p.name.lower() == player_name.lower():
                    player = p
                    break
            
            if not player:
                player = players[0]  # Use first match
            
            # Parse destination
            destination_map = {
                "ml": RosterType.MAJOR_LEAGUE,
                "mil": RosterType.MINOR_LEAGUE,
                "il": RosterType.INJURED_LIST,
                "fa": RosterType.FREE_AGENCY
            }
            
            to_roster = destination_map.get(destination_str.lower())
            if not to_roster:
                self.logger.error(f"Invalid destination: {destination_str}")
                return False
            
            # Determine player's current roster status based on their team and roster type
            if player.team_id == builder.team.id:
                # Player is on the user's team - need to determine which roster
                # This would need to be enhanced to check actual roster data
                # For now, we'll assume they're coming from Major League
                from_roster = RosterType.MAJOR_LEAGUE
            else:
                # Player is on another team or free agency
                from_roster = RosterType.FREE_AGENCY
            
            # Create move
            move = TransactionMove(
                player=player,
                from_roster=from_roster,
                to_roster=to_roster,
                from_team=None if from_roster == RosterType.FREE_AGENCY else builder.team,
                to_team=None if to_roster == RosterType.FREE_AGENCY else builder.team
            )
            
            success, error_message = builder.add_move(move)
            if not success:
                self.logger.warning(f"Failed to add quick move: {error_message}")
            return success
            
        except Exception as e:
            self.logger.error(f"Error adding quick move: {e}")
            return False
    
    @app_commands.command(
        name="cleartransaction",
        description="Clear your current transaction builder"
    )
    @logged_command("/cleartransaction")
    async def clear_transaction(self, interaction: discord.Interaction):
        """Clear the user's current transaction builder."""
        clear_transaction_builder(interaction.user.id)
        
        await interaction.response.send_message(
            "✅ Your transaction builder has been cleared.",
            ephemeral=True
        )
    
    @app_commands.command(
        name="transactionstatus", 
        description="Show your current transaction builder status"
    )
    @logged_command("/transactionstatus")
    async def transaction_status(self, interaction: discord.Interaction):
        """Show the current status of user's transaction builder."""
        await interaction.response.defer(ephemeral=True)
        
        # Get user's major league team
        major_league_teams = await team_service.get_teams_by_owner(
            interaction.user.id,
            SBA_CURRENT_SEASON,
            roster_type="ml"
        )

        if not major_league_teams:
            await interaction.followup.send(
                "❌ You don't appear to own a major league team in the current season.",
                ephemeral=True
            )
            return

        team = major_league_teams[0]
        builder = get_transaction_builder(interaction.user.id, team)
        
        if builder.is_empty:
            await interaction.followup.send(
                "📋 Your transaction builder is empty. Use `/dropadd` to start building!",
                ephemeral=True
            )
            return
        
        # Show current status
        validation = await builder.validate_transaction()
        
        status_msg = f"📋 **Transaction Builder Status - {team.abbrev}**\n\n"
        status_msg += f"**Moves:** {builder.move_count}\n"
        status_msg += f"**Status:** {'✅ Legal' if validation.is_legal else '❌ Illegal'}\n\n"
        
        if validation.errors:
            status_msg += "**Errors:**\n"
            status_msg += "\n".join([f"• {error}" for error in validation.errors])
            status_msg += "\n\n"
        
        if validation.suggestions:
            status_msg += "**Suggestions:**\n" 
            status_msg += "\n".join([f"💡 {suggestion}" for suggestion in validation.suggestions])
        
        await interaction.followup.send(status_msg, ephemeral=True)


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(DropAddCommands(bot))