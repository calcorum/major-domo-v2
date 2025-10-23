"""
Modern /dropadd Command

Interactive transaction builder with real-time validation and elegant UX.
"""
from typing import Optional, List

import discord
from discord.ext import commands
from discord import app_commands

from config import get_config
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.autocomplete import player_autocomplete
from utils.team_utils import validate_user_has_team

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
    
    
    @app_commands.command(
        name="dropadd",
        description="Build a transaction for next week"
    )
    @app_commands.describe(
        player="Player name; begin typing for autocomplete",
        destination="Where to move the player: Major League, Minor League, or Free Agency"
    )
    @app_commands.autocomplete(player=player_autocomplete)
    @app_commands.choices(destination=[
        app_commands.Choice(name="Major League", value="ml"),
        app_commands.Choice(name="Minor League", value="mil"),
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
        await interaction.response.defer(ephemeral=True)

        # Get user's major league team
        team = await validate_user_has_team(interaction)
        if not team:
            return

        # Get or create transaction builder
        builder = get_transaction_builder(interaction.user.id, team)

        # Handle different scenarios based on builder state and parameters
        if player and destination:
            # User provided both parameters - try to add the move
            success, error_message = await self._add_quick_move(builder, player, destination)

            if success:
                # Move added successfully - show updated transaction builder
                embed = await create_transaction_embed(builder, command_name="/dropadd")
                view = TransactionEmbedView(builder, interaction.user.id, submission_handler="scheduled", command_name="/dropadd")

                success_msg = f"✅ **Added {player} → {destination.upper()}**"
                if builder.move_count > 1:
                    success_msg += f"\n📊 Transaction now has {builder.move_count} moves"

                await interaction.followup.send(
                    content=success_msg,
                    embed=embed,
                    view=view,
                    ephemeral=True
                )
                self.logger.info(f"Move added for {team.abbrev}: {player} → {destination}")

            else:
                # Failed to add move - still show current transaction state
                embed = await create_transaction_embed(builder, command_name="/dropadd")
                view = TransactionEmbedView(builder, interaction.user.id, submission_handler="scheduled", command_name="/dropadd")

                await interaction.followup.send(
                    content=f"❌ **{error_message}**\n"
                             f"💡 Try using autocomplete for player names",
                    embed=embed,
                    view=view,
                    ephemeral=True
                )
                self.logger.warning(f"Failed to add move: {player} → {destination}: {error_message}")
        else:
            # No parameters or incomplete parameters - show current transaction state
            embed = await create_transaction_embed(builder, command_name="/dropadd")
            view = TransactionEmbedView(builder, interaction.user.id, submission_handler="scheduled", command_name="/dropadd")
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    async def _add_quick_move(
        self,
        builder: TransactionBuilder,
        player_name: str,
        destination_str: str
    ) -> tuple[bool, str]:
        """
        Add a move quickly from command parameters by auto-determining the action.

        Args:
            builder: TransactionBuilder instance
            player_name: Name of player to move
            destination_str: Destination string (ml, mil, fa)

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        try:
            # Find player using the new search endpoint
            players = await player_service.search_players(player_name, limit=10, season=get_config().sba_current_season)
            if not players:
                self.logger.error(f"Player not found: {player_name}")
                return False, f"Player '{player_name}' not found"
            
            # Use exact match if available, otherwise first result
            player = None
            for p in players:
                if p.name.lower() == player_name.lower():
                    player = p
                    break

            if not player:
                player = players[0]  # Use first match

            # Check if player belongs to another team (not user's team and not Free Agency)
            if player.team and hasattr(player.team, 'abbrev'):
                # Player belongs to another team if:
                # 1. They have a team assigned AND
                # 2. That team is not Free Agency (abbrev != 'FA') AND
                # 3. That team is not in the same organization as the user's team
                if (player.team.abbrev != 'FA' and
                    not builder.team.is_same_organization(player.team)):
                    self.logger.warning(f"Player {player.name} belongs to {player.team.abbrev}, cannot add to {builder.team.abbrev} transaction")
                    return False, f"{player.name} belongs to {player.team.abbrev} and cannot be added to your transaction"
            
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
                return False, f"Invalid destination: {destination_str}"
            
            # Determine player's current roster status by checking actual roster data
            # Note: Minor League players have different team_id than Major League team
            self.logger.debug(f"🔍 DIAGNOSTIC: Player {player.name} (ID={player.id}) team_id: {player.team_id}, Builder team_id: {builder.team.id}")
            if player.team:
                self.logger.debug(f"🔍 DIAGNOSTIC: Player team abbrev: {player.team.abbrev}")

            await builder.load_roster_data()
            if builder._current_roster:
                # Log roster composition for diagnostics
                ml_count = len(builder._current_roster.active_players)
                mil_count = len(builder._current_roster.minor_league_players)
                il_count = len(builder._current_roster.il_players)

                self.logger.debug(f"🔍 DIAGNOSTIC: Roster loaded for {builder.team.abbrev}: "
                               f"ML={ml_count}, MiL={mil_count}, IL={il_count}")

                # Log ALL player IDs in each roster section
                ml_ids = [p.id for p in builder._current_roster.active_players]
                mil_ids = [p.id for p in builder._current_roster.minor_league_players]
                il_ids = [p.id for p in builder._current_roster.il_players]

                self.logger.debug(f"🔍 DIAGNOSTIC: ML player IDs: {ml_ids}")
                self.logger.debug(f"🔍 DIAGNOSTIC: MiL player IDs: {mil_ids}")
                self.logger.debug(f"🔍 DIAGNOSTIC: IL player IDs: {il_ids}")
                self.logger.debug(f"🔍 DIAGNOSTIC: Searching for player ID: {player.id}")

                # Check which roster section the player is on (regardless of team_id)
                player_on_active = any(p.id == player.id for p in builder._current_roster.active_players)
                player_on_minor = any(p.id == player.id for p in builder._current_roster.minor_league_players)
                player_on_il = any(p.id == player.id for p in builder._current_roster.il_players)

                self.logger.debug(f"🔍 DIAGNOSTIC: Player {player.name} found - ML:{player_on_active}, MiL:{player_on_minor}, IL:{player_on_il}")

                if player_on_active:
                    from_roster = RosterType.MAJOR_LEAGUE
                    self.logger.debug(f"✅ Player {player.name} found on active roster (Major League)")
                elif player_on_minor:
                    from_roster = RosterType.MINOR_LEAGUE
                    self.logger.debug(f"✅ Player {player.name} found on minor league roster")
                elif player_on_il:
                    from_roster = RosterType.INJURED_LIST
                    self.logger.debug(f"✅ Player {player.name} found on injured list")
                else:
                    # Player not found on user's roster - they're from another team or free agency
                    from_roster = RosterType.FREE_AGENCY
                    self.logger.warning(f"⚠️  Player {player.name} (ID={player.id}) not found on user's roster, treating as free agency")

                    # Additional diagnostic: Check if player's team suggests they should be on roster
                    if player.team and builder.team.is_same_organization(player.team):
                        self.logger.error(f"❌ BUG DETECTED: Player {player.name} belongs to {player.team.abbrev} "
                                        f"(same organization as {builder.team.abbrev}) but not found in roster lists!")
                        self.logger.error(f"❌ Player team_id={player.team_id}, roster team_id={builder._current_roster.team_id}")
            else:
                # Couldn't load roster data, assume free agency as safest fallback
                from_roster = RosterType.FREE_AGENCY
                self.logger.error(f"❌ Could not load roster data, assuming {player.name} is free agency")
            
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
                return False, error_message
            return True, ""

        except Exception as e:
            self.logger.error(f"Error adding quick move: {e}")
            return False, f"Error adding move: {str(e)}"
    
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
    


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(DropAddCommands(bot))